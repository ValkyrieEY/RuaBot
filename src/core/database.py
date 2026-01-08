"""Database management for XQNEXT framework.

This module provides SQLAlchemy-based database management,
including models for plugin settings and binary storage.
"""

import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

from sqlalchemy import create_engine, select, update, delete
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, Session
from sqlalchemy.pool import StaticPool

from .logger import get_logger
from .models.plugin import PluginSetting
from .models.storage import BinaryStorage
from .models.ai import AIConfig, LLMModel, AIPreset, AIMemory, MCPServer

logger = get_logger(__name__)

Base = declarative_base()


class DatabaseManager:
    """Database manager for plugin system.
    
    Manages SQLAlchemy connections and provides high-level API
    for plugin settings and binary storage.
    """
    
    def __init__(self, db_path: str = "./data/plugins.db"):
        """Initialize database manager.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create async engine
        db_url = f"sqlite+aiosqlite:///{self.db_path}"
        self.engine = create_async_engine(
            db_url,
            echo=False,
            poolclass=StaticPool,
        )
        
        # Create session factory
        self.async_session = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        
        self._initialized = False
    
    async def initialize(self):
        """Initialize database tables."""
        if self._initialized:
            return
        
        async with self.engine.begin() as conn:
            # Import all models to ensure they're registered
            from .models.plugin import Base as PluginBase
            from .models.storage import Base as StorageBase
            from .models.ai import Base as AIBase
            from .models.tool_permission import Base as ToolPermissionBase
            
            # Create tables
            await conn.run_sync(PluginBase.metadata.create_all)
            await conn.run_sync(StorageBase.metadata.create_all)
            await conn.run_sync(AIBase.metadata.create_all)
            await conn.run_sync(ToolPermissionBase.metadata.create_all)
        
        self._initialized = True
        logger.info(f"Database initialized", db_path=str(self.db_path))
    
    @asynccontextmanager
    async def session(self):
        """Get database session context manager."""
        async with self.async_session() as session:
            try:
                yield session
                await session.commit()
            except Exception as e:
                await session.rollback()
                raise
    
    # ==================== Plugin Settings ====================
    
    async def get_plugin_setting(self, author: str, name: str) -> Optional[PluginSetting]:
        """Get plugin setting by author and name."""
        async with self.session() as session:
            result = await session.execute(
                select(PluginSetting).where(
                    PluginSetting.plugin_author == author,
                    PluginSetting.plugin_name == name
                )
            )
            return result.scalar_one_or_none()
    
    async def list_plugin_settings(self, enabled_only: bool = False) -> List[PluginSetting]:
        """List all plugin settings.
        
        Args:
            enabled_only: If True, only return enabled plugins
        """
        async with self.session() as session:
            query = select(PluginSetting)
            if enabled_only:
                query = query.where(PluginSetting.enabled == True)
            
            query = query.order_by(PluginSetting.priority.desc(), PluginSetting.plugin_name)
            result = await session.execute(query)
            return list(result.scalars().all())
    
    async def create_plugin_setting(
        self,
        author: str,
        name: str,
        enabled: bool = True,
        priority: int = 0,
        config: Optional[Dict[str, Any]] = None,
        install_source: str = 'local',
        install_info: Optional[Dict[str, Any]] = None
    ) -> PluginSetting:
        """Create new plugin setting."""
        async with self.session() as session:
            setting = PluginSetting(
                plugin_author=author,
                plugin_name=name,
                enabled=enabled,
                priority=priority,
                config=config or {},
                install_source=install_source,
                install_info=install_info or {}
            )
            session.add(setting)
            await session.flush()
            await session.refresh(setting)
            return setting
    
    async def update_plugin_setting(
        self,
        author: str,
        name: str,
        **kwargs
    ) -> bool:
        """Update plugin setting.
        
        Args:
            author: Plugin author
            name: Plugin name
            **kwargs: Fields to update (enabled, priority, config, etc.)
        
        Returns:
            True if updated, False if not found
        """
        async with self.session() as session:
            result = await session.execute(
                update(PluginSetting)
                .where(
                    PluginSetting.plugin_author == author,
                    PluginSetting.plugin_name == name
                )
                .values(**kwargs)
            )
            return result.rowcount > 0
    
    async def delete_plugin_setting(self, author: str, name: str) -> bool:
        """Delete plugin setting."""
        async with self.session() as session:
            result = await session.execute(
                delete(PluginSetting).where(
                    PluginSetting.plugin_author == author,
                    PluginSetting.plugin_name == name
                )
            )
            return result.rowcount > 0
    
    # ==================== Binary Storage ====================
    
    async def get_binary(
        self,
        owner_type: str,
        owner: str,
        key: str
    ) -> Optional[bytes]:
        """Get binary data.
        
        Args:
            owner_type: Type of owner (e.g., 'plugin')
            owner: Owner identifier (e.g., plugin name)
            key: Storage key
        
        Returns:
            Binary data or None if not found
        """
        unique_key = BinaryStorage.make_unique_key(owner_type, owner, key)
        async with self.session() as session:
            result = await session.execute(
                select(BinaryStorage).where(BinaryStorage.unique_key == unique_key)
            )
            storage = result.scalar_one_or_none()
            return storage.value if storage else None
    
    async def set_binary(
        self,
        owner_type: str,
        owner: str,
        key: str,
        value: bytes
    ) -> bool:
        """Set binary data.
        
        Args:
            owner_type: Type of owner (e.g., 'plugin')
            owner: Owner identifier (e.g., plugin name)
            key: Storage key
            value: Binary data (max 10MB recommended)
        
        Returns:
            True if successful
        """
        if len(value) > 10 * 1024 * 1024:  # 10MB
            logger.warning(f"Binary data exceeds 10MB", size=len(value))
        
        unique_key = BinaryStorage.make_unique_key(owner_type, owner, key)
        
        async with self.session() as session:
            # Try to get existing
            result = await session.execute(
                select(BinaryStorage).where(BinaryStorage.unique_key == unique_key)
            )
            storage = result.scalar_one_or_none()
            
            if storage:
                # Update existing
                storage.value = value
            else:
                # Create new
                storage = BinaryStorage(
                    unique_key=unique_key,
                    key=key,
                    owner_type=owner_type,
                    owner=owner,
                    value=value
                )
                session.add(storage)
            
            await session.flush()
            return True
    
    async def delete_binary(
        self,
        owner_type: str,
        owner: str,
        key: str
    ) -> bool:
        """Delete binary data."""
        unique_key = BinaryStorage.make_unique_key(owner_type, owner, key)
        async with self.session() as session:
            result = await session.execute(
                delete(BinaryStorage).where(BinaryStorage.unique_key == unique_key)
            )
            return result.rowcount > 0
    
    async def list_binary_keys(
        self,
        owner_type: str,
        owner: str
    ) -> List[str]:
        """List all binary storage keys for an owner."""
        async with self.session() as session:
            result = await session.execute(
                select(BinaryStorage.key).where(
                    BinaryStorage.owner_type == owner_type,
                    BinaryStorage.owner == owner
                )
            )
            return [row[0] for row in result.all()]
    
    # ==================== AI Configuration ====================
    
    async def get_ai_config(self, config_type: str, target_id: Optional[str] = None) -> Optional[AIConfig]:
        """Get AI configuration."""
        async with self.session() as session:
            result = await session.execute(
                select(AIConfig).where(
                    AIConfig.config_type == config_type,
                    AIConfig.target_id == target_id
                )
            )
            return result.scalar_one_or_none()
    
    async def list_ai_configs(self, config_type: Optional[str] = None) -> List[AIConfig]:
        """List AI configurations."""
        async with self.session() as session:
            query = select(AIConfig)
            if config_type:
                query = query.where(AIConfig.config_type == config_type)
            query = query.order_by(AIConfig.updated_at.desc())
            result = await session.execute(query)
            return list(result.scalars().all())
    
    async def create_ai_config(
        self,
        config_type: str,
        target_id: Optional[str] = None,
        enabled: bool = False,
        model_uuid: Optional[str] = None,
        preset_uuid: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> AIConfig:
        """Create AI configuration."""
        async with self.session() as session:
            ai_config = AIConfig(
                config_type=config_type,
                target_id=target_id,
                enabled=enabled,
                model_uuid=model_uuid,
                preset_uuid=preset_uuid,
                config=config or {}
            )
            session.add(ai_config)
            await session.flush()
            await session.refresh(ai_config)
            return ai_config
    
    async def update_ai_config(
        self,
        config_type: str,
        target_id: Optional[str],
        **kwargs
    ) -> bool:
        """Update AI configuration."""
        async with self.session() as session:
            result = await session.execute(
                update(AIConfig)
                .where(
                    AIConfig.config_type == config_type,
                    AIConfig.target_id == target_id
                )
                .values(**kwargs)
            )
            return result.rowcount > 0
    
    async def delete_ai_config(self, config_type: str, target_id: Optional[str]) -> bool:
        """Delete AI configuration."""
        async with self.session() as session:
            result = await session.execute(
                delete(AIConfig).where(
                    AIConfig.config_type == config_type,
                    AIConfig.target_id == target_id
                )
            )
            return result.rowcount > 0
    
    async def batch_update_ai_configs(
        self,
        config_type: str,
        target_ids: List[str],
        **kwargs
    ) -> int:
        """Batch update AI configurations."""
        async with self.session() as session:
            result = await session.execute(
                update(AIConfig)
                .where(
                    AIConfig.config_type == config_type,
                    AIConfig.target_id.in_(target_ids)
                )
                .values(**kwargs)
            )
            return result.rowcount
    
    # ==================== LLM Models ====================
    
    async def get_llm_model(self, uuid: str) -> Optional[LLMModel]:
        """Get LLM model."""
        async with self.session() as session:
            result = await session.execute(
                select(LLMModel).where(LLMModel.uuid == uuid)
            )
            return result.scalar_one_or_none()
    
    async def list_llm_models(self) -> List[LLMModel]:
        """List all LLM models."""
        async with self.session() as session:
            result = await session.execute(
                select(LLMModel).order_by(LLMModel.created_at.desc())
            )
            return list(result.scalars().all())
    
    async def create_llm_model(
        self,
        uuid: str,
        name: str,
        provider: str,
        model_name: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        is_default: bool = False,
        supports_tools: bool = False,
        supports_vision: bool = False,
        description: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> LLMModel:
        """Create LLM model."""
        async with self.session() as session:
            # If setting as default, unset other defaults
            if is_default:
                await session.execute(
                    update(LLMModel).values(is_default=False)
                )
            
            llm_model = LLMModel(
                uuid=uuid,
                name=name,
                description=description,
                provider=provider,
                model_name=model_name,
                api_key=api_key,
                base_url=base_url,
                is_default=is_default,
                supports_tools=supports_tools,
                supports_vision=supports_vision,
                config=config or {}
            )
            session.add(llm_model)
            await session.flush()
            await session.refresh(llm_model)
            return llm_model
    
    async def update_llm_model(self, uuid: str, **kwargs) -> bool:
        """Update LLM model."""
        async with self.session() as session:
            # If setting as default, unset other defaults
            if kwargs.get('is_default') is True:
                await session.execute(
                    update(LLMModel).where(LLMModel.uuid != uuid).values(is_default=False)
                )
            
            result = await session.execute(
                update(LLMModel).where(LLMModel.uuid == uuid).values(**kwargs)
            )
            return result.rowcount > 0
    
    async def delete_llm_model(self, uuid: str) -> bool:
        """Delete LLM model."""
        async with self.session() as session:
            result = await session.execute(
                delete(LLMModel).where(LLMModel.uuid == uuid)
            )
            return result.rowcount > 0
    
    async def get_default_llm_model(self) -> Optional[LLMModel]:
        """Get default LLM model."""
        async with self.session() as session:
            result = await session.execute(
                select(LLMModel).where(LLMModel.is_default == True)
            )
            return result.scalar_one_or_none()
    
    # ==================== AI Presets ====================
    
    async def get_ai_preset(self, uuid: str) -> Optional[AIPreset]:
        """Get AI preset."""
        async with self.session() as session:
            result = await session.execute(
                select(AIPreset).where(AIPreset.uuid == uuid)
            )
            return result.scalar_one_or_none()
    
    async def list_ai_presets(self) -> List[AIPreset]:
        """List all AI presets."""
        async with self.session() as session:
            result = await session.execute(
                select(AIPreset).order_by(AIPreset.created_at.desc())
            )
            return list(result.scalars().all())
    
    async def create_ai_preset(
        self,
        uuid: str,
        name: str,
        system_prompt: str,
        temperature: float = 1.0,
        max_tokens: int = 2000,
        description: Optional[str] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> AIPreset:
        """Create AI preset."""
        async with self.session() as session:
            preset = AIPreset(
                uuid=uuid,
                name=name,
                description=description,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                top_k=top_k,
                config=config or {}
            )
            session.add(preset)
            await session.flush()
            await session.refresh(preset)
            return preset
    
    async def update_ai_preset(self, uuid: str, **kwargs) -> bool:
        """Update AI preset."""
        async with self.session() as session:
            result = await session.execute(
                update(AIPreset).where(AIPreset.uuid == uuid).values(**kwargs)
            )
            return result.rowcount > 0
    
    async def delete_ai_preset(self, uuid: str) -> bool:
        """Delete AI preset."""
        async with self.session() as session:
            result = await session.execute(
                delete(AIPreset).where(AIPreset.uuid == uuid)
            )
            return result.rowcount > 0
    
    # ==================== AI Memory ====================
    
    async def get_ai_memory(
        self,
        memory_type: str,
        target_id: str,
        preset_uuid: Optional[str] = None
    ) -> Optional[AIMemory]:
        """Get AI memory."""
        async with self.session() as session:
            query = select(AIMemory).where(
                AIMemory.memory_type == memory_type,
                AIMemory.target_id == target_id
            )
            if preset_uuid:
                query = query.where(AIMemory.preset_uuid == preset_uuid)
            else:
                query = query.where(AIMemory.preset_uuid.is_(None))
            
            result = await session.execute(query)
            return result.scalar_one_or_none()
    
    async def list_ai_memories(
        self,
        memory_type: Optional[str] = None,
        target_id: Optional[str] = None
    ) -> List[AIMemory]:
        """List AI memories."""
        async with self.session() as session:
            query = select(AIMemory)
            if memory_type:
                query = query.where(AIMemory.memory_type == memory_type)
            if target_id:
                query = query.where(AIMemory.target_id == target_id)
            query = query.order_by(AIMemory.last_active.desc())
            result = await session.execute(query)
            return list(result.scalars().all())
    
    async def create_ai_memory(
        self,
        uuid: str,
        memory_type: str,
        target_id: str,
        preset_uuid: Optional[str] = None,
        messages: Optional[List[Dict[str, Any]]] = None
    ) -> AIMemory:
        """Create AI memory."""
        async with self.session() as session:
            memory = AIMemory(
                uuid=uuid,
                memory_type=memory_type,
                target_id=target_id,
                preset_uuid=preset_uuid,
                messages=messages or []
            )
            session.add(memory)
            await session.flush()
            await session.refresh(memory)
            return memory
    
    async def update_ai_memory(
        self,
        uuid: str,
        **kwargs
    ) -> bool:
        """Update AI memory."""
        async with self.session() as session:
            result = await session.execute(
                update(AIMemory).where(AIMemory.uuid == uuid).values(**kwargs)
            )
            return result.rowcount > 0
    
    async def delete_ai_memory(self, uuid: str) -> bool:
        """Delete AI memory."""
        async with self.session() as session:
            result = await session.execute(
                delete(AIMemory).where(AIMemory.uuid == uuid)
            )
            return result.rowcount > 0
    
    async def clear_ai_memory(
        self,
        memory_type: str,
        target_id: str,
        preset_uuid: Optional[str] = None
    ) -> bool:
        """Clear AI memory (set messages to empty)."""
        async with self.session() as session:
            query = update(AIMemory).where(
                AIMemory.memory_type == memory_type,
                AIMemory.target_id == target_id
            )
            if preset_uuid:
                query = query.where(AIMemory.preset_uuid == preset_uuid)
            else:
                query = query.where(AIMemory.preset_uuid.is_(None))
            
            result = await session.execute(
                query.values(messages=[], message_count=0)
            )
            return result.rowcount > 0
    
    # ==================== MCP Servers ====================
    
    async def get_mcp_server(self, uuid: str) -> Optional[MCPServer]:
        """Get MCP server."""
        async with self.session() as session:
            result = await session.execute(
                select(MCPServer).where(MCPServer.uuid == uuid)
            )
            return result.scalar_one_or_none()
    
    async def list_mcp_servers(self, enabled_only: bool = False) -> List[MCPServer]:
        """List MCP servers."""
        async with self.session() as session:
            query = select(MCPServer)
            if enabled_only:
                query = query.where(MCPServer.enabled == True)
            query = query.order_by(MCPServer.created_at.desc())
            result = await session.execute(query)
            return list(result.scalars().all())
    
    async def create_mcp_server(
        self,
        uuid: str,
        name: str,
        mode: str,
        enabled: bool = False,
        description: Optional[str] = None,
        command: Optional[str] = None,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        url: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> MCPServer:
        """Create MCP server."""
        async with self.session() as session:
            server = MCPServer(
                uuid=uuid,
                name=name,
                description=description,
                enabled=enabled,
                mode=mode,
                command=command,
                args=args or [],
                env=env or {},
                url=url,
                headers=headers or {},
                timeout=timeout,
                config=config or {}
            )
            session.add(server)
            await session.flush()
            await session.refresh(server)
            return server
    
    async def update_mcp_server(self, uuid: str, **kwargs) -> bool:
        """Update MCP server."""
        async with self.session() as session:
            result = await session.execute(
                update(MCPServer).where(MCPServer.uuid == uuid).values(**kwargs)
            )
            return result.rowcount > 0
    
    async def delete_mcp_server(self, uuid: str) -> bool:
        """Delete MCP server."""
        async with self.session() as session:
            result = await session.execute(
                delete(MCPServer).where(MCPServer.uuid == uuid)
            )
            return result.rowcount > 0
    
    async def close(self):
        """Close database connections."""
        await self.engine.dispose()
        logger.info("Database connections closed")


# Global database manager instance
_db_manager: Optional[DatabaseManager] = None


def get_database_manager() -> DatabaseManager:
    """Get global database manager instance."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


async def initialize_database():
    """Initialize global database manager."""
    db = get_database_manager()
    await db.initialize()

