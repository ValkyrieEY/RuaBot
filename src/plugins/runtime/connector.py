"""Plugin runtime connector (inspired by LangBot).

Manages communication with plugin runtime process via stdio.
"""

import asyncio
import json
import sys
import os
from pathlib import Path
from typing import Optional, Dict, Any, Callable, Coroutine, List, Tuple
import asyncio
from datetime import datetime

from ...core.logger import get_logger
from ...core.event_bus import EventBus
from ...core.database import DatabaseManager
from ..interceptor import InterceptorRegistry, MessageInterceptor, InterceptorResult

logger = get_logger(__name__)


async def install_plugin_dependencies(plugin_path: Path, plugin_metadata: Dict[str, Any]) -> bool:
    """Install plugin dependencies automatically.
    
    Supports two methods:
    1. From plugin.json dependencies field
    2. From requirements.txt file
    
    Args:
        plugin_path: Plugin directory path
        plugin_metadata: Plugin metadata from plugin.json
        
    Returns:
        True if installation succeeded or no dependencies, False on error
    """
    import subprocess
    import sys
    
    dependencies_to_install = []
    
    # Method 1: Check plugin.json dependencies field
    if 'dependencies' in plugin_metadata:
        deps = plugin_metadata['dependencies']
        if isinstance(deps, list):
            for dep in deps:
                if isinstance(dep, dict):
                    # Format: {"name": "package", "version": ">=1.0.0"}
                    dep_name = dep.get('name', '')
                    dep_version = dep.get('version', '')
                    if dep_name:
                        if dep_version:
                            dependencies_to_install.append(f"{dep_name}{dep_version}")
                        else:
                            dependencies_to_install.append(dep_name)
                elif isinstance(dep, str):
                    # Format: "package>=1.0.0" or just "package"
                    dependencies_to_install.append(dep)
    
    # Method 2: Check requirements.txt
    requirements_file = plugin_path / "requirements.txt"
    if requirements_file.exists():
        try:
            with open(requirements_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # Skip comments and empty lines
                    if line and not line.startswith('#'):
                        dependencies_to_install.append(line)
        except Exception as e:
            logger.warning(f"Failed to read requirements.txt: {e}")
    
    # If no dependencies found, return success
    if not dependencies_to_install:
        logger.info(f"No dependencies found for plugin at {plugin_path}")
        return True
    
    # Install dependencies
    logger.info(f"Installing {len(dependencies_to_install)} dependencies for plugin: {plugin_path.name}")
    
    try:
        # Use pip to install dependencies
        # Try pip3 first, then pip
        pip_cmd = 'pip3' if sys.platform != 'win32' else 'pip'
        
        # Check if pip is available
        try:
            result = subprocess.run(
                [pip_cmd, '--version'],
                capture_output=True,
                timeout=5
            )
            if result.returncode != 0:
                # Try 'pip' if 'pip3' failed
                pip_cmd = 'pip'
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pip_cmd = 'pip'
        
        # Install each dependency (run in thread pool to avoid blocking)
        failed_deps = []
        loop = asyncio.get_event_loop()
        
        def install_dep(dep: str) -> Tuple[str, bool, str]:
            """Install a single dependency synchronously."""
            try:
                logger.info(f"Installing dependency: {dep}")
                result = subprocess.run(
                    [sys.executable, '-m', 'pip', 'install', dep],
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minutes timeout
                )
                
                if result.returncode == 0:
                    logger.info(f"Successfully installed: {dep}")
                    return (dep, True, "")
                else:
                    error_msg = result.stderr or result.stdout
                    logger.warning(f"Failed to install {dep}: {error_msg}")
                    return (dep, False, error_msg)
            except subprocess.TimeoutExpired:
                logger.error(f"Timeout installing {dep}")
                return (dep, False, "Timeout")
            except Exception as e:
                logger.error(f"Error installing {dep}: {e}")
                return (dep, False, str(e))
        
        # Install dependencies sequentially (to avoid conflicts)
        for dep in dependencies_to_install:
            dep_name, success, error = await loop.run_in_executor(None, install_dep, dep)
            if not success:
                failed_deps.append(dep_name)
        
        if failed_deps:
            logger.warning(f"Some dependencies failed to install: {failed_deps}")
            # Don't fail the entire installation, just warn
            return True
        else:
            logger.info(f"All dependencies installed successfully for plugin: {plugin_path.name}")
            return True
            
    except Exception as e:
        logger.error(f"Error installing plugin dependencies: {e}", exc_info=True)
        # Don't fail the entire installation, just warn
        return True


class ProxyMessageInterceptor(MessageInterceptor):
    """代理拦截器 - 通过消息传递调用插件运行时的拦截逻辑"""
    
    def __init__(self, plugin_id: str, connector, priority: int = 100):
        """初始化代理拦截器
        
        Args:
            plugin_id: 插件ID
            connector: PluginRuntimeConnector实例
            priority: 优先级
        """
        super().__init__(plugin_id, priority)
        self.connector = connector
        self.plugin_id = plugin_id
    
    async def intercept_message(
        self,
        action: str,
        params: Dict[str, Any],
        source_plugin: Optional[str] = None
    ) -> InterceptorResult:
        """拦截消息 - 通过消息传递到插件运行时执行拦截逻辑"""
        import uuid
        
        # 发送拦截请求到插件运行时
        request_id = str(uuid.uuid4())
        future = asyncio.get_event_loop().create_future()
        
        # 临时存储future（需要在connector中实现）
        if not hasattr(self.connector, '_interceptor_futures'):
            self.connector._interceptor_futures = {}
        self.connector._interceptor_futures[request_id] = future
        
        # 发送拦截请求
        await self.connector._send_to_runtime({
            'type': 'intercept_message',
            'data': {
                'request_id': request_id,
                'plugin_id': self.plugin_id,
                'action': action,
                'params': params,
                'source_plugin': source_plugin
            }
        })
        
        try:
            # 等待响应（超时1秒）
            result = await asyncio.wait_for(future, timeout=1.0)
            return result
        except asyncio.TimeoutError:
            # 超时则放行
            logger.warning(f"拦截器响应超时: {self.plugin_id}, 放行消息")
            return InterceptorResult(allow=True)
        except Exception as e:
            logger.error(f"拦截器执行错误: {self.plugin_id}, {e}")
            return InterceptorResult(allow=True)
        finally:
            self.connector._interceptor_futures.pop(request_id, None)


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
        
        # Interceptor futures for async communication
        self._interceptor_futures: Dict[str, asyncio.Future] = {}
        
        # Pending requests for event context communication
        self.pending_requests: Dict[str, asyncio.Future] = {}
        
        # Cleanup task for expired requests
        self._cleanup_task: Optional[asyncio.Task] = None
    
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
            
            # Start cleanup task for expired requests
            self._cleanup_task = asyncio.create_task(self._cleanup_expired_requests())
            
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
        if self.runtime_process:
            # Check if process is still running
            is_running = False
            if hasattr(self.runtime_process, 'returncode'):
                is_running = self.runtime_process.returncode is None
            elif hasattr(self.runtime_process, 'poll'):
                is_running = self.runtime_process.poll() is None
            
            if is_running:
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
                    except Exception as e:
                        logger.error(f"Failed to kill old runtime process: {e}")
                except Exception as e:
                    logger.error(f"Error terminating old runtime process: {e}")
        
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
        # Windows + Python 3.13 compatibility: ensure ProactorEventLoop policy is set
        if sys.platform == 'win32' and sys.version_info >= (3, 13):
            try:
                current_policy = asyncio.get_event_loop_policy()
                if not isinstance(current_policy, asyncio.WindowsProactorEventLoopPolicy):
                    # Try to set ProactorEventLoop policy
                    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
                    logger.info("Set ProactorEventLoop policy for subprocess support")
            except Exception as e:
                logger.warning(f"Failed to set ProactorEventLoop policy: {e}")
        
        try:
            self.runtime_process = await asyncio.create_subprocess_exec(
                sys.executable,
                str(self.runtime_script),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except NotImplementedError as e:
            # Fallback to subprocess.Popen for Windows + Python 3.13
            if sys.platform == 'win32' and sys.version_info >= (3, 13):
                logger.warning("asyncio.create_subprocess_exec not supported, using subprocess.Popen fallback")
                try:
                    import subprocess
                    # Use subprocess.Popen as fallback
                    popen_process = subprocess.Popen(
                        [sys.executable, str(self.runtime_script)],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        bufsize=0,  # Unbuffered
                    )
                    # Wrap Popen in a simple async-compatible interface
                    # Create a minimal wrapper that mimics asyncio.subprocess.Process
                    class PopenWrapper:
                        def __init__(self, popen_proc):
                            self._popen = popen_proc
                            self.stdin = popen_proc.stdin
                            self.stdout = popen_proc.stdout
                            self.stderr = popen_proc.stderr
                            self.pid = popen_proc.pid
                        
                        def poll(self):
                            return self._popen.poll()
                        
                        def wait(self):
                            return self._popen.wait()
                        
                        def terminate(self):
                            self._popen.terminate()
                        
                        def kill(self):
                            self._popen.kill()
                    
                    self.runtime_process = PopenWrapper(popen_process)
                    logger.info(f"Plugin runtime started with Popen fallback, pid={self.runtime_process.pid}")
                except Exception as fallback_error:
                    error_msg = (
                        f"Failed to create subprocess with both asyncio and Popen fallback: {e}. "
                        f"Fallback error: {fallback_error}"
                    )
                    logger.error(error_msg)
                    raise RuntimeError(error_msg) from e
            else:
                error_msg = (
                    f"Failed to create subprocess: {e}. "
                    "On Windows with Python 3.13+, ProactorEventLoop policy is required."
                )
                logger.error(error_msg)
                raise RuntimeError(error_msg) from e
        
        # Set larger limit for stdout to handle large base64 images (10MB)
        if self.runtime_process.stdout and hasattr(self.runtime_process.stdout, '_limit'):
            try:
                self.runtime_process.stdout._limit = 10 * 1024 * 1024  # 10MB
            except AttributeError:
                # Popen fallback doesn't have _limit attribute, that's OK
                pass
        
        self.is_running = True
        
        # Start output reader task
        self.runtime_task = asyncio.create_task(self._read_runtime_output())
        
        logger.info("Plugin runtime process started", pid=self.runtime_process.pid)
    
    async def _read_runtime_output(self):
        """Read and process runtime output."""
        if not self.runtime_process or not self.runtime_process.stdout:
            return
        
        # Check if this is asyncio subprocess or Popen fallback
        is_async_process = hasattr(self.runtime_process.stdout, 'readline') and asyncio.iscoroutinefunction(self.runtime_process.stdout.readline)
        
        consecutive_errors = 0
        max_consecutive_errors = 10
        should_call_disconnect = False
        
        try:
            while self.is_running:
                try:
                    if is_async_process:
                        # Asyncio subprocess - add timeout to prevent indefinite blocking
                        try:
                            line = await asyncio.wait_for(
                                self.runtime_process.stdout.readline(),
                                timeout=60.0  # 60 second timeout
                            )
                        except asyncio.TimeoutError:
                            # Timeout is OK, just check if process is still alive
                            if self.runtime_process and hasattr(self.runtime_process, 'poll'):
                                if self.runtime_process.poll() is not None:
                                    logger.warning("Runtime process terminated")
                                    break
                            # Continue reading
                            continue
                    else:
                        # Popen fallback - use sync readline in executor with timeout
                        loop = asyncio.get_event_loop()
                        try:
                            line = await asyncio.wait_for(
                                loop.run_in_executor(None, self.runtime_process.stdout.readline),
                                timeout=60.0  # 60 second timeout
                            )
                        except asyncio.TimeoutError:
                            # Timeout is OK, check if process is still alive
                            if self.runtime_process and hasattr(self.runtime_process, 'poll'):
                                if self.runtime_process.poll() is not None:
                                    logger.warning("Runtime process terminated")
                                    break
                            # Continue reading
                            continue
                    
                    if not line:
                        # EOF - process may have closed stdout
                        logger.warning("Runtime stdout closed (EOF)")
                        # Check if process is still alive
                        if self.runtime_process and hasattr(self.runtime_process, 'poll'):
                            if self.runtime_process.poll() is not None:
                                logger.warning("Runtime process terminated")
                                break
                        # Wait a bit before checking again (process might restart)
                        await asyncio.sleep(1.0)
                        continue
                    
                    # Reset error counter on successful read
                    consecutive_errors = 0
                    
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
                        consecutive_errors += 1
                        if consecutive_errors >= max_consecutive_errors:
                            logger.error(f"Too many consecutive JSON decode errors ({consecutive_errors}), stopping reader")
                            break
                    except Exception as e:
                        logger.error(f"Error handling runtime message: {e}", exc_info=True)
                        consecutive_errors += 1
                        if consecutive_errors >= max_consecutive_errors:
                            logger.error(f"Too many consecutive errors ({consecutive_errors}), stopping reader")
                            break
                
                except Exception as e:
                    consecutive_errors += 1
                    logger.error(f"Error reading from runtime stdout: {e}", exc_info=True)
                    if consecutive_errors >= max_consecutive_errors:
                        logger.error(f"Too many consecutive read errors ({consecutive_errors}), stopping reader")
                        should_call_disconnect = True
                        break
                    # Wait before retrying
                    await asyncio.sleep(0.5)
        
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Runtime output reader fatal error: {e}", exc_info=True)
        finally:
            # Mark as not running, but don't immediately call disconnect_callback
            # Let the heartbeat and other mechanisms handle reconnection
            self.is_running = False
            logger.warning("Runtime output reader stopped. Plugin runtime may be disconnected.")
            
            # Only call disconnect callback if we have one and it's a real disconnection
            # (not just a temporary read error)
            if self.disconnect_callback and should_call_disconnect:
                try:
                    await self.disconnect_callback()
                except Exception as callback_error:
                    logger.error(f"Error in disconnect callback: {callback_error}", exc_info=True)
    
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
        
        elif msg_type == 'register_interceptor':
            # Plugin wants to register an interceptor
            plugin_id = data.get('plugin_id')
            priority = data.get('priority', 100)
            
            logger.info(f"Registering interceptor for plugin: {plugin_id}, priority: {priority}")
            
            # Create proxy interceptor
            proxy_interceptor = ProxyMessageInterceptor(plugin_id, self, priority=priority)
            self.interceptor_registry.register_message_interceptor(proxy_interceptor)
            logger.info(f"✅ 拦截器已注册: {plugin_id}")
        
        elif msg_type == 'unregister_interceptor':
            # Plugin wants to unregister an interceptor
            plugin_id = data.get('plugin_id')
            
            logger.info(f"Unregistering interceptor for plugin: {plugin_id}")
            self.interceptor_registry.unregister_message_interceptor(plugin_id)
            logger.info(f"✅ 拦截器已取消注册: {plugin_id}")
        
        elif msg_type == 'intercept_message_response':
            # Response from plugin runtime for intercept_message request
            request_id = data.get('request_id')
            allow = data.get('allow', True)
            modified_data = data.get('modified_data')
            block_reason = data.get('block_reason')
            
            if request_id in self._interceptor_futures:
                future = self._interceptor_futures.pop(request_id)
                if not future.done():
                    result = InterceptorResult(
                        allow=allow,
                        modified_data=modified_data,
                        block_reason=block_reason
                    )
                    future.set_result(result)
        
        elif msg_type == 'event_with_context_response':
            # Response from plugin runtime for event_with_context request
            request_id = data.get('request_id')
            success = data.get('success', True)
            event_context_dict = data.get('event_context')
            error = data.get('error')
            
            logger.debug(f"Received event_with_context_response: request_id={request_id}, success={success}, has_context={event_context_dict is not None}")
            
            if request_id in self.pending_requests:
                future = self.pending_requests.pop(request_id)
                if not future.done():
                    result = {
                        'success': success,
                        'event_context': event_context_dict,
                        'error': error
                    }
                    try:
                        future.set_result(result)
                        logger.debug(f"Set result for request {request_id}")
                    except Exception as e:
                        # Future may have been cancelled or already set
                        logger.debug(f"Failed to set result for request {request_id}: {e}")
                else:
                    logger.debug(f"Future already done for request_id={request_id} (likely timeout, but response arrived)")
            else:
                # Response arrived but future was already cleaned up (likely due to timeout)
                logger.debug(f"No pending request found for request_id={request_id} (likely timeout, response arrived late)")
        
        elif msg_type == 'storage_request':
            # Plugin wants to access storage
            request_id = data.get('request_id')
            action = data.get('action')  # 'get_binary', 'set_binary', 'delete_binary', 'list_binary_keys'
            plugin_id = data.get('plugin_id')
            
            logger.debug(f"Storage request: {action} from plugin {plugin_id}, request_id: {request_id}")
            
            # Use handler to process storage request
            from .handler import RuntimeConnectionHandler
            handler = RuntimeConnectionHandler(self.db_manager)
            
            # Prepare handler data
            handler_data = {
                'owner': plugin_id,
                'key': data.get('key'),
                'value': data.get('value')  # base64 encoded for set_binary
            }
            
            try:
                # Call appropriate handler method
                if action == 'get_binary':
                    result = await handler._handle_get_binary(handler_data)
                elif action == 'set_binary':
                    result = await handler._handle_set_binary(handler_data)
                elif action == 'delete_binary':
                    result = await handler._handle_delete_binary(handler_data)
                elif action == 'list_binary_keys':
                    result = await handler._handle_list_binary_keys(handler_data)
                else:
                    result = {'success': False, 'error': f'Unknown storage action: {action}'}
                
                # Send response back to plugin
                await self._send_to_runtime({
                    'type': 'storage_response',
                    'data': {
                        'request_id': request_id,
                        **result
                    }
                })
            except Exception as e:
                logger.error(f"Error handling storage request: {e}", exc_info=True)
                await self._send_to_runtime({
                    'type': 'storage_response',
                    'data': {
                        'request_id': request_id,
                        'success': False,
                        'error': str(e)
                    }
                })
        
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
                    # Call OneBot API with source_plugin info to skip message.before_send processing
                    onebot = self.app.onebot_adapter
                    result = await onebot.call_api(action, params, source_plugin=source_plugin)
                    
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
        
        elif msg_type == 'reload_plugin_request':
            # Plugin wants to reload itself (from within plugin)
            request_id = data.get('request_id')
            plugin_name = data.get('plugin_name')
            
            logger.info(f"Plugin {plugin_name} requested reload from within plugin")
            
            try:
                # Use connector's reload_plugin method which gets config from database
                success = await self.reload_plugin(plugin_name)
                
                # Send response back to plugin
                await self._send_to_runtime({
                    'type': 'reload_plugin_response',
                    'data': {
                        'request_id': request_id,
                        'success': success
                    }
                })
            except Exception as e:
                logger.error(f"Error handling reload_plugin_request: {e}", exc_info=True)
                await self._send_to_runtime({
                    'type': 'reload_plugin_response',
                    'data': {
                        'request_id': request_id,
                        'success': False,
                        'error': str(e)
                    }
                })
        
        elif msg_type == 'config_request':
            # Plugin wants to update config
            request_id = data.get('request_id')
            action = data.get('action')  # 'set_config'
            author = data.get('author')
            name = data.get('name')
            config = data.get('config', {})
            
            logger.debug(f"Config request: {action} for plugin {author}/{name}, request_id: {request_id}")
            
            # Use handler to process config request
            from .handler import RuntimeConnectionHandler
            handler = RuntimeConnectionHandler(self.db_manager)
            
            try:
                # Call handler method
                if action == 'set_config':
                    result = await handler._handle_set_config({
                        'author': author,
                        'name': name,
                        'config': config
                    })
                else:
                    result = {'success': False, 'error': f'Unknown config action: {action}'}
                
                # Send response back to plugin
                await self._send_to_runtime({
                    'type': 'config_response',
                    'data': {
                        'request_id': request_id,
                        **result
                    }
                })
            except Exception as e:
                logger.error(f"Error handling config request: {e}", exc_info=True)
                await self._send_to_runtime({
                    'type': 'config_response',
                    'data': {
                        'request_id': request_id,
                        'success': False,
                        'error': str(e)
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
            
            # Check if this is asyncio subprocess or Popen fallback
            stdin = self.runtime_process.stdin
            if hasattr(stdin, 'drain'):
                # Asyncio subprocess - async IO
                stdin.write(data.encode())
                await stdin.drain()
            else:
                # Popen fallback - sync IO, use executor
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, stdin.write, data.encode())
                await loop.run_in_executor(None, stdin.flush)
            
            logger.debug(f"Sent to runtime: {msg_type}")
        except Exception as e:
            logger.error(f"Error sending to runtime: {e}", exc_info=True)
    
    async def _heartbeat_loop(self):
        """Send periodic heartbeat to runtime.
        
        Inspired by LangBot: heartbeat failure doesn't immediately disconnect,
        just logs the error. This prevents false disconnections due to temporary issues.
        """
        consecutive_failures = 0
        max_consecutive_failures = 5  # Allow 5 consecutive failures before considering disconnection
        
        try:
            while self.is_running:
                await asyncio.sleep(30)  # Every 30 seconds
                
                try:
                    await self._send_to_runtime({
                        'type': 'heartbeat',
                        'data': {'timestamp': datetime.utcnow().isoformat()}
                    })
                    consecutive_failures = 0  # Reset on success
                    logger.debug("Heartbeat sent successfully")
                except Exception as e:
                    consecutive_failures += 1
                    logger.debug(f"Heartbeat failed ({consecutive_failures}/{max_consecutive_failures}): {e}")
                    
                    # Only log warning after multiple failures
                    if consecutive_failures >= max_consecutive_failures:
                        logger.warning(
                            f"Heartbeat failed {consecutive_failures} times consecutively. "
                            f"Plugin runtime may be disconnected."
                        )
                        # Don't immediately disconnect - let the read loop detect actual disconnection
                        
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Heartbeat loop fatal error: {e}", exc_info=True)
    
    async def _cleanup_expired_requests(self):
        """Periodically cleanup expired pending requests."""
        try:
            while self.is_running:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                expired = []
                for request_id, future in list(self.pending_requests.items()):
                    if future.done() or future.cancelled():
                        expired.append(request_id)
                
                for request_id in expired:
                    self.pending_requests.pop(request_id, None)
                    logger.debug(f"Cleaned up expired request: {request_id}")
                
                # Also cleanup interceptor futures
                expired_interceptors = []
                for request_id, future in list(self._interceptor_futures.items()):
                    if future.done() or future.cancelled():
                        expired_interceptors.append(request_id)
                
                for request_id in expired_interceptors:
                    self._interceptor_futures.pop(request_id, None)
                    logger.debug(f"Cleaned up expired interceptor future: {request_id}")
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Cleanup task error: {e}", exc_info=True)
    
    async def _initialize_plugins(self):
        """Initialize all enabled plugins."""
        try:
            # Get enabled plugins from database
            plugins = await self.db_manager.list_plugin_settings(enabled_only=True)
            
            logger.info(f"Found {len(plugins)} enabled plugins")
            
            # Send init command to runtime
            # Priority: database > plugin.json > default (100)
            plugin_list = []
            for p in plugins:
                # Try to get priority from plugin.json
                priority_from_json = None
                try:
                    from pathlib import Path
                    from ...core.config import get_config
                    config = get_config()
                    plugin_dir = Path(config.plugin_dir)
                    if not plugin_dir.is_absolute():
                        from pathlib import Path as P
                        project_root = P(__file__).parent.parent.parent.parent
                        plugin_dir = (project_root / config.plugin_dir).resolve()
                    
                    plugin_path = plugin_dir / p.plugin_name
                    plugin_json = plugin_path / "plugin.json"
                    if plugin_json.exists():
                        import json
                        with open(plugin_json, 'r', encoding='utf-8') as f:
                            plugin_metadata = json.load(f)
                            priority_from_json = plugin_metadata.get('priority')
                except Exception:
                    pass
                
                # Priority: database > plugin.json > default
                final_priority = p.priority
                if p.priority == 100 and priority_from_json is not None:
                    # Database has default, use plugin.json if available
                    final_priority = priority_from_json
                
                plugin_list.append({
                    'author': p.plugin_author,
                    'name': p.plugin_name,
                    'config': p.config,
                    'priority': final_priority
                })
            
            await self._send_to_runtime({
                'type': 'init_plugins',
                'data': {
                    'plugins': plugin_list
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
    
    async def emit_event_with_context(
        self,
        event_context: 'EventContext',
        bound_plugins: Optional[List[str]] = None
    ) -> Optional['EventContext']:
        """Emit event with context to plugins (similar to LangBot).
        
        Plugins can modify the event context and prevent default behavior.
        
        Args:
            event_context: EventContext instance
            bound_plugins: List of plugin IDs to include (None = all enabled plugins)
            
        Returns:
            Modified EventContext or None if event was blocked
        """
        from ...core.event_context import EventContext
        
        if not self.is_running:
            return event_context
        
        # Send event context to runtime for plugin processing
        import uuid
        request_id = str(uuid.uuid4())
        future = asyncio.get_event_loop().create_future()
        self.pending_requests[request_id] = future
        
        await self._send_to_runtime({
            'type': 'event_with_context',
            'data': {
                'request_id': request_id,
                'event_context': event_context.to_dict(),
                'bound_plugins': bound_plugins
            }
        })
        
        try:
            # Wait for response (with timeout)
            # Inspired by LangBot: use longer timeout (180s) for event processing
            # to allow plugins to perform complex operations (API calls, LLM invocations, etc.)
            # Use shorter timeout for message.before_send to avoid blocking API calls
            if event_context.event_name == 'message.before_send':
                timeout = 5.0  # Short timeout for before_send to avoid blocking
            else:
                timeout = 180.0  # Longer timeout for received events (same as LangBot)
            result = await asyncio.wait_for(future, timeout=timeout)
            
            if result.get('success', True):  # Default to True if not specified
                # Get modified context from result
                modified_ctx_dict = result.get('event_context')
                if modified_ctx_dict:
                    logger.debug(f"Returning modified context for {event_context.event_name}")
                    return EventContext.from_dict(modified_ctx_dict)
                # No modification, return original context
                logger.debug(f"Returning original context for {event_context.event_name} (no modifications)")
                return event_context
            else:
                # Event was blocked
                logger.debug(f"Event blocked by plugin: {event_context.event_name}")
                return None
                
        except asyncio.TimeoutError:
            # Remove future from pending_requests to prevent memory leak
            # If response arrives later, it will be ignored (future already timed out)
            self.pending_requests.pop(request_id, None)
            logger.warning(f"Event context timeout: {event_context.event_name} (request_id={request_id})")
            # Return original context to allow processing to continue
            return event_context
        except Exception as e:
            self.pending_requests.pop(request_id, None)
            logger.error(f"Error emitting event with context: {e}", exc_info=True)
            return event_context
    
    async def _get_enabled_plugins_with_priority(
        self,
        bound_plugins: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Get enabled plugins with priority information."""
        try:
            from ...core.database import get_database_manager
            from ...core.models.plugin import PluginSetting
            
            db_manager = get_database_manager()
            if not db_manager:
                return []
            
            # Get all plugin settings
            async with db_manager.session() as session:
                from sqlalchemy import select
                result = await session.execute(select(PluginSetting))
                settings = result.scalars().all()
                
                enabled_plugins = []
                for setting in settings:
                    if not setting.enabled:
                        continue
                    
                    plugin_id = f"{setting.plugin_author}/{setting.plugin_name}"
                    
                    # Filter by bound_plugins if specified
                    if bound_plugins is not None and plugin_id not in bound_plugins:
                        continue
                    
                    enabled_plugins.append({
                        'plugin_id': plugin_id,
                        'author': setting.plugin_author,
                        'name': setting.plugin_name,
                        'priority': getattr(setting, 'priority', 100),  # Default priority: 100
                    })
                
                return enabled_plugins
        except Exception as e:
            logger.error(f"Error getting enabled plugins: {e}", exc_info=True)
            return []
    
    async def install_plugin(self, author: str, name: str, source: str):
        """Install a plugin.
        
        Args:
            author: Plugin author
            name: Plugin name
            source: Installation source (path, url, etc.)
            
        Returns:
            True if successful
        """
        logger.info(f"Installing plugin: {author}/{name} from {source}")
        
        try:
            from ...core.config import get_config
            config = get_config()
            plugins_dir = Path(config.plugin_dir)
            plugin_path = plugins_dir / name
            
            # 如果插件目录已存在，先检查
            if plugin_path.exists():
                logger.warning(f"Plugin {name} already exists at {plugin_path}")
                return False
            
            # 根据source类型处理
            if source.startswith('http://') or source.startswith('https://'):
                # URL下载（GitHub等）
                logger.info(f"Downloading plugin from URL: {source}")
                
                try:
                    import aiohttp
                    import tempfile
                    import zipfile
                    
                    # 创建临时目录
                    temp_dir = Path(tempfile.gettempdir()) / f"plugin_install_{name}_{datetime.now().timestamp()}"
                    temp_dir.mkdir(exist_ok=True)
                    temp_zip = temp_dir / f"{name}.zip"
                    
                    # 处理GitHub URL
                    if 'github.com' in source:
                        # 如果是GitHub仓库URL，转换为下载链接
                        if source.endswith('.zip'):
                            download_url = source
                        elif '/archive/' in source:
                            download_url = source
                        else:
                            # 假设是仓库URL，添加/archive/refs/heads/main.zip
                            if source.endswith('/'):
                                source = source[:-1]
                            if not source.endswith('.zip'):
                                # 尝试获取main分支的zip
                                download_url = f"{source}/archive/refs/heads/main.zip"
                            else:
                                download_url = source
                    else:
                        download_url = source
                    
                    # 下载文件
                    async with aiohttp.ClientSession() as session:
                        async with session.get(download_url) as response:
                            if response.status != 200:
                                logger.error(f"Failed to download plugin: HTTP {response.status}")
                                return False
                            
                            # 保存到临时文件
                            with open(temp_zip, 'wb') as f:
                                async for chunk in response.content.iter_chunked(8192):
                                    f.write(chunk)
                    
                    # 解压ZIP文件
                    with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
                        # 获取解压后的根目录名
                        zip_names = zip_ref.namelist()
                        if zip_names:
                            # 通常GitHub zip的第一层是 仓库名-分支名/
                            root_dir = zip_names[0].split('/')[0]
                            # 解压到临时目录
                            extract_dir = temp_dir / "extracted"
                            zip_ref.extractall(extract_dir)
                            
                            # 找到实际的插件目录（可能有一层包装）
                            extracted_root = extract_dir / root_dir
                            if extracted_root.exists():
                                # 检查是否直接就是插件目录（有plugin.json）
                                if (extracted_root / "plugin.json").exists():
                                    source_path = extracted_root
                                else:
                                    # 查找包含plugin.json的子目录
                                    plugin_dirs = [d for d in extracted_root.iterdir() if d.is_dir() and (d / "plugin.json").exists()]
                                    if plugin_dirs:
                                        source_path = plugin_dirs[0]
                                    else:
                                        logger.error("Could not find plugin.json in downloaded archive")
                                        import shutil
                                        shutil.rmtree(temp_dir, ignore_errors=True)
                                        return False
                            else:
                                logger.error("Failed to extract plugin archive")
                                import shutil
                                shutil.rmtree(temp_dir, ignore_errors=True)
                                return False
                            
                            # 复制到插件目录
                            import shutil
                            shutil.copytree(source_path, plugin_path)
                            logger.info(f"Downloaded and installed plugin from {source} to {plugin_path}")
                            
                            # 清理临时文件
                            shutil.rmtree(temp_dir, ignore_errors=True)
                        else:
                            logger.error("Downloaded archive is empty")
                            import shutil
                            shutil.rmtree(temp_dir, ignore_errors=True)
                            return False
                        
                except Exception as e:
                    logger.error(f"Failed to download plugin from URL: {e}", exc_info=True)
                    # 清理临时文件
                    try:
                        import shutil
                        if 'temp_dir' in locals() and temp_dir.exists():
                            shutil.rmtree(temp_dir, ignore_errors=True)
                    except:
                        pass
                    return False
            elif Path(source).exists():
                # 本地路径
                source_path = Path(source)
                if source_path.is_dir():
                    # 复制目录
                    import shutil
                    shutil.copytree(source_path, plugin_path)
                    logger.info(f"Copied plugin from {source_path} to {plugin_path}")
                elif source_path.is_file() and source_path.suffix == '.zip':
                    # 解压ZIP文件
                    import zipfile
                    with zipfile.ZipFile(source_path, 'r') as zip_ref:
                        zip_ref.extractall(plugin_path)
                    logger.info(f"Extracted plugin from {source_path} to {plugin_path}")
                else:
                    logger.error(f"Unsupported source type: {source}")
                    return False
            else:
                logger.error(f"Source not found: {source}")
                return False
            
            # 验证插件（检查plugin.json）
            plugin_json = plugin_path / "plugin.json"
            if not plugin_json.exists():
                logger.error(f"Plugin {name} missing plugin.json, installation failed")
                # 清理
                import shutil
                if plugin_path.exists():
                    shutil.rmtree(plugin_path)
                return False
            
            # 读取plugin.json获取元数据
            import json
            with open(plugin_json, 'r', encoding='utf-8') as f:
                plugin_metadata = json.load(f)
            
            # 自动安装依赖
            logger.info(f"Checking dependencies for plugin: {author}/{name}")
            await install_plugin_dependencies(plugin_path, plugin_metadata)
            
            # 在数据库中注册插件
            if self.db_manager:
                
                # 检查插件设置是否已存在
                existing_setting = await self.db_manager.get_plugin_setting(author, name)
                
                default_config = plugin_metadata.get('default_config', {})
                install_info = {
                    'source': source,
                    'version': plugin_metadata.get('version', '1.0.0'),
                    'installed_at': datetime.now().isoformat()
                }
                
                if existing_setting:
                    # 更新现有设置
                    success = await self.db_manager.update_plugin_setting(
                        author, name,
                        enabled=True,
                        config=default_config,
                        install_source='local' if Path(source).exists() else 'url',
                        install_info=install_info
                    )
                else:
                    # 创建新设置
                    try:
                        await self.db_manager.create_plugin_setting(
                            author, name,
                            enabled=True,
                            config=default_config,
                            install_source='local' if Path(source).exists() else 'url',
                            install_info=install_info
                        )
                        success = True
                    except Exception as e:
                        logger.error(f"Failed to create plugin setting: {e}")
                        success = False
                
                if success:
                    logger.info(f"Plugin {author}/{name} installed successfully")
                    # 重新加载插件
                    await self.reload_plugin(f"{author}/{name}")
                    return True
                else:
                    logger.error(f"Failed to register plugin in database")
                    return False
            else:
                logger.warning("Database manager not available, plugin installed but not registered")
                return True
                
        except Exception as e:
            logger.error(f"Failed to install plugin {author}/{name}: {e}", exc_info=True)
            # 清理失败的安装
            try:
                if plugin_path.exists():
                    import shutil
                    shutil.rmtree(plugin_path)
            except:
                pass
            return False
    
    async def uninstall_plugin(self, author: str, name: str):
        """Uninstall a plugin completely.
        
        This will:
        1. Unload plugin from runtime
        2. Delete plugin directory
        3. Delete all plugin storage data from database
        4. Delete plugin settings from database
        
        Args:
            author: Plugin author
            name: Plugin name
            
        Returns:
            True if successful
        """
        logger.info(f"Uninstalling plugin: {author}/{name}")
        
        plugin_id = f"{author}/{name}"
        
        try:
            # 1. 先卸载插件（从runtime中移除）
            await self.unload_plugin(plugin_id)
            
            # 2. 删除插件目录
            from ...core.config import get_config
            config = get_config()
            plugins_dir = Path(config.plugin_dir)
            plugin_path = plugins_dir / name
            
            if plugin_path.exists():
                import shutil
                try:
                    shutil.rmtree(plugin_path)
                    logger.info(f"Deleted plugin directory: {plugin_path}")
                except Exception as e:
                    logger.warning(f"Failed to delete plugin directory: {e}")
            
            # 3. 删除数据库中的所有插件数据
            if self.db_manager:
                # 3.1 删除插件的所有存储数据
                try:
                    storage_keys = await self.db_manager.list_binary_keys('plugin', plugin_id)
                    deleted_count = 0
                    for key in storage_keys:
                        try:
                            await self.db_manager.delete_binary('plugin', plugin_id, key)
                            deleted_count += 1
                            logger.debug(f"Deleted storage key: {key} for plugin {plugin_id}")
                        except Exception as e:
                            logger.warning(f"Failed to delete storage key {key}: {e}")
                    if storage_keys:
                        logger.info(f"Deleted {deleted_count}/{len(storage_keys)} storage keys for plugin {plugin_id}")
                except Exception as e:
                    logger.warning(f"Failed to delete plugin storage data: {e}")
                
                # 3.2 删除插件设置（完全删除，不只是禁用）
                try:
                    success = await self.db_manager.delete_plugin_setting(author, name)
                    if success:
                        logger.info(f"Deleted plugin settings for {author}/{name}")
                    else:
                        logger.warning(f"Plugin settings not found in database: {author}/{name}")
                except Exception as e:
                    logger.error(f"Failed to delete plugin settings: {e}")
                    return False
                
                logger.info(f"Plugin {author}/{name} uninstalled successfully (all data deleted)")
                return True
            else:
                logger.warning("Database manager not available, only deleted plugin directory")
                return True
                
        except Exception as e:
            logger.error(f"Failed to uninstall plugin {author}/{name}: {e}", exc_info=True)
            return False
    
    async def unload_plugin(self, plugin_name: str) -> bool:
        """Unload a single plugin without reloading.
        
        Args:
            plugin_name: Plugin name (format: author/name or just name)
            
        Returns:
            True if unloaded successfully
        """
        logger.info(f"Unloading plugin: {plugin_name}")
        
        try:
            # Send unload message to runtime
            await self._send_to_runtime({
                'type': 'unload_plugin',
                'data': {
                    'plugin_name': plugin_name
                }
            })
            
            # Wait a bit for the unload to complete
            await asyncio.sleep(0.3)
            
            logger.info(f"Plugin {plugin_name} unloaded successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to unload plugin {plugin_name}: {e}", exc_info=True)
            return False
    
    async def reload_plugin(self, plugin_name: str) -> bool:
        """Reload a single plugin.
        
        Args:
            plugin_name: Plugin name (format: author/name or just name)
            
        Returns:
            True if reloaded successfully
        """
        logger.info(f"Reloading single plugin: {plugin_name}")
        
        try:
            # Get fresh config from database to pass to runtime
            # This avoids SQLite cross-process caching issues
            plugin_config = {}  # 初始化为空字典，而不是None
            
            if self.db_manager:
                # Parse plugin name to get author/name
                if '/' in plugin_name:
                    author, name = plugin_name.split('/', 1)
                else:
                    # Try to get author from plugin.json
                    from ...core.config import get_config
                    config = get_config()
                    plugin_path = Path(config.plugin_dir) / plugin_name
                    plugin_json = plugin_path / "plugin.json"
                    if plugin_json.exists():
                        import json
                        # Use thread pool for synchronous file IO
                        thread_pool = getattr(self.app, 'plugin_thread_pool', None)
                        if thread_pool:
                            def read_plugin_json():
                                with open(plugin_json, 'r', encoding='utf-8') as f:
                                    return json.load(f)
                            metadata = await thread_pool.run_in_executor(read_plugin_json)
                        else:
                            # Fallback to sync operation if thread pool not available
                            with open(plugin_json, 'r', encoding='utf-8') as f:
                                metadata = json.load(f)
                        author = metadata.get('author', 'Unknown')
                        name = plugin_name
                    else:
                        author = 'Unknown'
                        name = plugin_name
                
                # Get latest config from database
                setting = await self.db_manager.get_plugin_setting(author, name)
                if setting and setting.config:
                    plugin_config = setting.config
                    logger.debug(f"Loaded fresh config from database for {plugin_name}: {plugin_config}")
                else:
                    # 如果数据库中没有配置，使用默认配置
                    plugin_config = {}
                    logger.debug(f"No config in database for {plugin_name}, using empty config")
            
            # 确保plugin_config不是None
            if plugin_config is None:
                plugin_config = {}
            
            # Send reload message to runtime with fresh config
            await self._send_to_runtime({
                'type': 'reload_plugin',
                'data': {
                    'plugin_name': plugin_name,
                    'config': plugin_config  # Pass config directly to avoid cross-process cache issues
                }
            })
            
            # Wait a bit for the reload to complete
            await asyncio.sleep(0.5)
            
            logger.info(f"Plugin {plugin_name} reloaded successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to reload plugin {plugin_name}: {e}", exc_info=True)
            return False
    
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
        
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
        
        if self.runtime_task and not self.runtime_task.done():
            self.runtime_task.cancel()
            try:
                await self.runtime_task
            except asyncio.CancelledError:
                pass
            self.runtime_task = None
        
        # Terminate process
        if self.runtime_process:
            try:
                # Check if process is still running
                is_running = False
                if hasattr(self.runtime_process, 'returncode'):
                    is_running = self.runtime_process.returncode is None
                elif hasattr(self.runtime_process, 'poll'):
                    is_running = self.runtime_process.poll() is None
                
                if is_running:
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
    
    async def cleanup_orphan_processes(self) -> int:
        """Manually cleanup orphaned plugin runtime processes.
        
        Returns:
            Number of processes cleaned up
        """
        logger.info("Manually cleaning up orphaned plugin runtime processes...")
        cleaned_count = 0
        
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
                        logger.info(f"Found orphaned plugin runtime process: PID {proc.info['pid']}, terminating...")
                        try:
                            proc_obj = psutil.Process(proc.info['pid'])
                            proc_obj.terminate()
                            proc_obj.wait(timeout=2)
                            logger.info(f"Orphaned process {proc.info['pid']} terminated")
                            cleaned_count += 1
                        except (psutil.NoSuchProcess, psutil.TimeoutExpired):
                            try:
                                proc_obj.kill()
                                logger.info(f"Orphaned process {proc.info['pid']} killed")
                                cleaned_count += 1
                            except psutil.NoSuchProcess:
                                pass
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except ImportError:
            logger.warning("psutil not available, cannot cleanup orphaned processes")
        except Exception as e:
            logger.error(f"Error cleaning up orphaned processes: {e}", exc_info=True)
        
        logger.info(f"Cleaned up {cleaned_count} orphaned plugin runtime process(es)")
        return cleaned_count

