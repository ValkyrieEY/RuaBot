"""Plugin runtime main script.

This script runs as a separate process and loads/executes plugins.
Communication with main framework happens via stdio (JSON messages).
"""

import sys
import json
import asyncio
import importlib.util
import os
import signal
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add parent directory to path (project root)
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))


class PluginRuntime:
    """Plugin runtime process."""
    
    def __init__(self):
        self.plugins: Dict[str, Any] = {}  # author/name -> plugin instance
        self.plugin_configs: Dict[str, Dict[str, Any]] = {}  # author/name -> config
        self.running = True
        self.plugins_dir = Path("plugins")
        self.pending_requests: Dict[str, asyncio.Future] = {}  # request_id -> Future
        self.parent_pid = os.getppid()  # Store parent process ID
        self.parent_check_task: Optional[asyncio.Task] = None
    
    async def run(self):
        """Main runtime loop."""
        self.log("info", "Plugin runtime started")
        
        # Setup signal handlers for graceful shutdown
        self._setup_signal_handlers()
        
        # Start parent process monitor
        self.parent_check_task = asyncio.create_task(self._monitor_parent_process())
        
        # Start stdin reader in background
        asyncio.create_task(self._stdin_reader())
        
        # Process messages from queue
        try:
            while self.running:
                # Small sleep to yield control
                await asyncio.sleep(0.01)
        except KeyboardInterrupt:
            pass
        finally:
            # Cancel parent check task
            if self.parent_check_task and not self.parent_check_task.done():
                self.parent_check_task.cancel()
                try:
                    await self.parent_check_task
                except asyncio.CancelledError:
                    pass
            self.log("info", "Plugin runtime stopped")
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            """Handle termination signals."""
            self.log("info", f"Received signal {signum}, shutting down...")
            self.running = False
        
        # Register signal handlers (Unix only)
        if sys.platform != 'win32':
            signal.signal(signal.SIGTERM, signal_handler)
            signal.signal(signal.SIGINT, signal_handler)
    
    async def _monitor_parent_process(self):
        """Monitor parent process and exit if it's gone.
        
        This prevents orphaned plugin processes when the framework crashes.
        """
        try:
            while self.running:
                await asyncio.sleep(5)  # Check every 5 seconds
                
                # Check if parent process still exists
                try:
                    if sys.platform == 'win32':
                        # On Windows, use psutil if available
                        try:
                            import psutil
                            try:
                                parent = psutil.Process(self.parent_pid)
                                if not parent.is_running():
                                    self.log("warning", "Parent process no longer exists, shutting down...")
                                    self.running = False
                                    break
                            except (psutil.NoSuchProcess, psutil.AccessDenied):
                                self.log("warning", "Parent process no longer exists, shutting down...")
                                self.running = False
                                break
                        except ImportError:
                            # psutil not available on Windows
                            # Try alternative: check if stdin is closed (indicates parent is gone)
                            try:
                                if sys.stdin.closed:
                                    self.log("warning", "Stdin closed, parent process likely gone, shutting down...")
                                    self.running = False
                                    break
                            except Exception:
                                # If we can't check, continue monitoring
                                pass
                    else:
                        # On Unix, use os.kill with signal 0 to check if process exists
                        try:
                            os.kill(self.parent_pid, 0)
                        except OSError:
                            # Parent process doesn't exist
                            self.log("warning", "Parent process no longer exists, shutting down...")
                            self.running = False
                            break
                except Exception as e:
                    self.log("error", f"Error checking parent process: {e}")
                    # Continue monitoring even if check fails
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.log("error", f"Error in parent process monitor: {e}")
    
    async def _stdin_reader(self):
        """Continuously read from stdin in background."""
        consecutive_errors = 0
        max_consecutive_errors = 10
        
        try:
            while self.running:
                try:
                    # Read line in executor with timeout to avoid indefinite blocking
                    loop = asyncio.get_event_loop()
                    try:
                        line = await asyncio.wait_for(
                            loop.run_in_executor(None, sys.stdin.readline),
                            timeout=60.0  # 60 second timeout
                        )
                    except asyncio.TimeoutError:
                        # Timeout is OK, just check if stdin is still open
                        if sys.stdin.closed:
                            self.log("warning", "Stdin closed, stopping reader")
                            self.running = False
                            break
                        # Continue reading
                        continue
                    
                    if not line:
                        # EOF - stdin may have been closed
                        self.log("warning", "Stdin EOF, checking if closed...")
                        if sys.stdin.closed:
                            self.log("warning", "Stdin closed, stopping reader")
                            self.running = False
                            break
                        # Wait a bit before checking again
                        await asyncio.sleep(1.0)
                        continue
                    
                    # Reset error counter on successful read
                    consecutive_errors = 0
                    
                    try:
                        message = json.loads(line.strip())
                        msg_type = message.get('type', 'unknown')
                        self.log("debug", f"Received message: {msg_type}")
                        # Handle message immediately (don't await, run as task)
                        asyncio.create_task(self.handle_message(message))
                    except json.JSONDecodeError:
                        self.log("error", f"Invalid JSON: {line.strip()}")
                        consecutive_errors += 1
                        if consecutive_errors >= max_consecutive_errors:
                            self.log("error", f"Too many consecutive JSON decode errors ({consecutive_errors})")
                            break
                    except Exception as e:
                        self.log("error", f"Error in stdin reader: {e}")
                        import traceback
                        self.log("error", traceback.format_exc())
                        consecutive_errors += 1
                        if consecutive_errors >= max_consecutive_errors:
                            self.log("error", f"Too many consecutive errors ({consecutive_errors})")
                            break
                
                except Exception as e:
                    consecutive_errors += 1
                    self.log("error", f"Error reading from stdin: {e}")
                    if consecutive_errors >= max_consecutive_errors:
                        self.log("error", f"Too many consecutive read errors ({consecutive_errors}), stopping reader")
                        break
                    # Wait before retrying
                    await asyncio.sleep(0.5)
                    
        except Exception as e:
            self.log("error", f"Fatal error in stdin reader: {e}")
            import traceback
            self.log("error", traceback.format_exc())
            self.running = False
    
    async def handle_message(self, message: Dict[str, Any]):
        """Handle message from framework.
        
        Args:
            message: Message dict with 'type' and 'data' fields
        """
        msg_type = message.get('type')
        data = message.get('data', {})
        
        if msg_type == 'init_plugins':
            await self.init_plugins(data.get('plugins', []))
        elif msg_type == 'reload_plugin':
            await self.reload_plugin(data.get('plugin_name'), data.get('config'))
        elif msg_type == 'unload_plugin':
            await self.unload_plugin(data.get('plugin_name'))
        elif msg_type == 'event':
            await self.handle_event(data)
        elif msg_type == 'event_with_context':
            await self.handle_event_with_context(data)
        elif msg_type == 'heartbeat':
            self.send_message({'type': 'heartbeat', 'data': {}})
        elif msg_type == 'api_response':
            # API response from framework
            request_id = data.get('request_id')
            result = data.get('result')
            success = data.get('success', True)
            error = data.get('error')
            
            self.log("info", f"Received API response: request_id={request_id}, success={success}")
            
            if request_id in self.pending_requests:
                self.log("info", f"Resolving future for request_id={request_id}")
                future = self.pending_requests.pop(request_id)
                if not future.done():
                    if success:
                        future.set_result(result)
                        self.log("info", f"Future resolved with result")
                    else:
                        future.set_exception(Exception(error or 'API call failed'))
                        self.log("error", f"Future resolved with error: {error}")
                else:
                    self.log("warning", f"Future already done for request_id={request_id}")
            else:
                self.log("warning", f"No pending request found for request_id={request_id}")
        
        elif msg_type == 'storage_response':
            # Storage response from framework
            request_id = data.get('request_id')
            success = data.get('success', False)
            value = data.get('value')  # base64 encoded for get_binary
            keys = data.get('keys')  # for list_binary_keys
            error = data.get('error')
            
            self.log("debug", f"Received storage response: request_id={request_id}, success={success}")
            
            if request_id in self.pending_requests:
                future = self.pending_requests.pop(request_id)
                if not future.done():
                    if success:
                        # Return appropriate result based on action
                        result = {}
                        if value is not None:
                            result['value'] = value
                        if keys is not None:
                            result['keys'] = keys
                        future.set_result(result)
                    else:
                        future.set_result({'success': False, 'error': error})
                else:
                    self.log("warning", f"Future already done for request_id={request_id}")
            else:
                self.log("warning", f"No pending request found for request_id={request_id}")
        
        elif msg_type == 'reload_plugin_response':
            # Response from framework for reload_plugin_request
            request_id = data.get('request_id')
            success = data.get('success', False)
            error = data.get('error')
            
            self.log("debug", f"Received reload_plugin response: request_id={request_id}, success={success}")
            
            if request_id in self.pending_requests:
                future = self.pending_requests.pop(request_id)
                if not future.done():
                    future.set_result({'success': success, 'error': error})
                else:
                    self.log("warning", f"Future already done for request_id={request_id}")
            else:
                self.log("warning", f"No pending request found for request_id={request_id}")
        
        elif msg_type == 'config_response':
            # Response from framework for config_request
            request_id = data.get('request_id')
            success = data.get('success', False)
            error = data.get('error')
            
            self.log("debug", f"Received config response: request_id={request_id}, success={success}")
            
            if request_id in self.pending_requests:
                future = self.pending_requests.pop(request_id)
                if not future.done():
                    future.set_result({'success': success, 'error': error})
                else:
                    self.log("warning", f"Future already done for request_id={request_id}")
            else:
                self.log("warning", f"No pending request found for request_id={request_id}")
        
        elif msg_type == 'intercept_message':
            # Framework wants to run interceptor
            request_id = data.get('request_id')
            plugin_id = data.get('plugin_id')
            action = data.get('action')
            params = data.get('params', {})
            source_plugin = data.get('source_plugin')
            
            # Get interceptor from runtime
            if hasattr(self, '_interceptors') and plugin_id in self._interceptors:
                interceptor = self._interceptors[plugin_id]
                try:
                    # Run interceptor
                    result = await interceptor.intercept_message(action, params, source_plugin)
                    
                    # Send response
                    self.send_message({
                        'type': 'intercept_message_response',
                        'data': {
                            'request_id': request_id,
                            'allow': result.allow,
                            'modified_data': result.modified_data,
                            'block_reason': result.block_reason
                        }
                    })
                except Exception as e:
                    self.log("error", f"Interceptor error: {e}")
                    # On error, allow the message
                    self.send_message({
                        'type': 'intercept_message_response',
                        'data': {
                            'request_id': request_id,
                            'allow': True
                        }
                    })
            else:
                # No interceptor found, allow the message
                self.send_message({
                    'type': 'intercept_message_response',
                    'data': {
                        'request_id': request_id,
                        'allow': True
                    }
                })
        else:
            self.log("warning", f"Unknown message type: {msg_type}")
    
    async def init_plugins(self, plugins: List[Dict[str, Any]]):
        """Initialize plugins.
        
        Args:
            plugins: List of plugin configs
        """
        self.log("info", f"Initializing {len(plugins)} plugins")
        
        for plugin_config in plugins:
            author = plugin_config.get('author')
            name = plugin_config.get('name')
            plugin_id = f"{author}/{name}"
            
            try:
                # Find plugin directory
                plugin_dir = self.plugins_dir / name
                if not plugin_dir.exists():
                    self.log("error", f"Plugin directory not found: {plugin_dir}")
                    continue
                
                # Read plugin.json
                plugin_json = plugin_dir / "plugin.json"
                if not plugin_json.exists():
                    self.log("error", f"plugin.json not found: {plugin_json}")
                    continue
                
                with open(plugin_json, 'r', encoding='utf-8') as f:
                    plugin_metadata = json.load(f)
                
                # Get entry point
                entry = plugin_metadata.get('entry', 'main.py')
                plugin_file = plugin_dir / entry
                
                if not plugin_file.exists():
                    self.log("error", f"Plugin entry file not found: {plugin_file}")
                    continue
                
                # Load plugin module
                spec = importlib.util.spec_from_file_location(
                    f"plugin_{name}", 
                    plugin_file
                )
                if not spec or not spec.loader:
                    self.log("error", f"Failed to load plugin module: {plugin_file}")
                    continue
                
                module = importlib.util.module_from_spec(spec)
                sys.modules[f"plugin_{name}"] = module
                spec.loader.exec_module(module)
                
                # Create plugin API wrapper
                plugin_api = PluginAPI(self, plugin_id)
                
                # Get plugin config - merge default with database config
                default_config = plugin_metadata.get('default_config', {})
                db_config = plugin_config.get('config', {}) or {}
                config = {**default_config, **db_config}  # Database config overrides default
                
                # Get priority: database > plugin.json > default (100)
                priority_from_json = plugin_metadata.get('priority')
                priority_from_db = plugin_config.get('priority', 100)
                # Database priority takes precedence over plugin.json
                final_priority = priority_from_db if priority_from_db != 100 or priority_from_json is None else priority_from_json
                config['priority'] = final_priority
                
                # Create plugin instance
                if hasattr(module, 'create_plugin'):
                    plugin_instance = await module.create_plugin(plugin_api, config)
                elif hasattr(module, f'{name.title().replace("_", "")}Plugin'):
                    plugin_class = getattr(module, f'{name.title().replace("_", "")}Plugin')
                    plugin_instance = plugin_class(plugin_api, config)
                    if hasattr(plugin_instance, 'on_load'):
                        await plugin_instance.on_load()
                else:
                    self.log("error", f"Plugin {plugin_id} has no create_plugin function or plugin class")
                    continue
                
                # Check if plugin already exists (prevent duplicate loading)
                if plugin_id in self.plugins:
                    self.log("warning", f"Plugin {plugin_id} already loaded! Unloading old instance first.")
                    old_instance = self.plugins[plugin_id]
                    if hasattr(old_instance, 'on_unload'):
                        try:
                            await old_instance.on_unload()
                        except Exception as e:
                            self.log("error", f"Error unloading old plugin instance: {e}")
                
                self.plugins[plugin_id] = plugin_instance
                self.plugin_configs[plugin_id] = config
                self.log("info", f"Loaded plugin: {plugin_id} (total plugins: {len(self.plugins)})")
                
            except Exception as e:
                self.log("error", f"Failed to load plugin {plugin_id}: {e}")
                import traceback
                self.log("error", traceback.format_exc())
    
    async def unload_plugin(self, plugin_name: str):
        """Unload a single plugin without reloading.
        
        Args:
            plugin_name: Plugin name (format: author/name or just name)
        """
        self.log("info", f"Unloading plugin: {plugin_name}")
        
        try:
            # Parse plugin name
            if '/' in plugin_name:
                plugin_id = plugin_name
            else:
                # Try to find plugin by name
                plugin_id = None
                for pid in self.plugins.keys():
                    if pid.endswith(f'/{plugin_name}') or pid == plugin_name:
                        plugin_id = pid
                        break
                
                if not plugin_id:
                    self.log("warning", f"Plugin {plugin_name} not found in loaded plugins")
                    return
            
            # Unload plugin
            if plugin_id in self.plugins:
                plugin_instance = self.plugins[plugin_id]
                if hasattr(plugin_instance, 'on_unload'):
                    try:
                        await plugin_instance.on_unload()
                    except Exception as e:
                        self.log("error", f"Error in plugin on_unload: {e}")
                
                # Unregister interceptors for this plugin
                if hasattr(self, '_interceptors') and plugin_id in self._interceptors:
                    self.log("info", f"Unregistering interceptors for plugin: {plugin_id}")
                    del self._interceptors[plugin_id]
                    
                    # Send unregistration request to main framework
                    self.send_message({
                        'type': 'unregister_interceptor',
                        'data': {
                            'plugin_id': plugin_id
                        }
                    })
                
                del self.plugins[plugin_id]
                if plugin_id in self.plugin_configs:
                    del self.plugin_configs[plugin_id]
                
                # Remove module from sys.modules
                module_name = f"plugin_{plugin_id.replace('/', '_')}"
                if module_name in sys.modules:
                    del sys.modules[module_name]
                
                self.log("info", f"Plugin {plugin_id} unloaded successfully")
            else:
                self.log("warning", f"Plugin {plugin_id} not found in loaded plugins")
        except Exception as e:
            self.log("error", f"Failed to unload plugin {plugin_name}: {e}")
            import traceback
            self.log("error", traceback.format_exc())
    
    async def reload_plugin(self, plugin_name: str, config_override: Optional[Dict[str, Any]] = None):
        """Reload a single plugin.
        
        Args:
            plugin_name: Plugin name (format: author/name or just name)
            config_override: Optional config to use instead of reading from database
        """
        self.log("info", f"Reloading plugin: {plugin_name}")
        
        try:
            # Parse plugin name
            if '/' in plugin_name:
                author, name = plugin_name.split('/', 1)
                plugin_id = plugin_name
            else:
                # Try to find plugin by name
                plugin_id = None
                for pid in self.plugins.keys():
                    if pid.endswith(f'/{plugin_name}') or pid == plugin_name:
                        plugin_id = pid
                        break
                
                # If not found in loaded plugins, try to load it fresh
                if not plugin_id:
                    self.log("info", f"Plugin {plugin_name} not found in loaded plugins, attempting fresh load")
                    author = 'XQNEXT'  # Default author
                    name = plugin_name
                    plugin_id = f"{author}/{name}"
            
            # Unload plugin first
            if plugin_id in self.plugins:
                plugin_instance = self.plugins[plugin_id]
                if hasattr(plugin_instance, 'on_unload'):
                    try:
                        await plugin_instance.on_unload()
                    except Exception as e:
                        self.log("error", f"Error in plugin on_unload: {e}")
                
                del self.plugins[plugin_id]
                if plugin_id in self.plugin_configs:
                    del self.plugin_configs[plugin_id]
                
                # Remove module from sys.modules
                module_name = f"plugin_{plugin_id.replace('/', '_')}"
                if module_name in sys.modules:
                    del sys.modules[module_name]
            
            # Check if plugin is enabled before reloading
            if '/' in plugin_id:
                author, name = plugin_id.split('/', 1)
            else:
                author = 'XQNEXT'  # Default author
                name = plugin_id
            
            # Check plugin enabled status from database
            is_enabled = True
            try:
                from src.core.database import get_database_manager
                db_manager = get_database_manager()
                setting = await db_manager.get_plugin_setting(author, name)
                if setting:
                    is_enabled = setting.enabled
                else:
                    # If not in database, check system.json
                    plugin_path = self.plugins_dir / name
                    system_json = plugin_path / "system.json"
                    if system_json.exists():
                        import json
                        with open(system_json, 'r', encoding='utf-8') as f:
                            system_data = json.load(f)
                            is_enabled = system_data.get('enabled', False)
            except Exception as e:
                self.log("warning", f"Could not check plugin enabled status: {e}, assuming enabled")
            
            # Only reload if plugin is enabled
            if not is_enabled:
                self.log("info", f"Plugin {plugin_id} is disabled, not reloading")
                return
            
            # Get config: use override if provided, otherwise read from database
            plugin_config_data = {}
            if config_override is not None:
                # 使用传递过来的配置（即使为空字典）
                plugin_config_data = config_override if config_override else {}
                self.log("info", f"Using config override for {plugin_id}: {plugin_config_data}")
            else:
                # config_override是None，说明connector没有传递配置
                # runtime进程无法直接访问数据库（相对导入问题），所以使用默认配置
                self.log("warning", f"Config override is None for {plugin_id}, using default config from plugin.json")
                # Fallback to default config from plugin.json
                plugin_path = self.plugins_dir / name
                plugin_json = plugin_path / "plugin.json"
                if plugin_json.exists():
                    import json
                    with open(plugin_json, 'r', encoding='utf-8') as f:
                        plugin_metadata = json.load(f)
                        plugin_config_data = plugin_metadata.get('default_config', {})
            
            # Get plugin config
            plugin_config = {
                'author': author,
                'name': name,
                'config': plugin_config_data
            }
            
            # Load plugin
            await self.init_plugins([plugin_config])
            
            self.log("info", f"Plugin {plugin_id} reloaded successfully with config: {plugin_config_data}")
        except Exception as e:
            self.log("error", f"Failed to reload plugin {plugin_name}: {e}")
            import traceback
            self.log("error", traceback.format_exc())
    
    async def handle_event(self, data: Dict[str, Any]):
        """Handle event from framework (deprecated - use handle_event_with_context instead).
        
        This method is kept for compatibility but should not be used.
        All events should go through handle_event_with_context.
        
        Args:
            data: Event data with 'event' and 'data' fields
        """
        # Convert to event context format and use the new handler
        from src.core.event_context import EventContext
        import uuid
        
        event_name = data.get('event')
        event_data = data.get('data', {})
        
        ctx = EventContext(
            event_name=event_name,
            event_data=event_data,
            source="framework"
        )
        
        # Use event context handler
        await self.handle_event_with_context({
            'request_id': 'legacy_' + str(uuid.uuid4()),
            'event_context': ctx.to_dict(),
            'bound_plugins': None
        })
    
    async def handle_event_with_context(self, data: Dict[str, Any]):
        """Handle event with context from framework (similar to LangBot).
        
        Plugins can modify the event context and prevent default behavior.
        
        Args:
            data: Event data with 'request_id', 'event_context', and 'bound_plugins'
        """
        try:
            # Use absolute import since we're running as a standalone script
            from src.core.event_context import EventContext
            
            request_id = data.get('request_id')
            event_context_dict = data.get('event_context', {})
            bound_plugins = data.get('bound_plugins')
            
            self.log("debug", f"handle_event_with_context called: request_id={request_id}, has_context={bool(event_context_dict)}, bound_plugins={bound_plugins}")
            
            # Create EventContext from dict
            try:
                event_context = EventContext.from_dict(event_context_dict)
            except Exception as e:
                self.log("error", f"Failed to parse event context: {e}")
                self.send_message({
                    'type': 'event_with_context_response',
                    'data': {
                        'request_id': request_id,
                        'success': False,
                        'error': str(e)
                    }
                })
                return
        
            # Get enabled plugins with priority
            enabled_plugins = []
            for plugin_id, plugin_instance in self.plugins.items():
                # Filter by bound_plugins if specified
                if bound_plugins is not None and plugin_id not in bound_plugins:
                    continue
                
                # Get plugin priority from config or default to 100
                plugin_config = self.plugin_configs.get(plugin_id, {})
                priority = plugin_config.get('priority', 100)
                
                enabled_plugins.append({
                    'plugin_id': plugin_id,
                    'instance': plugin_instance,
                    'priority': priority
                })
            
            self.log("debug", f"Processing event {event_context.event_name} with {len(enabled_plugins)} enabled plugins")
            
            # Sort by priority (lower priority = earlier execution)
            enabled_plugins.sort(key=lambda x: x['priority'])
            
            # Process event through plugins in priority order
            modified_context = event_context
            prevented = False
            
            if not enabled_plugins:
                self.log("debug", f"No enabled plugins to process event {event_context.event_name}")
            
            for plugin_info in enabled_plugins:
                plugin_id = plugin_info['plugin_id']
                plugin_instance = plugin_info['instance']
                
                try:
                    # Check if plugin has on_event_context handler
                    if hasattr(plugin_instance, 'on_event_context'):
                        self.log("debug", f"Calling on_event_context for plugin {plugin_id}")
                        
                        # For message.received events, use timeout to prevent blocking
                        # Plugins should return quickly and handle API calls asynchronously
                        if modified_context.event_name == 'message.received':
                            try:
                                # Use shorter timeout for message.received to prevent blocking
                                result = await asyncio.wait_for(
                                    plugin_instance.on_event_context(modified_context),
                                    timeout=2.0  # 2 seconds timeout
                                )
                            except asyncio.TimeoutError:
                                self.log("warning", f"Plugin {plugin_id} on_event_context timeout for {modified_context.event_name}, continuing...")
                                # Continue with next plugin, don't block
                                result = None
                        else:
                            # For other events, wait normally
                            result = await plugin_instance.on_event_context(modified_context)
                        
                        if result is not None:
                            # Plugin returned modified context
                            if isinstance(result, EventContext):
                                modified_context = result
                            elif isinstance(result, dict):
                                # Update event data
                                modified_context.event_data.update(result)
                                modified_context.mark_modified()
                        
                        # Check if plugin prevented default
                        if modified_context.is_prevented_default():
                            prevented = True
                            self.log("info", f"Plugin {plugin_id} prevented default behavior for event {modified_context.event_name}")
                            break
                    
                    # Only on_event_context is supported, no fallback
                    else:
                        self.log("debug", f"Plugin {plugin_id} does not implement on_event_context, skipping")
                        
                except Exception as e:
                    self.log("error", f"Error in plugin {plugin_id} handling event context: {e}")
                    import traceback
                    self.log("error", traceback.format_exc())
            
            # Send response back to framework
            self.log("debug", f"Sending event_with_context_response for {event_context.event_name}, prevented={prevented}, modified={modified_context.is_modified()}")
            self.send_message({
                'type': 'event_with_context_response',
                'data': {
                    'request_id': request_id,
                    'success': not prevented,
                    'event_context': modified_context.to_dict() if not prevented else None
                }
            })
        except Exception as e:
            self.log("error", f"Error in handle_event_with_context: {e}")
            import traceback
            self.log("error", traceback.format_exc())
            # Send error response - ensure we always send a response even on error
            request_id = data.get('request_id') if 'data' in locals() else None
            if request_id:
                try:
                    self.send_message({
                        'type': 'event_with_context_response',
                        'data': {
                            'request_id': request_id,
                            'success': False,
                            'error': str(e)
                        }
                    })
                except Exception as send_error:
                    self.log("error", f"Failed to send error response: {send_error}")
            else:
                self.log("warning", "No request_id available to send error response")
    
    def send_message(self, message: Dict[str, Any]):
        """Send message to framework via stdout.
        
        Args:
            message: Message dict to send
        """
        try:
            print(json.dumps(message), flush=True)
        except Exception as e:
            sys.stderr.write(f"Error sending message: {e}\n")
    
    def log(self, level: str, message: str, plugin: str = "runtime"):
        """Send log message to framework.
        
        Args:
            level: Log level (debug, info, warning, error)
            message: Log message
            plugin: Plugin name (default: runtime)
        """
        self.send_message({
            'type': 'log',
            'data': {
                'level': level,
                'message': message,
                'plugin': plugin
            }
        })


