"""Plugin runtime main script.

This script runs as a separate process and loads/executes plugins.
Communication with main framework happens via stdio (JSON messages).
"""

import sys
import json
import asyncio
import importlib.util
from pathlib import Path
from typing import Dict, Any, List

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


class PluginRuntime:
    """Plugin runtime process."""
    
    def __init__(self):
        self.plugins: Dict[str, Any] = {}  # author/name -> plugin instance
        self.plugin_configs: Dict[str, Dict[str, Any]] = {}  # author/name -> config
        self.running = True
        self.plugins_dir = Path("plugins")
        self.pending_requests: Dict[str, asyncio.Future] = {}  # request_id -> Future
    
    async def run(self):
        """Main runtime loop."""
        self.log("info", "Plugin runtime started")
        
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
            self.log("info", "Plugin runtime stopped")
    
    async def _stdin_reader(self):
        """Continuously read from stdin in background."""
        try:
            while self.running:
                # Read line in executor to avoid blocking event loop
                line = await asyncio.get_event_loop().run_in_executor(
                    None, sys.stdin.readline
                )
                
                if not line:
                    self.running = False
                    break
                
                try:
                    message = json.loads(line.strip())
                    msg_type = message.get('type', 'unknown')
                    self.log("debug", f"Received message: {msg_type}")
                    # Handle message immediately (don't await, run as task)
                    asyncio.create_task(self.handle_message(message))
                except json.JSONDecodeError:
                    self.log("error", f"Invalid JSON: {line.strip()}")
                except Exception as e:
                    self.log("error", f"Error in stdin reader: {e}")
                    import traceback
                    self.log("error", traceback.format_exc())
        except Exception as e:
            self.log("error", f"Fatal error in stdin reader: {e}")
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
            await self.reload_plugin(data.get('plugin_name'))
        elif msg_type == 'event':
            await self.handle_event(data)
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
    
    async def reload_plugin(self, plugin_name: str):
        """Reload a single plugin.
        
        Args:
            plugin_name: Plugin name (format: author/name or just name)
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
            
            # Unload plugin
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
            
            # Reload plugin from database
            # Get plugin setting from database
            if '/' in plugin_id:
                author, name = plugin_id.split('/', 1)
            else:
                author = 'XQNEXT'  # Default author
                name = plugin_id
            
            # Always get fresh config from database
            plugin_config_data = {}
            try:
                from ..core.database import get_database_manager
                db_manager = get_database_manager()
                setting = await db_manager.get_plugin_setting(author, name)
                if setting and setting.config:
                    plugin_config_data = setting.config
                else:
                    # Fallback to default config from plugin.json
                    plugin_path = self.plugins_dir / name
                    plugin_json = plugin_path / "plugin.json"
                    if plugin_json.exists():
                        import json
                        with open(plugin_json, 'r', encoding='utf-8') as f:
                            plugin_metadata = json.load(f)
                            plugin_config_data = plugin_metadata.get('default_config', {})
            except Exception as e:
                self.log("warning", f"Could not get plugin config from database: {e}, using default config")
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
            
            self.log("info", f"Plugin {plugin_id} reloaded successfully")
        except Exception as e:
            self.log("error", f"Failed to reload plugin {plugin_name}: {e}")
            import traceback
            self.log("error", traceback.format_exc())
    
    async def handle_event(self, data: Dict[str, Any]):
        """Handle event from framework.
        
        Args:
            data: Event data with 'event' and 'data' fields
        """
        event_name = data.get('event')
        event_data = data.get('data', {})
        
        self.log("info", f"Dispatching event {event_name} to {len(self.plugins)} plugins: {list(self.plugins.keys())}")
        
        # Dispatch to all plugins
        for plugin_id, plugin_instance in self.plugins.items():
            try:
                if hasattr(plugin_instance, 'on_event'):
                    self.log("debug", f"Calling on_event for plugin {plugin_id}")
                    await plugin_instance.on_event(event_name, event_data)
            except Exception as e:
                self.log("error", f"Error in plugin {plugin_id} handling event {event_name}: {e}")
                import traceback
                self.log("error", traceback.format_exc())
    
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
            result = await asyncio.wait_for(future, timeout=10.0)
            self.log("debug", f"API {action} result: {result}")
            return result
        except asyncio.TimeoutError:
            self.runtime.pending_requests.pop(request_id, None)
            self.log("error", f"API {action} timeout")
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
            {} on success (empty dict)
        """
        result = await self.call_api('send_like', user_id=user_id, times=times)
        # send_like returns None/empty, wrap as success
        return {'success': True} if result is None else result
    
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
    
    async def set_config(self, key: str, value: Any):
        """Set plugin config."""
        # TODO: Implement config persistence
        if self.plugin_id not in self.runtime.plugin_configs:
            self.runtime.plugin_configs[self.plugin_id] = {}
        self.runtime.plugin_configs[self.plugin_id][key] = value
    
    async def get_storage(self, key: str) -> bytes:
        """Get binary storage."""
        # TODO: Implement storage
        return b''
    
    async def set_storage(self, key: str, value: bytes):
        """Set binary storage."""
        # TODO: Implement storage
        pass


async def main():
    """Main entry point."""
    runtime = PluginRuntime()
    await runtime.run()


if __name__ == '__main__':
    asyncio.run(main())
