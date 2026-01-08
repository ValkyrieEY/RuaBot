"""Plugin API for XQNEXT plugins.

Provides API for plugins to interact with the framework,
including sending messages, managing config, and storage.
"""

import asyncio
from typing import Dict, Any, Optional, List
from ...core.logger import get_logger

logger = get_logger(__name__)


class PluginAPI:
    """Plugin API interface.
    
    This class is provided to each plugin and allows it to:
    - Send OneBot messages
    - Read/write configuration
    - Store/retrieve binary data
    - Emit events
    - Access framework services
    """
    
    def __init__(self, plugin_name: str, connector):
        """Initialize plugin API.
        
        Args:
            plugin_name: Name of the plugin
            connector: PluginRuntimeConnector instance
        """
        self.plugin_name = plugin_name
        self.connector = connector
        self.db_manager = connector.db_manager
        self.event_bus = connector.event_bus
    
    # ==================== OneBot API ====================
    
    async def call_api(self, action: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Call any OneBot API.
        
        This is a universal method to call any OneBot API endpoint.
        
        Args:
            action: API action name (e.g., 'send_private_msg', 'get_group_list')
            params: API parameters
        
        Returns:
            API response dict
        
        Example:
            # Get group list
            result = await api.call_api('get_group_list')
            
            # Send like
            result = await api.call_api('send_like', {'user_id': 123456, 'times': 10})
            
            # Get group member list
            result = await api.call_api('get_group_member_list', {'group_id': 123456})
        """
        try:
            # Get OneBot adapter
            if hasattr(self.connector, 'app') and hasattr(self.connector.app, 'onebot_adapter'):
                onebot = self.connector.app.onebot_adapter
            elif hasattr(self.connector, 'onebot_adapter'):
                onebot = self.connector.onebot_adapter
            else:
                logger.error("OneBot adapter not available")
                return {'success': False, 'error': 'OneBot adapter not available'}
            
            # Call API
            if hasattr(onebot, 'call_api'):
                result = await onebot.call_api(action, params or {})
            elif hasattr(onebot, action):
                # Try to call method directly
                method = getattr(onebot, action)
                if params:
                    result = await method(**params)
                else:
                    result = await method()
            else:
                return {'success': False, 'error': f'API action not found: {action}'}
            
            logger.debug(
                f"[Plugin:{self.plugin_name}] Called API: {action}",
                params=params
            )
            return {'success': True, 'data': result}
            
        except Exception as e:
            logger.error(f"[Plugin:{self.plugin_name}] API call failed: {action}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    async def send_message(
        self,
        message_type: str,
        target_id: int,
        message: str,
        auto_escape: bool = False
    ) -> Dict[str, Any]:
        """Send OneBot message.
        
        Args:
            message_type: 'private' or 'group'
            target_id: User ID or Group ID
            message: Message content (support CQ code)
            auto_escape: Whether to escape CQ code
        
        Returns:
            Response dict with message_id
        
        Example:
            await api.send_message('group', 123456, 'Hello World!')
            await api.send_message('private', 789, '[CQ:image,file=xxx.jpg]')
        """
        try:
            # Get OneBot adapter from connector
            if not hasattr(self.connector, 'onebot_adapter'):
                # Try to get from app
                if hasattr(self.connector, 'app') and hasattr(self.connector.app, 'onebot_adapter'):
                    onebot = self.connector.app.onebot_adapter
                else:
                    logger.error("OneBot adapter not available")
                    return {'success': False, 'error': 'OneBot adapter not available'}
            else:
                onebot = self.connector.onebot_adapter
            
            # Call OneBot API
            if message_type == 'private':
                result = await onebot.send_private_msg(target_id, message, auto_escape)
            elif message_type == 'group':
                result = await onebot.send_group_msg(target_id, message, auto_escape)
            else:
                return {'success': False, 'error': f'Invalid message_type: {message_type}'}
            
            logger.info(
                f"[Plugin:{self.plugin_name}] Sent {message_type} message",
                target_id=target_id
            )
            return {'success': True, 'data': result}
            
        except Exception as e:
            logger.error(f"[Plugin:{self.plugin_name}] Failed to send message: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    async def send_private_msg(self, user_id: int, message: str, auto_escape: bool = False) -> Dict[str, Any]:
        """Send private message (shortcut).
        
        Args:
            user_id: QQ number
            message: Message content
            auto_escape: Whether to escape CQ code
        
        Returns:
            Response dict
        """
        return await self.send_message('private', user_id, message, auto_escape)
    
    async def send_group_msg(self, group_id: int, message: str, auto_escape: bool = False) -> Dict[str, Any]:
        """Send group message (shortcut).
        
        Args:
            group_id: Group number
            message: Message content
            auto_escape: Whether to escape CQ code
        
        Returns:
            Response dict
        """
        return await self.send_message('group', group_id, message, auto_escape)
    
    async def delete_msg(self, message_id: int) -> Dict[str, Any]:
        """Delete a message.
        
        Args:
            message_id: Message ID
        
        Returns:
            Response dict
        """
        try:
            if hasattr(self.connector, 'onebot_adapter'):
                onebot = self.connector.onebot_adapter
            elif hasattr(self.connector, 'app') and hasattr(self.connector.app, 'onebot_adapter'):
                onebot = self.connector.app.onebot_adapter
            else:
                return {'success': False, 'error': 'OneBot adapter not available'}
            
            result = await onebot.delete_msg(message_id)
            return {'success': True, 'data': result}
        except Exception as e:
            logger.error(f"[Plugin:{self.plugin_name}] Failed to delete message: {e}")
            return {'success': False, 'error': str(e)}
    
    async def get_msg(self, message_id: int) -> Dict[str, Any]:
        """Get message info.
        
        Args:
            message_id: Message ID
        
        Returns:
            Message info dict
        """
        try:
            if hasattr(self.connector, 'onebot_adapter'):
                onebot = self.connector.onebot_adapter
            elif hasattr(self.connector, 'app') and hasattr(self.connector.app, 'onebot_adapter'):
                onebot = self.connector.app.onebot_adapter
            else:
                return {'success': False, 'error': 'OneBot adapter not available'}
            
            result = await onebot.get_msg(message_id)
            return {'success': True, 'data': result}
        except Exception as e:
            logger.error(f"[Plugin:{self.plugin_name}] Failed to get message: {e}")
            return {'success': False, 'error': str(e)}
    
    # ==================== Config API ====================
    
    async def get_config(self, key: Optional[str] = None) -> Any:
        """Get plugin configuration.
        
        Args:
            key: Config key (if None, return all config)
        
        Returns:
            Config value or dict
        """
        try:
            # Parse plugin name (format: author/name)
            if '/' in self.plugin_name:
                author, name = self.plugin_name.split('/', 1)
            else:
                author, name = 'unknown', self.plugin_name
            
            setting = await self.db_manager.get_plugin_setting(author, name)
            if not setting:
                return {} if key is None else None
            
            config = setting.config or {}
            
            if key is None:
                return config
            else:
                return config.get(key)
        except Exception as e:
            logger.error(f"[Plugin:{self.plugin_name}] Failed to get config: {e}")
            return {} if key is None else None
    
    async def set_config(self, key: str, value: Any) -> bool:
        """Set plugin configuration.
        
        Args:
            key: Config key
            value: Config value
        
        Returns:
            True if successful
        """
        try:
            # Parse plugin name
            if '/' in self.plugin_name:
                author, name = self.plugin_name.split('/', 1)
            else:
                author, name = 'unknown', self.plugin_name
            
            # Get current config
            setting = await self.db_manager.get_plugin_setting(author, name)
            if not setting:
                logger.error(f"[Plugin:{self.plugin_name}] Plugin setting not found")
                return False
            
            # Update config
            config = setting.config or {}
            config[key] = value
            
            # Save to database
            success = await self.db_manager.update_plugin_setting(
                author, name, config=config
            )
            
            if success:
                logger.info(f"[Plugin:{self.plugin_name}] Config updated: {key}")
            
            return success
        except Exception as e:
            logger.error(f"[Plugin:{self.plugin_name}] Failed to set config: {e}")
            return False
    
    # ==================== Storage API ====================
    
    async def get_storage(self, key: str) -> Optional[bytes]:
        """Get binary storage.
        
        Args:
            key: Storage key
        
        Returns:
            Binary data or None
        """
        try:
            value = await self.db_manager.get_binary('plugin', self.plugin_name, key)
            return value
        except Exception as e:
            logger.error(f"[Plugin:{self.plugin_name}] Failed to get storage: {e}")
            return None
    
    async def set_storage(self, key: str, value: bytes) -> bool:
        """Set binary storage.
        
        Args:
            key: Storage key
            value: Binary data (max 10MB recommended)
        
        Returns:
            True if successful
        """
        try:
            success = await self.db_manager.set_binary('plugin', self.plugin_name, key, value)
            if success:
                logger.info(f"[Plugin:{self.plugin_name}] Storage set: {key}")
            return success
        except Exception as e:
            logger.error(f"[Plugin:{self.plugin_name}] Failed to set storage: {e}")
            return False
    
    async def delete_storage(self, key: str) -> bool:
        """Delete binary storage.
        
        Args:
            key: Storage key
        
        Returns:
            True if successful
        """
        try:
            success = await self.db_manager.delete_binary('plugin', self.plugin_name, key)
            return success
        except Exception as e:
            logger.error(f"[Plugin:{self.plugin_name}] Failed to delete storage: {e}")
            return False
    
    async def list_storage_keys(self) -> List[str]:
        """List all storage keys for this plugin.
        
        Returns:
            List of keys
        """
        try:
            keys = await self.db_manager.list_binary_keys('plugin', self.plugin_name)
            return keys
        except Exception as e:
            logger.error(f"[Plugin:{self.plugin_name}] Failed to list storage keys: {e}")
            return []
    
    # ==================== Event API ====================
    
    async def emit_event(self, event_name: str, data: Dict[str, Any]):
        """Emit custom event to framework.
        
        Args:
            event_name: Event name (will be prefixed with 'plugin.')
            data: Event data
        """
        try:
            full_event_name = f"plugin.{self.plugin_name}.{event_name}"
            await self.event_bus.emit(full_event_name, data)
            logger.debug(f"[Plugin:{self.plugin_name}] Emitted event: {full_event_name}")
        except Exception as e:
            logger.error(f"[Plugin:{self.plugin_name}] Failed to emit event: {e}")
    
    # ==================== Utility API ====================
    
    def log(self, level: str, message: str, **kwargs):
        """Log message from plugin.
        
        Args:
            level: Log level (debug, info, warning, error)
            message: Log message
            **kwargs: Additional context
        """
        log_func = getattr(logger, level, logger.info)
        log_func(f"[Plugin:{self.plugin_name}] {message}", **kwargs)
    
    def get_plugin_name(self) -> str:
        """Get plugin name."""
        return self.plugin_name
    
    # ==================== Convenience Methods (常用 API 快捷方法) ====================
    
    async def get_group_list(self) -> Dict[str, Any]:
        """获取群列表"""
        return await self.call_api('get_group_list')
    
    async def get_group_info(self, group_id: int, no_cache: bool = False) -> Dict[str, Any]:
        """获取群信息"""
        return await self.call_api('get_group_info', {'group_id': group_id, 'no_cache': no_cache})
    
    async def get_group_member_list(self, group_id: int) -> Dict[str, Any]:
        """获取群成员列表"""
        return await self.call_api('get_group_member_list', {'group_id': group_id})
    
    async def get_group_member_info(self, group_id: int, user_id: int, no_cache: bool = False) -> Dict[str, Any]:
        """获取群成员信息"""
        return await self.call_api('get_group_member_info', {
            'group_id': group_id,
            'user_id': user_id,
            'no_cache': no_cache
        })
    
    async def get_friend_list(self) -> Dict[str, Any]:
        """获取好友列表"""
        return await self.call_api('get_friend_list')
    
    async def get_stranger_info(self, user_id: int, no_cache: bool = False) -> Dict[str, Any]:
        """获取陌生人信息"""
        return await self.call_api('get_stranger_info', {'user_id': user_id, 'no_cache': no_cache})
    
    async def send_like(self, user_id: int, times: int = 1) -> Dict[str, Any]:
        """点赞"""
        return await self.call_api('send_like', {'user_id': user_id, 'times': times})
    
    async def set_group_kick(self, group_id: int, user_id: int, reject_add_request: bool = False) -> Dict[str, Any]:
        """群踢人"""
        return await self.call_api('set_group_kick', {
            'group_id': group_id,
            'user_id': user_id,
            'reject_add_request': reject_add_request
        })
    
    async def set_group_ban(self, group_id: int, user_id: int, duration: int = 1800) -> Dict[str, Any]:
        """群禁言"""
        return await self.call_api('set_group_ban', {
            'group_id': group_id,
            'user_id': user_id,
            'duration': duration
        })
    
    async def set_group_whole_ban(self, group_id: int, enable: bool = True) -> Dict[str, Any]:
        """全员禁言"""
        return await self.call_api('set_group_whole_ban', {'group_id': group_id, 'enable': enable})
    
    async def set_group_admin(self, group_id: int, user_id: int, enable: bool = True) -> Dict[str, Any]:
        """设置群管理"""
        return await self.call_api('set_group_admin', {
            'group_id': group_id,
            'user_id': user_id,
            'enable': enable
        })
    
    async def set_group_card(self, group_id: int, user_id: int, card: str = "") -> Dict[str, Any]:
        """设置群名片"""
        return await self.call_api('set_group_card', {
            'group_id': group_id,
            'user_id': user_id,
            'card': card
        })
    
    async def set_group_name(self, group_id: int, group_name: str) -> Dict[str, Any]:
        """设置群名"""
        return await self.call_api('set_group_name', {'group_id': group_id, 'group_name': group_name})
    
    async def set_group_leave(self, group_id: int, is_dismiss: bool = False) -> Dict[str, Any]:
        """退出群"""
        return await self.call_api('set_group_leave', {'group_id': group_id, 'is_dismiss': is_dismiss})
    
    async def get_login_info(self) -> Dict[str, Any]:
        """获取登录号信息"""
        return await self.call_api('get_login_info')
    
    async def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        return await self.call_api('get_status')
    
    async def get_version_info(self) -> Dict[str, Any]:
        """获取版本信息"""
        return await self.call_api('get_version_info')
    
    async def upload_group_file(self, group_id: int, file: str, name: str, folder: str = "/") -> Dict[str, Any]:
        """上传群文件"""
        return await self.call_api('upload_group_file', {
            'group_id': group_id,
            'file': file,
            'name': name,
            'folder': folder
        })
    
    async def get_group_file_url(self, group_id: int, file_id: str, busid: int) -> Dict[str, Any]:
        """获取群文件下载链接"""
        return await self.call_api('get_group_file_url', {
            'group_id': group_id,
            'file_id': file_id,
            'busid': busid
        })
    
    async def get_image(self, file: str) -> Dict[str, Any]:
        """获取图片"""
        return await self.call_api('get_image', {'file': file})
    
    async def get_record(self, file: str, out_format: str) -> Dict[str, Any]:
        """获取语音"""
        return await self.call_api('get_record', {'file': file, 'out_format': out_format})
    
    async def can_send_image(self) -> Dict[str, Any]:
        """检查是否可以发送图片"""
        return await self.call_api('can_send_image')
    
    async def can_send_record(self) -> Dict[str, Any]:
        """检查是否可以发送语音"""
        return await self.call_api('can_send_record')
    
    async def ocr_image(self, image: str) -> Dict[str, Any]:
        """OCR 图片识别"""
        return await self.call_api('ocr_image', {'image': image})
    
    async def mark_msg_as_read(self, message_id: int) -> Dict[str, Any]:
        """标记消息已读"""
        return await self.call_api('mark_msg_as_read', {'message_id': message_id})
    
    async def forward_friend_single_msg(self, user_id: int, message_id: int) -> Dict[str, Any]:
        """转发消息到私聊"""
        return await self.call_api('forward_friend_single_msg', {
            'user_id': user_id,
            'message_id': message_id
        })
    
    async def forward_group_single_msg(self, group_id: int, message_id: int) -> Dict[str, Any]:
        """转发消息到群"""
        return await self.call_api('forward_group_single_msg', {
            'group_id': group_id,
            'message_id': message_id
        })

