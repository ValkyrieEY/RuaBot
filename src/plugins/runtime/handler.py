"""Runtime connection handler (placeholder).

This will be expanded to handle plugin runtime requests.
"""

from typing import Dict, Any
from ...core.logger import get_logger

logger = get_logger(__name__)


class RuntimeConnectionHandler:
    """Handler for plugin runtime connections.
    
    Processes requests from plugin runtime and interacts with
    framework services (database, event bus, etc.).
    """
    
    def __init__(self, db_manager):
        """Initialize handler.
        
        Args:
            db_manager: DatabaseManager instance
        """
        self.db_manager = db_manager
    
    async def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle request from plugin runtime.
        
        Args:
            request: Request dict with 'action' and 'data' fields
        
        Returns:
            Response dict
        """
        action = request.get('action')
        data = request.get('data', {})
        
        if action == 'get_config':
            return await self._handle_get_config(data)
        elif action == 'set_config':
            return await self._handle_set_config(data)
        elif action == 'get_config_upload':
            return await self._handle_get_config_upload(data)
        elif action == 'get_binary':
            return await self._handle_get_binary(data)
        elif action == 'set_binary':
            return await self._handle_set_binary(data)
        else:
            return {'success': False, 'error': f'Unknown action: {action}'}
    
    async def _handle_get_config(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get_config request."""
        author = data.get('author')
        name = data.get('name')
        
        setting = await self.db_manager.get_plugin_setting(author, name)
        if setting:
            return {'success': True, 'config': setting.config}
        else:
            return {'success': False, 'error': 'Plugin not found'}
    
    async def _handle_set_config(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle set_config request."""
        author = data.get('author')
        name = data.get('name')
        config = data.get('config', {})
        
        success = await self.db_manager.update_plugin_setting(
            author, name, config=config
        )
        return {'success': success}

    async def _handle_get_config_upload(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle plugin config upload reads from plugin-private storage."""
        owner = data.get('owner')
        key = data.get('key')

        if not isinstance(key, str) or not key.startswith('plugin_config_'):
            return {'success': False, 'error': 'Invalid config upload key'}

        value = await self.db_manager.get_binary('plugin', owner, key)
        if value:
            import base64

            return {'success': True, 'value': base64.b64encode(value).decode()}
        return {'success': False, 'error': 'Key not found'}
    
    async def _handle_get_binary(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get_binary request."""
        owner = data.get('owner')
        key = data.get('key')
        
        value = await self.db_manager.get_binary('plugin', owner, key)
        if value:
            # Encode binary as base64 for JSON transport
            import base64
            return {'success': True, 'value': base64.b64encode(value).decode()}
        else:
            return {'success': False, 'error': 'Key not found'}
    
    async def _handle_set_binary(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle set_binary request."""
        owner = data.get('owner')
        key = data.get('key')
        value_b64 = data.get('value')
        
        try:
            # Decode base64
            import base64
            value = base64.b64decode(value_b64)
            
            logger.debug(f"Saving binary for plugin={owner}, key={key}, size={len(value)} bytes")
            success = await self.db_manager.set_binary('plugin', owner, key, value)
            logger.debug(f"Save result: {success}")
            
            if not success:
                logger.error(f"set_binary returned False for plugin={owner}, key={key}")
            
            return {'success': success}
        except Exception as e:
            logger.error(f"Exception in _handle_set_binary: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    async def _handle_delete_binary(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle delete_binary request."""
        owner = data.get('owner')
        key = data.get('key')
        
        success = await self.db_manager.delete_binary('plugin', owner, key)
        return {'success': success}
    
    async def _handle_list_binary_keys(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle list_binary_keys request."""
        owner = data.get('owner')
        
        keys = await self.db_manager.list_binary_keys('plugin', owner)
        return {'success': True, 'keys': keys}

