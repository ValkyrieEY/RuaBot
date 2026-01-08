"""AI function manager."""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from ..core.database import DatabaseManager, get_database_manager
from ..core.models.ai import AIConfig, AIMemory
from ..core.logger import get_logger
from .model_manager import ModelManager

logger = get_logger(__name__)


class AIManager:
    """Manages AI functionality."""
    
    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        model_manager: Optional[ModelManager] = None
    ):
        self.db_manager = db_manager or get_database_manager()
        self.model_manager = model_manager
        self._config_cache: Dict[str, AIConfig] = {}
        self._memory_cache: Dict[str, AIMemory] = {}
    
    async def initialize(self):
        """Initialize AI manager."""
        await self._refresh_config_cache()
        logger.info("AIManager initialized")
    
    async def _refresh_config_cache(self):
        """Refresh config cache."""
        configs = await self.db_manager.list_ai_configs()
        self._config_cache = {}
        for config in configs:
            key = f"{config.config_type}:{config.target_id or 'global'}"
            self._config_cache[key] = config
    
    # ==================== Configuration Management ====================
    
    async def get_config(
        self,
        config_type: str,
        target_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get AI configuration with inheritance from global config.
        
        For group/user configs, inherits from global config if not set.
        """
        config = await self.db_manager.get_ai_config(config_type, target_id)
        config_dict = config.to_dict() if config else None
        
        # For group/user configs, merge with global config
        if config_type in ('group', 'user') and config_dict:
            global_config = await self.db_manager.get_ai_config('global', None)
            if global_config:
                global_dict = global_config.to_dict()
                # Merge config dict (like trigger_command) - only inherit if not set locally
                global_config_dict = global_dict.get('config', {})
                local_config_dict = config_dict.get('config', {})
                # Start with global config, then override with local config
                # Only override if local value is explicitly set (not empty string or None)
                merged_config = global_config_dict.copy()
                for key, value in local_config_dict.items():
                    # If local config has the key, use it (even if empty string - that's an explicit override)
                    merged_config[key] = value
                config_dict['config'] = merged_config
                # Inherit model/preset if not set locally
                if not config_dict.get('model_uuid') and global_dict.get('model_uuid'):
                    config_dict['model_uuid'] = global_dict['model_uuid']
                if not config_dict.get('preset_uuid') and global_dict.get('preset_uuid'):
                    config_dict['preset_uuid'] = global_dict['preset_uuid']
        
        if config_dict:
            return config_dict
        
        # Return default config if not exists
        return {
            'config_type': config_type,
            'target_id': target_id,
            'enabled': False,
            'model_uuid': None,
            'preset_uuid': None,
            'message_count': 0,
            'config': {}
        }
    
    async def update_config(
        self,
        config_type: str,
        target_id: Optional[str] = None,
        **kwargs
    ) -> bool:
        """Update AI configuration."""
        # Check if config exists
        existing = await self.db_manager.get_ai_config(config_type, target_id)
        
        if existing:
            success = await self.db_manager.update_ai_config(
                config_type, target_id, **kwargs
            )
        else:
            # Create new config
            config = await self.db_manager.create_ai_config(
                config_type=config_type,
                target_id=target_id,
                **kwargs
            )
            success = config is not None
        
        if success:
            await self._refresh_config_cache()
            logger.info(f"AI config updated: {config_type}:{target_id}")
        
        return success
    
    async def list_group_configs(self) -> List[Dict[str, Any]]:
        """List all group configurations."""
        configs = await self.db_manager.list_ai_configs('group')
        return [config.to_dict() for config in configs]
    
    async def batch_update_groups(
        self,
        group_ids: List[str],
        enabled: Optional[bool] = None,
        model_uuid: Optional[str] = None,
        preset_uuid: Optional[str] = None
    ) -> int:
        """Batch update group configurations."""
        updates = {}
        if enabled is not None:
            updates['enabled'] = enabled
        if model_uuid is not None:
            updates['model_uuid'] = model_uuid
        if preset_uuid is not None:
            updates['preset_uuid'] = preset_uuid
        
        if not updates:
            return 0
        
        # Ensure configs exist for all groups
        for group_id in group_ids:
            existing = await self.db_manager.get_ai_config('group', group_id)
            if not existing:
                await self.db_manager.create_ai_config(
                    config_type='group',
                    target_id=group_id,
                    **updates
                )
        
        # Batch update
        count = await self.db_manager.batch_update_ai_configs('group', group_ids, **updates)
        await self._refresh_config_cache()
        logger.info(f"Batch updated {count} group configs")
        return count
    
    async def is_enabled(
        self,
        config_type: str,
        target_id: Optional[str] = None
    ) -> bool:
        """Check if AI is enabled for target."""
        # Check global config first
        global_config = await self.db_manager.get_ai_config('global', None)
        if global_config and not global_config.enabled:
            return False
        
        # Check specific config
        config = await self.db_manager.get_ai_config(config_type, target_id)
        if config:
            return config.enabled
        
        return False
    
    async def increment_message_count(
        self,
        config_type: str,
        target_id: Optional[str] = None
    ):
        """Increment message count."""
        config = await self.db_manager.get_ai_config(config_type, target_id)
        if config:
            await self.db_manager.update_ai_config(
                config_type, target_id,
                message_count=config.message_count + 1
            )
            await self._refresh_config_cache()
    
    # ==================== Memory Management ====================
    
    async def get_memory(
        self,
        memory_type: str,
        target_id: str,
        preset_uuid: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get AI memory."""
        memory = await self.db_manager.get_ai_memory(memory_type, target_id, preset_uuid)
        if memory:
            return memory.to_dict()
        
        # Return empty memory if not exists
        return {
            'uuid': None,
            'memory_type': memory_type,
            'target_id': target_id,
            'preset_uuid': preset_uuid,
            'messages': [],
            'message_count': 0
        }
    
    async def create_or_update_memory(
        self,
        memory_type: str,
        target_id: str,
        messages: List[Dict[str, Any]],
        preset_uuid: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create or update AI memory."""
        existing = await self.db_manager.get_ai_memory(memory_type, target_id, preset_uuid)
        
        if existing:
            await self.db_manager.update_ai_memory(
                existing.uuid,
                messages=messages,
                message_count=len(messages),
                last_active=datetime.utcnow()
            )
            await self._refresh_memory_cache(existing.uuid)
            return existing.to_dict()
        else:
            memory_uuid = str(uuid.uuid4())
            memory = await self.db_manager.create_ai_memory(
                uuid=memory_uuid,
                memory_type=memory_type,
                target_id=target_id,
                preset_uuid=preset_uuid,
                messages=messages
            )
            self._memory_cache[memory_uuid] = memory
            return memory.to_dict()
    
    async def clear_memory(
        self,
        memory_type: str,
        target_id: str,
        preset_uuid: Optional[str] = None
    ) -> bool:
        """Clear AI memory."""
        success = await self.db_manager.clear_ai_memory(memory_type, target_id, preset_uuid)
        if success:
            logger.info(f"Memory cleared: {memory_type}:{target_id}")
        return success
    
    async def list_memories(
        self,
        memory_type: Optional[str] = None,
        target_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List AI memories."""
        memories = await self.db_manager.list_ai_memories(memory_type, target_id)
        return [memory.to_dict() for memory in memories]
    
    async def delete_memory(self, memory_uuid: str) -> bool:
        """Delete AI memory."""
        success = await self.db_manager.delete_ai_memory(memory_uuid)
        if success:
            if memory_uuid in self._memory_cache:
                del self._memory_cache[memory_uuid]
            logger.info(f"Memory deleted: {memory_uuid}")
        return success
    
    async def _refresh_memory_cache(self, memory_uuid: str):
        """Refresh memory cache for a specific memory."""
        # This would be called after updates
        pass