class PluginAPI:
    """API for plugins to interact with framework."""
    
    def __init__(self, runtime: PluginRuntime, plugin_id: str):
        self.runtime = runtime
        self.plugin_id = plugin_id
    
    def log(self, level: str, message: str, **kwargs):
        """Log a message."""
        msg = message
        if kwargs:
            msg += f" {kwargs}"
        self.runtime.log(level, msg, plugin=self.plugin_id)
    
    async def call_api(self, action: str, **params) -> Dict[str, Any]:
        """Call any OneBot API and wait for response.
        
        Args:
            action: API action name (e.g., 'send_like', 'get_group_list')
            **params: API parameters
        
        Returns:
            API response data (the actual result from OneBot)
        """
        import uuid
        
        request_id = str(uuid.uuid4())
        future = asyncio.get_event_loop().create_future()
        self.runtime.pending_requests[request_id] = future
        
        self.log("debug", f"Calling API: {action} with params: {params}, request_id: {request_id}")
        
        # Send API request to framework
        self.runtime.send_message({
            'type': 'api_call',
            'data': {
                'request_id': request_id,
                'action': action,
                'params': params,
                'source_plugin': self.plugin_id  # Pass plugin ID for interceptor tracking
            }
        })
        
        try:
            # Wait for response (with timeout)
            # Use longer timeout for message-sending actions (they may be slower)
            # Other actions use shorter timeout
            if action in ['send_group_msg', 'send_private_msg', 'send_msg', 
                         'send_group_forward_msg', 'send_private_forward_msg', 'send_forward_msg']:
                timeout = 60.0  # 60 seconds for message sending (may be slow)
            else:
                timeout = 30.0  # 30 seconds for other actions
            
            result = await asyncio.wait_for(future, timeout=timeout)
            self.log("debug", f"API {action} result: {result}")
            return result
        except asyncio.TimeoutError:
            self.runtime.pending_requests.pop(request_id, None)
            self.log("error", f"API {action} timeout after {timeout}s")
            raise Exception(f"API call timeout: {action}")
        except Exception as e:
            self.runtime.pending_requests.pop(request_id, None)
            self.log("error", f"API {action} error: {e}")
            raise
    
    async def send_private_msg(self, user_id: int, message: str, auto_escape: bool = False) -> Dict[str, Any]:
        """Send private message.
        
        Returns:
            {'message_id': int} on success
        """
        return await self.call_api('send_private_msg', user_id=user_id, message=message, auto_escape=auto_escape)
    
    async def send_group_msg(self, group_id: int, message: str, auto_escape: bool = False) -> Dict[str, Any]:
        """Send group message.
        
        Returns:
            {'message_id': int} on success
        """
        return await self.call_api('send_group_msg', group_id=group_id, message=message, auto_escape=auto_escape)
    
    async def send_like(self, user_id: int, times: int = 1) -> Dict[str, Any]:
        """Send like to user.
        
        Returns:
            {'success': True} on success, {'success': False, 'error': '...'} on failure
        """
        try:
            result = await self.call_api('send_like', user_id=user_id, times=times)
            # send_like API returns empty dict {} on success (OneBot spec)
            # Normalize to always include 'success' field for plugin compatibility
            if result is None or result == {}:
                return {'success': True}
            # If result already has 'success' field, return as-is
            if 'success' in result:
                return result
            # Otherwise, assume success if no error
            return {'success': True, 'data': result}
        except Exception as e:
            # API call failed, return error format
            return {'success': False, 'error': str(e)}
    
    async def get_group_list(self) -> List[Dict[str, Any]]:
        """Get group list.
        
        Returns:
            List of group info dicts
        """
        return await self.call_api('get_group_list')
    
    async def get_friend_list(self) -> List[Dict[str, Any]]:
        """Get friend list.
        
        Returns:
            List of friend info dicts
        """
        return await self.call_api('get_friend_list')
    
    async def get_group_info(self, group_id: int, no_cache: bool = False) -> Dict[str, Any]:
        """Get group info.
        
        Returns:
            Group info dict
        """
        return await self.call_api('get_group_info', group_id=group_id, no_cache=no_cache)
    
    async def get_group_member_list(self, group_id: int) -> List[Dict[str, Any]]:
        """Get group member list.
        
        Returns:
            List of member info dicts
        """
        return await self.call_api('get_group_member_list', group_id=group_id)
    
    async def get_login_info(self) -> Dict[str, Any]:
        """Get bot login info.
        
        Returns:
            {'user_id': int, 'nickname': str}
        """
        return await self.call_api('get_login_info')
    
    async def get_status(self) -> Dict[str, Any]:
        """Get bot status.
        
        Returns:
            Status info dict
        """
        return await self.call_api('get_status')
    
    async def set_group_ban(self, group_id: int, user_id: int, duration: int = 30 * 60) -> Dict[str, Any]:
        """Ban group member.
        
        Returns:
            {} on success (empty dict)
        """
        result = await self.call_api('set_group_ban', group_id=group_id, user_id=user_id, duration=duration)
        return {'success': True} if result is None else result
    
    async def get_config(self, key: str = None) -> Any:
        """Get plugin config."""
        config = self.runtime.plugin_configs.get(self.plugin_id, {})
        if key:
            return config.get(key)
        return config
    
    async def set_config(self, key: str, value: Any) -> bool:
        """Set plugin config with persistence.
        
        Args:
            key: Config key
            value: Config value
            
        Returns:
            True if successful
        """
        import uuid
        
        # Update in-memory config first
        if self.plugin_id not in self.runtime.plugin_configs:
            self.runtime.plugin_configs[self.plugin_id] = {}
        self.runtime.plugin_configs[self.plugin_id][key] = value
        
        # Persist to database via message to main framework
        request_id = str(uuid.uuid4())
        future = asyncio.get_event_loop().create_future()
        self.runtime.pending_requests[request_id] = future
        
        # Parse plugin ID to get author/name
        if '/' in self.plugin_id:
            author, name = self.plugin_id.split('/', 1)
        else:
            author = 'XQNEXT'  # Default author
            name = self.plugin_id
        
        # Get current config
        current_config = self.runtime.plugin_configs.get(self.plugin_id, {}).copy()
        current_config[key] = value
        
        # Send config update request to framework
        self.runtime.send_message({
            'type': 'config_request',
            'data': {
                'request_id': request_id,
                'action': 'set_config',
                'author': author,
                'name': name,
                'config': current_config
            }
        })
        
        try:
            # Wait for response (with timeout)
            result = await asyncio.wait_for(future, timeout=10.0)
            if isinstance(result, dict):
                return result.get('success', False)
            return False
        except asyncio.TimeoutError:
            self.runtime.pending_requests.pop(request_id, None)
            self.log("error", f"Config set_config timeout for key: {key}")
            return False
        except Exception as e:
            self.runtime.pending_requests.pop(request_id, None)
            self.log("error", f"Config set_config error for key {key}: {e}")
            return False
    
    async def get_storage(self, key: str) -> Optional[bytes]:
        """Get binary storage.
        
        Args:
            key: Storage key
            
        Returns:
            Binary data or None if not found
        """
        import uuid
        import base64
        
        request_id = str(uuid.uuid4())
        future = asyncio.get_event_loop().create_future()
        self.runtime.pending_requests[request_id] = future
        
        # Send storage request to framework
        self.runtime.send_message({
            'type': 'storage_request',
            'data': {
                'request_id': request_id,
                'action': 'get_binary',
                'plugin_id': self.plugin_id,
                'key': key
            }
        })
        
        try:
            # Wait for response (with timeout)
            result = await asyncio.wait_for(future, timeout=10.0)
            # result is a dict with 'value' (base64) or 'success'/'error'
            if isinstance(result, dict):
                if result.get('success') and 'value' in result:
                    # Decode base64
                    value_b64 = result.get('value', '')
                    if value_b64:
                        return base64.b64decode(value_b64)
            return None
        except asyncio.TimeoutError:
            self.runtime.pending_requests.pop(request_id, None)
            self.log("error", f"Storage get_binary timeout for key: {key}")
            return None
        except Exception as e:
            self.runtime.pending_requests.pop(request_id, None)
            self.log("error", f"Storage get_binary error for key {key}: {e}")
            return None
    
    async def set_storage(self, key: str, value: bytes) -> bool:
        """Set binary storage.
        
        Args:
            key: Storage key
            value: Binary data (max 10MB recommended)
            
        Returns:
            True if successful
        """
        import uuid
        import base64
        
        request_id = str(uuid.uuid4())
        future = asyncio.get_event_loop().create_future()
        self.runtime.pending_requests[request_id] = future
        
        # Encode binary as base64 for JSON transport
        value_b64 = base64.b64encode(value).decode()
        
        # Send storage request to framework
        self.runtime.send_message({
            'type': 'storage_request',
            'data': {
                'request_id': request_id,
                'action': 'set_binary',
                'plugin_id': self.plugin_id,
                'key': key,
                'value': value_b64
            }
        })
        
        try:
            # Wait for response (with timeout)
            result = await asyncio.wait_for(future, timeout=10.0)
            return result.get('success', False)
        except asyncio.TimeoutError:
            self.runtime.pending_requests.pop(request_id, None)
            self.log("error", f"Storage set_binary timeout for key: {key}")
            return False
        except Exception as e:
            self.runtime.pending_requests.pop(request_id, None)
            self.log("error", f"Storage set_binary error for key {key}: {e}")
            return False
    
    async def delete_storage(self, key: str) -> bool:
        """Delete binary storage.
        
        Args:
            key: Storage key
            
        Returns:
            True if successful
        """
        import uuid
        
        request_id = str(uuid.uuid4())
        future = asyncio.get_event_loop().create_future()
        self.runtime.pending_requests[request_id] = future
        
        # Send storage request to framework
        self.runtime.send_message({
            'type': 'storage_request',
            'data': {
                'request_id': request_id,
                'action': 'delete_binary',
                'plugin_id': self.plugin_id,
                'key': key
            }
        })
        
        try:
            # Wait for response (with timeout)
            result = await asyncio.wait_for(future, timeout=10.0)
            return result.get('success', False)
        except asyncio.TimeoutError:
            self.runtime.pending_requests.pop(request_id, None)
            self.log("error", f"Storage delete_binary timeout for key: {key}")
            return False
        except Exception as e:
            self.runtime.pending_requests.pop(request_id, None)
            self.log("error", f"Storage delete_binary error for key {key}: {e}")
            return False
    
    async def list_storage_keys(self) -> List[str]:
        """List all storage keys for this plugin.
        
        Returns:
            List of keys
        """
        import uuid
        
        request_id = str(uuid.uuid4())
        future = asyncio.get_event_loop().create_future()
        self.runtime.pending_requests[request_id] = future
        
        # Send storage request to framework
        self.runtime.send_message({
            'type': 'storage_request',
            'data': {
                'request_id': request_id,
                'action': 'list_binary_keys',
                'plugin_id': self.plugin_id
            }
        })
        
        try:
            # Wait for response (with timeout)
            result = await asyncio.wait_for(future, timeout=10.0)
            if result.get('success'):
                return result.get('keys', [])
            return []
        except asyncio.TimeoutError:
            self.runtime.pending_requests.pop(request_id, None)
            self.log("error", "Storage list_binary_keys timeout")
            return []
        except Exception as e:
            self.runtime.pending_requests.pop(request_id, None)
            self.log("error", f"Storage list_binary_keys error: {e}")
            return []
    
    def register_message_interceptor(self, interceptor):
        """Register a message interceptor.
        
        Sends a request to the main framework to register the interceptor.
        The main framework will create a proxy interceptor that communicates
        with the plugin runtime via messages.
        
        Args:
            interceptor: MessageInterceptor instance
        """
        # Store interceptor in runtime for later use
        if not hasattr(self.runtime, '_interceptors'):
            self.runtime._interceptors = {}
        self.runtime._interceptors[self.plugin_id] = interceptor
        
        # Send registration request to main framework
        self.runtime.send_message({
            'type': 'register_interceptor',
            'data': {
                'plugin_id': self.plugin_id,
                'priority': getattr(interceptor, 'priority', 100)
            }
        })
        self.log("info", f"已发送拦截器注册请求到主框架: {self.plugin_id}")
    
    def unregister_message_interceptor(self):
        """Unregister all message interceptors for this plugin."""
        # Remove interceptor from runtime
        if hasattr(self.runtime, '_interceptors'):
            self.runtime._interceptors.pop(self.plugin_id, None)
        
        # Send unregistration request to main framework
        self.runtime.send_message({
            'type': 'unregister_interceptor',
            'data': {
                'plugin_id': self.plugin_id
            }
        })
        self.log("info", f"已发送拦截器取消注册请求到主框架: {self.plugin_id}")


async def main():
    """Main entry point."""
    runtime = PluginRuntime()
    await runtime.run()


if __name__ == '__main__':
    asyncio.run(main())
