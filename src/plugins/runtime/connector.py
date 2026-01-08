"""Plugin runtime connector (inspired by LangBot).

Manages communication with plugin runtime process via stdio.
"""

import asyncio
import json
import sys
import os
from pathlib import Path
from typing import Optional, Dict, Any, Callable, Coroutine
from datetime import datetime

from ...core.logger import get_logger
from ...core.event_bus import EventBus
from ...core.database import DatabaseManager
from ..interceptor import InterceptorRegistry

logger = get_logger(__name__)


class PluginRuntimeConnector:
    """Plugin runtime connector.
    
    Manages plugin runtime process and handles communication via stdio.
    Inspired by LangBot's PluginRuntimeConnector.
    """
    
    def __init__(
        self,
        event_bus: EventBus,
        db_manager: DatabaseManager,
        app: Optional[Any] = None,
        runtime_script: Optional[str] = None
    ):
        """Initialize plugin runtime connector.
        
        Args:
            event_bus: Event bus for framework events
            db_manager: Database manager for plugin settings
            app: Application instance (for accessing OneBot adapter)
            runtime_script: Path to plugin runtime script (default: auto-detect)
        """
        self.event_bus = event_bus
        self.db_manager = db_manager
        self.app = app
        
        # Runtime process
        self.runtime_process: Optional[asyncio.subprocess.Process] = None
        self.runtime_task: Optional[asyncio.Task] = None
        self.heartbeat_task: Optional[asyncio.Task] = None
        
        # Runtime script path
        if runtime_script:
            self.runtime_script = Path(runtime_script)
        else:
            # Default: src/plugins/runtime/main.py
            self.runtime_script = Path(__file__).parent / "main.py"
        
        # State
        self.is_running = False
        self.is_enabled = True
        
        # Callbacks
        self.disconnect_callback: Optional[Callable[[], Coroutine]] = None
        
        # Interceptor registry for high-privilege plugins
        self.interceptor_registry = InterceptorRegistry()
    
    async def initialize(self):
        """Initialize plugin runtime."""
        if not self.is_enabled:
            logger.info("Plugin system is disabled")
            return
        
        if not self.runtime_script.exists():
            logger.error(f"Plugin runtime script not found", path=str(self.runtime_script))
            return
        
        try:
            # Start runtime process
            await self._start_runtime_process()
            
            # Start heartbeat
            self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            
            # Initialize plugins
            await self._initialize_plugins()
            
            # Subscribe to OneBot events
            self._subscribe_to_events()
            
            logger.info("Plugin runtime initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize plugin runtime: {e}", exc_info=True)
            raise
    
    def _subscribe_to_events(self):
        """Subscribe to EventBus events and forward to plugins."""
        # Check if already subscribed (prevent duplicate subscriptions)
        if hasattr(self, '_events_subscribed') and self._events_subscribed:
            logger.warning("Events already subscribed, skipping duplicate subscription")
            return
        
        # Import Event class
        from ...core.event_bus import Event
        
        # Subscribe to all OneBot events
        async def forward_event(event: Event):
            """Forward event to plugin runtime.
            
            Args:
                event: Event object from EventBus
            """
            logger.debug(f"Forwarding event {event.name} to plugins", 
                       source=event.source, event_id=event.event_id)
            # Extract payload and forward to plugins
            await self.emit_event(event.name, event.payload, source=event.source)
        
        # Subscribe to specific OneBot event types (EventBus doesn't support wildcards)
        onebot_events = ["onebot.message", "onebot.notice", "onebot.request", "onebot.meta_event"]
        for event_name in onebot_events:
            self.event_bus.subscribe(event_name, forward_event)
            logger.info(f"Subscribed to event: {event_name}")
        
        self._events_subscribed = True
        logger.info("All OneBot event subscriptions complete")
    
    async def _start_runtime_process(self):
        """Start plugin runtime process."""
        # Ensure old process is terminated before starting new one
        if self.runtime_process and self.runtime_process.returncode is None:
            logger.warning("Old runtime process still running, terminating it first...")
            try:
                self.runtime_process.terminate()
                await asyncio.wait_for(self.runtime_process.wait(), timeout=2.0)
                logger.info("Old runtime process terminated")
            except (asyncio.TimeoutError, ProcessLookupError):
                try:
                    logger.warning("Force killing old runtime process...")
                    self.runtime_process.kill()
                    await self.runtime_process.wait()
                    logger.info("Old runtime process killed")
                except ProcessLookupError:
                    logger.debug("Old runtime process already terminated")
            except Exception as e:
                logger.error(f"Error terminating old runtime process: {e}")
            finally:
                self.runtime_process = None
        
        # Check for orphaned processes (processes running the runtime script)
        # This helps detect if previous processes weren't cleaned up
        try:
            import psutil
            current_pid = os.getpid()
            runtime_script_str = str(self.runtime_script)
            
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['pid'] == current_pid:
                        continue
                    
                    cmdline = proc.info.get('cmdline', [])
                    if cmdline and runtime_script_str in ' '.join(cmdline):
                        logger.warning(f"Found orphaned plugin runtime process: PID {proc.info['pid']}, terminating...")
                        try:
                            proc_obj = psutil.Process(proc.info['pid'])
                            proc_obj.terminate()
                            proc_obj.wait(timeout=2)
                            logger.info(f"Orphaned process {proc.info['pid']} terminated")
                        except (psutil.NoSuchProcess, psutil.TimeoutExpired):
                            try:
                                proc_obj.kill()
                                logger.info(f"Orphaned process {proc.info['pid']} killed")
                            except psutil.NoSuchProcess:
                                pass
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except ImportError:
            logger.debug("psutil not available, skipping orphaned process check")
        except Exception as e:
            logger.warning(f"Error checking for orphaned processes: {e}")
        
        logger.info("Starting plugin runtime process", script=str(self.runtime_script))
        
        # Start subprocess with stdio pipes
        self.runtime_process = await asyncio.create_subprocess_exec(
            sys.executable,
            str(self.runtime_script),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        # Set larger limit for stdout to handle large base64 images (10MB)
        if self.runtime_process.stdout:
            self.runtime_process.stdout._limit = 10 * 1024 * 1024  # 10MB
        
        self.is_running = True
        
        # Start output reader task
        self.runtime_task = asyncio.create_task(self._read_runtime_output())
        
        logger.info("Plugin runtime process started", pid=self.runtime_process.pid)
    
    async def _read_runtime_output(self):
        """Read and process runtime output."""
        if not self.runtime_process or not self.runtime_process.stdout:
            return
        
        try:
            while self.is_running:
                line = await self.runtime_process.stdout.readline()
                if not line:
                    break
                
                try:
                    # Parse JSON message
                    message = json.loads(line.decode().strip())
                    await self._handle_runtime_message(message)
                except json.JSONDecodeError as e:
                    # Don't log the full line if it's too long (might contain base64)
                    line_str = line.decode().strip()
                    if len(line_str) > 500:
                        line_preview = line_str[:200] + f"... (truncated, total {len(line_str)} chars)"
                    else:
                        line_preview = line_str
                    logger.warning(f"Invalid JSON from runtime: {line_preview}")
                except Exception as e:
                    logger.error(f"Error handling runtime message: {e}", exc_info=True)
        
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Runtime output reader error: {e}", exc_info=True)
        finally:
            self.is_running = False
            if self.disconnect_callback:
                await self.disconnect_callback()
    
    async def _handle_runtime_message(self, message: Dict[str, Any]):
        """Handle message from plugin runtime.
        
        Args:
            message: Message dict with 'type' and 'data' fields
        """
        msg_type = message.get('type')
        data = message.get('data', {})
        
        if msg_type == 'log':
            # Log message from plugin
            level = data.get('level', 'info')
            text = data.get('message', '')
            plugin = data.get('plugin', 'unknown')
            
            log_func = getattr(logger, level, logger.info)
            log_func(f"[Plugin:{plugin}] {text}")
        
        elif msg_type == 'event':
            # Plugin wants to emit event
            event_name = data.get('event')
            event_data = data.get('data', {})
            await self.event_bus.emit(event_name, event_data)
        
        elif msg_type == 'heartbeat':
            # Heartbeat response
            logger.debug("Received heartbeat from runtime")
        
        elif msg_type == 'api_call':
            # Plugin wants to call OneBot API
            request_id = data.get('request_id')
            action = data.get('action')
            params = data.get('params', {})
            source_plugin = data.get('source_plugin')  # Plugin ID that initiated the call
            
            logger.info(f"Plugin API call: {action} with params {params}, request_id: {request_id}, source: {source_plugin}")
            
            # Check if this is a message-sending action that should be intercepted
            message_actions = ['send_group_msg', 'send_private_msg', 'send_msg']
            is_message_action = action in message_actions
            
            if is_message_action:
                # Run message interceptors
                allow, modified_params = await self.interceptor_registry.intercept_message(
                    action, params, source_plugin
                )
                
                if not allow:
                    logger.warning(f"Message blocked by interceptor: {action} from {source_plugin}")
                    if request_id:
                        await self._send_to_runtime({
                            'type': 'api_response',
                            'data': {
                                'request_id': request_id,
                                'success': False,
                                'error': 'Message blocked by interceptor'
                            }
                        })
                    return
                
                # Use modified params if any interceptor changed them
                if modified_params != params:
                    logger.info(f"Message modified by interceptor: {action}")
                    params = modified_params
            
            # Get OneBot adapter from app
            if self.app and hasattr(self.app, 'onebot_adapter'):
                try:
                    # Call OneBot API using generic call_api method
                    onebot = self.app.onebot_adapter
                    result = await onebot.call_api(action, params)
                    
                    logger.info(f"API call {action} succeeded: {result}")
                    
                    # Send response back to plugin
                    if request_id:
                        await self._send_to_runtime({
                            'type': 'api_response',
                            'data': {
                                'request_id': request_id,
                                'success': True,
                                'result': result
                            }
                        })
                except Exception as e:
                    logger.error(f"API call {action} failed: {e}", exc_info=True)
                    # Send error response back to plugin
                    if request_id:
                        await self._send_to_runtime({
                            'type': 'api_response',
                            'data': {
                                'request_id': request_id,
                                'success': False,
                                'error': str(e)
                            }
                        })
            else:
                logger.warning("OneBot adapter not available for API call")
                if request_id:
                    await self._send_to_runtime({
                        'type': 'api_response',
                        'data': {
                            'request_id': request_id,
                            'success': False,
                            'error': 'OneBot adapter not available'
                        }
                    })
        
        else:
            logger.warning(f"Unknown message type from runtime: {msg_type}")
    
    async def _send_to_runtime(self, message: Dict[str, Any]):
        """Send message to plugin runtime.
        
        Args:
            message: Message dict to send
        """
        if not self.runtime_process or not self.runtime_process.stdin:
            logger.error("Cannot send to runtime: process not running")
            return
        
        try:
            msg_type = message.get('type', 'unknown')
            logger.debug(f"Sending to runtime: {msg_type}")
            if msg_type == 'api_response':
                logger.debug(f"   Response data: {message.get('data', {})}")
            data = json.dumps(message) + '\n'
            self.runtime_process.stdin.write(data.encode())
            await self.runtime_process.stdin.drain()
            logger.debug(f"Sent to runtime: {msg_type}")
        except Exception as e:
            logger.error(f"Error sending to runtime: {e}", exc_info=True)
    
    async def _heartbeat_loop(self):
        """Send periodic heartbeat to runtime."""
        try:
            while self.is_running:
                await asyncio.sleep(30)  # Every 30 seconds
                await self._send_to_runtime({
                    'type': 'heartbeat',
                    'data': {'timestamp': datetime.utcnow().isoformat()}
                })
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Heartbeat loop error: {e}", exc_info=True)
    
    async def _initialize_plugins(self):
        """Initialize all enabled plugins."""
        try:
            # Get enabled plugins from database
            plugins = await self.db_manager.list_plugin_settings(enabled_only=True)
            
            logger.info(f"Found {len(plugins)} enabled plugins")
            
            # Send init command to runtime
            await self._send_to_runtime({
                'type': 'init_plugins',
                'data': {
                    'plugins': [
                        {
                            'author': p.plugin_author,
                            'name': p.plugin_name,
                            'config': p.config,
                            'priority': p.priority
                        }
                        for p in plugins
                    ]
                }
            })
            
        except Exception as e:
            logger.error(f"Failed to initialize plugins: {e}", exc_info=True)
    
    async def emit_event(self, event_name: str, data: Dict[str, Any], source: Optional[str] = None):
        """Emit event to all plugins.
        
        Args:
            event_name: Event name
            data: Event data
            source: Event source (optional)
        """
        # Run event interceptors
        allow, modified_data = await self.interceptor_registry.intercept_event(
            event_name, data, source
        )
        
        if not allow:
            logger.debug(f"Event blocked by interceptor: {event_name} from {source}")
            return
        
        # Use modified data if any interceptor changed it
        if modified_data != data:
            logger.debug(f"Event modified by interceptor: {event_name}")
            data = modified_data
        
        await self._send_to_runtime({
            'type': 'event',
            'data': {
                'event': event_name,
                'data': data
            }
        })
    
    async def install_plugin(self, author: str, name: str, source: str):
        """Install a plugin.
        
        Args:
            author: Plugin author
            name: Plugin name
            source: Installation source (path, url, etc.)
        """
        # TODO: Implement plugin installation
        logger.info(f"Installing plugin: {author}/{name} from {source}")
        pass
    
    async def uninstall_plugin(self, author: str, name: str):
        """Uninstall a plugin."""
        # TODO: Implement plugin uninstallation
        logger.info(f"Uninstalling plugin: {author}/{name}")
        pass
    
    async def reload_plugin(self, plugin_name: str) -> bool:
        """Reload a single plugin.
        
        Args:
            plugin_name: Plugin name (format: author/name or just name)
            
        Returns:
            True if reloaded successfully
        """
        logger.info(f"Reloading single plugin: {plugin_name}")
        
        try:
            # Send reload message to runtime
            await self._send_to_runtime({
                'type': 'reload_plugin',
                'data': {
                    'plugin_name': plugin_name
                }
            })
            
            # Wait a bit for the reload to complete
            await asyncio.sleep(0.5)
            
            logger.info(f"Plugin {plugin_name} reloaded successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to reload plugin {plugin_name}: {e}", exc_info=True)
            # Fallback to reload all plugins
            logger.warning(f"Falling back to reload all plugins")
            await self.reload_plugins()
            return True
    
    async def reload_plugins(self):
        """Reload all plugins from database.
        
        This will restart the plugin runtime process to pick up
        any changes to plugin enabled/disabled status.
        """
        logger.info("Reloading plugins...")
        
        try:
            # Stop current runtime
            await self.dispose()
            
            # Wait a bit for cleanup
            await asyncio.sleep(0.5)
            
            # Restart runtime (re-initialize)
            await self.initialize()
            
            logger.info("Plugins reloaded successfully")
        except Exception as e:
            logger.error(f"Failed to reload plugins: {e}", exc_info=True)
            raise
    
    async def dispose(self):
        """Cleanup runtime resources."""
        logger.info("Disposing plugin runtime...")
        self.is_running = False
        
        # Cancel tasks
        if self.heartbeat_task and not self.heartbeat_task.done():
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass
            self.heartbeat_task = None
        
        if self.runtime_task and not self.runtime_task.done():
            self.runtime_task.cancel()
            try:
                await self.runtime_task
            except asyncio.CancelledError:
                pass
            self.runtime_task = None
        
        # Terminate process
        if self.runtime_process and self.runtime_process.returncode is None:
            try:
                # Try graceful termination first
                self.runtime_process.terminate()
                try:
                    await asyncio.wait_for(self.runtime_process.wait(), timeout=3.0)
                    logger.info("Runtime process terminated gracefully")
                except asyncio.TimeoutError:
                    logger.warning("Runtime process didn't terminate, killing it...")
                    self.runtime_process.kill()
                    await self.runtime_process.wait()
                    logger.info("Runtime process killed")
            except ProcessLookupError:
                # Process already terminated
                logger.debug("Runtime process already terminated")
            except Exception as e:
                logger.error(f"Error terminating runtime process: {e}")
            finally:
                # Clear process reference
                self.runtime_process = None
        
        # Clear stdin/stdout references
        self.runtime_stdin = None
        self.runtime_stdout = None
        
        logger.info("Plugin runtime disposed")

