"""Database management for XQNEXT framework.

This module provides SQLAlchemy-based database management,
including models for plugin settings and binary storage.
"""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any, Set
from contextlib import asynccontextmanager

from sqlalchemy import create_engine, select, update, delete, text, func, and_, or_
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, Session
from sqlalchemy.pool import StaticPool

from .logger import get_logger
from .models.plugin import PluginSetting
from .models.storage import BinaryStorage
from .models.sandbox import Sandbox, SandboxMessage
from .models.message_event import MessageEvent
from ..plugins.manifest import plugin_manifest_exists

logger = get_logger(__name__)

Base = declarative_base()


def collect_plugin_config_upload_keys(value: Any) -> Set[str]:
    """Collect Web UI config-file upload keys (prefix ``plugin_config_``) from JSON-like data."""
    found: Set[str] = set()

    def walk(v: Any) -> None:
        if isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
        elif isinstance(v, str) and v.startswith("plugin_config_"):
            found.add(v)

    walk(value)
    return found


class DatabaseManager:
    """Database manager for framework system.
    
    Manages SQLAlchemy connections and provides high-level API
    for plugin settings, binary storage, AI config, and knowledge graph.
    
    This database stores all framework data including:
    - Plugin settings and configurations
    - Binary storage
    - AI configurations (models, presets, memories, MCP)
    - Knowledge graph data
    """
    
    def __init__(self, db_path: str = "./data/framework.db"):
        """Initialize database manager.
        
        Args:
            db_path: Path to SQLite database file (default: framework.db)
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create async engine
        db_url = f"sqlite+aiosqlite:///{self.db_path}"
        self.engine = create_async_engine(
            db_url,
            echo=False,
            poolclass=StaticPool,
            pool_pre_ping=True,  # Enable connection health checks
        )
        
        # Create session factory
        self.async_session = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        
        self._initialized = False
        self._monitor_task: Optional[asyncio.Task] = None
    
    async def initialize(self):
        """Initialize database tables."""
        if self._initialized:
            return
        
        async with self.engine.begin() as conn:
            # Import all models to ensure they're registered
            from .models.plugin import Base as PluginBase
            from .models.storage import Base as StorageBase
            from .models.message_event import Base as MessageEventBase
            from .models.tool_permission import Base as ToolPermissionBase
            
            # Create tables for all subsystems
            await conn.run_sync(PluginBase.metadata.create_all)
            await conn.run_sync(StorageBase.metadata.create_all)
            await conn.run_sync(MessageEventBase.metadata.create_all)
            await conn.run_sync(ToolPermissionBase.metadata.create_all)

            from .models.sandbox import Base as SandboxBase
            await conn.run_sync(SandboxBase.metadata.create_all)
            logger.info("Sandbox tables initialized")
            
            # Run database migrations
            await self._run_migrations(conn)
        
        self._initialized = True
        
        # Start connection pool monitoring
        self._monitor_task = asyncio.create_task(self._monitor_connection_pool())
        
        logger.info(f"Framework database initialized", db_path=str(self.db_path))
    
    async def _run_migrations(self, conn):
        """Run database migrations to add missing columns."""
        # Old AI migrations were removed with the legacy AI subsystem.
        return
    
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
        priority: int = 100,  # Default: 100 (lower = earlier execution)
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
    
    async def prune_orphaned_plugin_settings(self, plugin_base: Path) -> List[str]:
        """Remove DB rows and related storage when the plugin directory is missing on disk.
        
        Matches the plugin runtime layout: ``plugin_base / plugin_name / metadata.yaml``
        plus ``settings.json``.
        Use after a plugin folder was removed manually (not via Web UI), so the database
        stays consistent with :meth:`delete_plugin` / :meth:`uninstall_plugin` behavior.
        
        Args:
            plugin_base: Resolved absolute path to the configured plugins directory.
        
        Returns:
            List of pruned plugin ids ``author/name`` (for logging).
        """
        plugin_base = Path(plugin_base).resolve()
        pruned: List[str] = []
        if not plugin_base.is_dir():
            logger.debug(
                "Skipping orphan plugin prune: plugin base is not a directory: %s",
                plugin_base,
            )
            return pruned
        
        try:
            rows = await self.list_plugin_settings(enabled_only=False)
        except Exception as e:
            logger.error("Failed to list plugin settings for orphan prune: %s", e, exc_info=True)
            return pruned
        
        for p in rows:
            manifest_dir = plugin_base / p.plugin_name
            if plugin_manifest_exists(manifest_dir):
                continue
            
            plugin_id = f"{p.plugin_author}/{p.plugin_name}"
            try:
                existing = await self.get_plugin_setting(p.plugin_author, p.plugin_name)
                try:
                    await self.delete_plugin_config_upload_blobs(
                        plugin_id,
                        existing.config if existing else None,
                        None,
                    )
                except Exception as e:
                    logger.warning(
                        "Orphan prune: failed to delete config upload blobs for %s: %s",
                        plugin_id,
                        e,
                    )
                
                await self.delete_plugin_setting(p.plugin_author, p.plugin_name)
                
                try:
                    storage_keys = await self.list_binary_keys("plugin", plugin_id)
                    for key in storage_keys:
                        await self.delete_binary("plugin", plugin_id, key)
                    if storage_keys:
                        logger.info(
                            "Orphan prune: removed %s binary key(s) for %s",
                            len(storage_keys),
                            plugin_id,
                        )
                except Exception as e:
                    logger.warning(
                        "Orphan prune: failed to clear binary storage for %s: %s",
                        plugin_id,
                        e,
                    )
                
                pruned.append(plugin_id)
                logger.info(
                    "Removed orphaned plugin record (manifest missing): %s (expected %s)",
                    plugin_id,
                    manifest,
                )
            except Exception as e:
                logger.error("Orphan prune failed for %s: %s", plugin_id, e, exc_info=True)
        
        if pruned:
            logger.info("Pruned %s orphaned plugin record(s) from database", len(pruned))
        return pruned
    
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
        try:
            if len(value) > 10 * 1024 * 1024:  # 10MB
                logger.warning(f"Binary data exceeds 10MB", size=len(value))
            
            unique_key = BinaryStorage.make_unique_key(owner_type, owner, key)
            
            logger.debug(f"set_binary: unique_key={unique_key}, size={len(value)}")
            
            async with self.session() as session:
                # Try to get existing
                result = await session.execute(
                    select(BinaryStorage).where(BinaryStorage.unique_key == unique_key)
                )
                storage = result.scalar_one_or_none()
                
                if storage:
                    # Update existing
                    logger.debug(f"Updating existing storage for {unique_key}")
                    storage.value = value
                else:
                    # Create new
                    logger.debug(f"Creating new storage for {unique_key}")
                    storage = BinaryStorage(
                        unique_key=unique_key,
                        key=key,
                        owner_type=owner_type,
                        owner=owner,
                        value=value
                    )
                    session.add(storage)
                
                await session.flush()
                logger.debug(f"set_binary: flush successful for {unique_key}")
                return True
        except Exception as e:
            logger.error(f"set_binary exception for {owner_type}:{owner}:{key}: {e}", exc_info=True)
            return False
    
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
    
    async def delete_plugin_config_upload_keys(
        self,
        plugin_owner: Optional[str],
        keys: Set[str],
    ) -> int:
        """Delete plugin config upload blobs from plugin-private binary storage."""
        if not keys:
            return 0

        deleted = 0
        for key in keys:
            try:
                if plugin_owner and await self.delete_binary("plugin", plugin_owner, key):
                    deleted += 1
            except Exception as e:
                logger.warning(f"Failed to delete plugin config upload blob {key}: {e}")

        logger.info(
            f"Removed {deleted}/{len(keys)} plugin_config upload blob(s) from binary storage"
        )
        return deleted

    async def delete_plugin_config_upload_blobs(
        self,
        plugin_owner: Optional[str],
        *configs: Optional[Dict[str, Any]],
    ) -> int:
        """Delete config-upload blobs referenced by plugin config dict(s)."""
        keys: Set[str] = set()
        for c in configs:
            if c:
                keys |= collect_plugin_config_upload_keys(c)
        return await self.delete_plugin_config_upload_keys(plugin_owner, keys)

    # ==================== Message Events ====================

    async def create_message_event(
        self,
        event_id: str,
        event_name: str,
        payload: Dict[str, Any],
        source: Optional[str] = None,
        event_time: Optional[datetime] = None,
    ) -> MessageEvent:
        """Persist a message/notice/request event for WebUI history recovery."""
        async with self.session() as session:
            row = MessageEvent(
                event_id=event_id,
                event_name=event_name,
                source=source,
                event_time=event_time or datetime.utcnow(),
                payload=payload or {},
            )
            session.add(row)
            await session.flush()
            await session.refresh(row)
            return row

    async def list_message_events(
        self,
        limit: int = 100,
        include_notices: bool = True,
        include_requests: bool = True,
        after_row_id: Optional[int] = None,
    ) -> List[MessageEvent]:
        """List persisted message log events, newest first."""
        # Guard query size to avoid large response payloads / memory spikes.
        limit = max(1, min(int(limit or 100), 500))
        async with self.session() as session:
            allowed_names = ["onebot.message", "onebot.message_sent"]
            if include_notices:
                allowed_names.append("onebot.notice")
            if include_requests:
                allowed_names.append("onebot.request")

            query = select(MessageEvent).where(MessageEvent.event_name.in_(allowed_names))
            if after_row_id is not None and after_row_id > 0:
                # Incremental catch-up: return rows newer than known DB cursor, oldest first.
                query = query.where(MessageEvent.id > after_row_id).order_by(MessageEvent.id.asc())
            else:
                # Full load: newest first.
                query = query.order_by(MessageEvent.event_time.desc(), MessageEvent.id.desc())
            query = query.limit(limit)
            result = await session.execute(query)
            return list(result.scalars().all())

    async def cleanup_message_events(self, retention_days: int = 7) -> int:
        """Delete old persisted message events."""
        cutoff = datetime.utcnow() - timedelta(days=retention_days)
        async with self.session() as session:
            result = await session.execute(
                delete(MessageEvent).where(MessageEvent.event_time < cutoff)
            )
            return int(result.rowcount or 0)

    async def truncate_message_events(self, max_rows: int = 50000) -> int:
        """Trim oldest persisted message events to keep at most ``max_rows`` rows."""
        if int(max_rows or 0) <= 0:
            return 0
        max_rows = max(1000, int(max_rows or 50000))
        async with self.session() as session:
            total_result = await session.execute(select(func.count(MessageEvent.id)))
            total_count = int(total_result.scalar() or 0)
            if total_count <= max_rows:
                return 0

            delete_count = total_count - max_rows
            old_ids_result = await session.execute(
                select(MessageEvent.id)
                .order_by(MessageEvent.event_time.asc(), MessageEvent.id.asc())
                .limit(delete_count)
            )
            old_ids = list(old_ids_result.scalars().all())
            if not old_ids:
                return 0

            result = await session.execute(
                delete(MessageEvent).where(MessageEvent.id.in_(old_ids))
            )
            return int(result.rowcount or 0)

    async def list_chat_message_events(
        self,
        chat_type: str,
        chat_id: str,
        limit: int = 50,
    ) -> List[MessageEvent]:
        """List persisted chat messages for a specific group/private conversation."""
        limit = max(1, min(int(limit or 50), 500))
        chat_id_str = str(chat_id)
        chat_id_int = int(chat_id_str) if chat_id_str.isdigit() else None

        async with self.session() as session:
            payload_message_type = func.json_extract(MessageEvent.payload, "$.message_type")
            payload_group_id = func.json_extract(MessageEvent.payload, "$.group_id")
            payload_user_id = func.json_extract(MessageEvent.payload, "$.user_id")
            payload_target_id = func.json_extract(MessageEvent.payload, "$.target_id")

            query = select(MessageEvent).where(
                MessageEvent.event_name.in_(["onebot.message", "onebot.message_sent"])
            )

            if chat_type == "group":
                group_conds = [payload_group_id == chat_id_str]
                if chat_id_int is not None:
                    group_conds.append(payload_group_id == chat_id_int)
                query = query.where(or_(*group_conds))
            elif chat_type == "private":
                private_conds = [payload_message_type == "private"]
                id_conds = [payload_user_id == chat_id_str, payload_target_id == chat_id_str]
                if chat_id_int is not None:
                    id_conds.extend([payload_user_id == chat_id_int, payload_target_id == chat_id_int])
                query = query.where(and_(or_(*private_conds), or_(*id_conds)))
            else:
                return []

            query = query.order_by(MessageEvent.event_time.desc(), MessageEvent.id.desc()).limit(limit)
            result = await session.execute(query)
            rows = list(result.scalars().all())
            rows.reverse()  # oldest -> newest for chat display
            return rows
    
    # ==================== AI Compatibility Stubs ====================

    async def get_ai_config(self, config_type: str, target_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        return None

    async def list_ai_configs(self, config_type: Optional[str] = None, exclude_left: bool = False) -> List[Any]:
        return []

    async def create_ai_config(self, config_type: str, target_id: Optional[str], enabled: bool = False, model_uuid: Optional[str] = None, preset_uuid: Optional[str] = None, config: Optional[Dict[str, Any]] = None, message_count: int = 0, is_left: bool = False, left_at: Optional[datetime] = None) -> Dict[str, Any]:
        return {
            "config_type": config_type,
            "target_id": target_id,
            "enabled": enabled,
            "model_uuid": model_uuid,
            "preset_uuid": preset_uuid,
            "config": config or {},
            "message_count": message_count,
            "is_left": is_left,
            "left_at": left_at.isoformat() if left_at else None,
        }

    async def update_ai_config(self, config_type: str, target_id: Optional[str], **kwargs) -> bool:
        return False

    async def delete_ai_config(self, config_type: str, target_id: Optional[str]) -> bool:
        return False

    async def batch_update_ai_configs(self, config_type: str, target_ids: List[str], **kwargs) -> int:
        return 0

    async def mark_group_left(self, group_id: str) -> bool:
        return False

    async def cleanup_expired_left_groups(self, days: int = 30) -> int:
        return 0

    async def get_llm_model(self, uuid: str) -> Optional[Dict[str, Any]]:
        return None

    async def list_llm_models(self) -> List[Any]:
        return []

    async def create_llm_model(self, uuid: str, name: str, provider: str, model_name: str, api_key: Optional[str] = None, base_url: Optional[str] = None, is_default: bool = False, supports_tools: bool = False, supports_vision: bool = False, description: Optional[str] = None, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {
            "uuid": uuid,
            "name": name,
            "provider": provider,
            "model_name": model_name,
            "base_url": base_url,
            "is_default": is_default,
            "supports_tools": supports_tools,
            "supports_vision": supports_vision,
            "description": description,
            "config": config or {},
        }

    async def update_llm_model(self, uuid: str, **kwargs) -> bool:
        return False

    async def delete_llm_model(self, uuid: str) -> bool:
        return False

    async def get_ai_preset(self, uuid: str) -> Optional[Any]:
        return None

    async def list_ai_presets(self) -> List[Any]:
        return []

    async def create_ai_preset(self, uuid: str, name: str, system_prompt: str, temperature: float = 1.0, max_tokens: int = 2000, description: Optional[str] = None, top_p: Optional[float] = None, top_k: Optional[int] = None, repetition_penalty: Optional[float] = None, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {
            "uuid": uuid,
            "name": name,
            "system_prompt": system_prompt,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "description": description,
            "top_p": top_p,
            "top_k": top_k,
            "repetition_penalty": repetition_penalty,
            "config": config or {},
        }

    async def update_ai_preset(self, uuid: str, **kwargs) -> bool:
        return False

    async def delete_ai_preset(self, uuid: str) -> bool:
        return False

    async def get_ai_memory(self, memory_type: str, target_id: str, preset_uuid: Optional[str] = None) -> Optional[Any]:
        return None

    async def list_ai_memories(self, memory_type: Optional[str] = None, target_id: Optional[str] = None) -> List[Any]:
        return []

    async def create_ai_memory(self, uuid: str, memory_type: str, target_id: str, preset_uuid: Optional[str] = None, messages: Optional[List[Dict[str, Any]]] = None, message_count: int = 0, last_active: Optional[datetime] = None) -> Dict[str, Any]:
        return {
            "uuid": uuid,
            "memory_type": memory_type,
            "target_id": target_id,
            "preset_uuid": preset_uuid,
            "messages": messages or [],
            "message_count": message_count,
            "last_active": (last_active or datetime.utcnow()).isoformat(),
        }

    async def update_ai_memory(self, uuid: str, **kwargs) -> bool:
        return False

    async def delete_ai_memory(self, uuid: str) -> bool:
        return False

    async def clear_ai_memory(self, memory_type: str, target_id: str, preset_uuid: Optional[str] = None) -> bool:
        return False

    async def get_mcp_server(self, uuid: str) -> Optional[Any]:
        return None

    async def list_mcp_servers(self, enabled_only: bool = False) -> List[Any]:
        return []

    async def create_mcp_server(self, uuid: str, name: str, mode: str, description: Optional[str] = None, enabled: bool = False, command: Optional[str] = None, args: Optional[List[str]] = None, env: Optional[Dict[str, str]] = None, url: Optional[str] = None, headers: Optional[Dict[str, str]] = None, timeout: int = 10, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {
            "uuid": uuid,
            "name": name,
            "mode": mode,
            "description": description,
            "enabled": enabled,
            "command": command,
            "args": args or [],
            "env": env or {},
            "url": url,
            "headers": headers or {},
            "timeout": timeout,
            "config": config or {},
        }

    async def update_mcp_server(self, uuid: str, **kwargs) -> bool:
        return False

    async def delete_mcp_server(self, uuid: str) -> bool:
        return False
    # ==================== Sandbox ====================

    async def list_sandboxes(self) -> List[Sandbox]:
        """Return all sandboxes ordered by last update."""
        async with self.session() as session:
            result = await session.execute(
                select(Sandbox).order_by(Sandbox.updated_at.desc())
            )
            return list(result.scalars().all())

    async def get_sandbox(self, uuid: str) -> Optional[Sandbox]:
        async with self.session() as session:
            result = await session.execute(select(Sandbox).where(Sandbox.uuid == uuid))
            return result.scalar_one_or_none()

    async def create_sandbox(
        self,
        uuid: str,
        name: str,
        mock_user_id: str,
        description: Optional[str] = None,
        mock_user_nickname: str = "",
        mock_group_id: Optional[str] = None,
        mock_group_name: Optional[str] = None,
        use_plugins: bool = True,
        use_ai: bool = True,
        ai_model_uuid: Optional[str] = None,
        ai_preset_uuid: Optional[str] = None,
        enabled: bool = True,
        **kwargs: Any,
    ) -> Sandbox:
        """Create a sandbox row."""
        async with self.session() as session:
            row = Sandbox(
                uuid=uuid,
                name=name,
                description=description,
                enabled=enabled,
                mock_user_id=mock_user_id,
                mock_user_nickname=mock_user_nickname or "",
                mock_group_id=mock_group_id or None,
                mock_group_name=mock_group_name or None,
                use_plugins=use_plugins,
                use_ai=use_ai,
                ai_model_uuid=ai_model_uuid or None,
                ai_preset_uuid=ai_preset_uuid or None,
                config=kwargs.get("config") if kwargs.get("config") is not None else {},
            )
            session.add(row)
            await session.flush()
            await session.refresh(row)
            return row

    async def update_sandbox(self, uuid: str, **fields: Any) -> Optional[Sandbox]:
        """Update sandbox fields (allows None to clear optional columns)."""
        async with self.session() as session:
            result = await session.execute(select(Sandbox).where(Sandbox.uuid == uuid))
            row = result.scalar_one_or_none()
            if not row:
                return None
            for k, v in fields.items():
                if k == "uuid" or not hasattr(row, k):
                    continue
                setattr(row, k, v)
            await session.flush()
            await session.refresh(row)
            return row

    async def delete_sandbox(self, uuid: str) -> None:
        async with self.session() as session:
            await session.execute(delete(SandboxMessage).where(SandboxMessage.sandbox_uuid == uuid))
            await session.execute(delete(Sandbox).where(Sandbox.uuid == uuid))

    async def list_sandbox_messages(self, sandbox_uuid: str, limit: int = 100) -> List[SandboxMessage]:
        async with self.session() as session:
            result = await session.execute(
                select(SandboxMessage)
                .where(SandboxMessage.sandbox_uuid == sandbox_uuid)
                .order_by(SandboxMessage.created_at.desc())
                .limit(limit)
            )
            return list(result.scalars().all())

    async def clear_sandbox_messages(self, sandbox_uuid: str) -> None:
        async with self.session() as session:
            await session.execute(delete(SandboxMessage).where(SandboxMessage.sandbox_uuid == sandbox_uuid))
            await session.execute(
                update(Sandbox)
                .where(Sandbox.uuid == sandbox_uuid)
                .values(message_count=0)
            )

    async def create_sandbox_message(
        self,
        sandbox_uuid: str,
        message_type: str,
        direction: str,
        user_id: str,
        content: str,
        user_nickname: Optional[str] = None,
        group_id: Optional[str] = None,
        group_name: Optional[str] = None,
        raw_message: Optional[str] = None,
        processed_by_plugins: bool = False,
        processed_by_ai: bool = False,
        plugin_responses: Optional[List[Any]] = None,
        ai_response: Optional[str] = None,
        has_error: bool = False,
        error_message: Optional[str] = None,
    ) -> SandboxMessage:
        async with self.session() as session:
            msg = SandboxMessage(
                sandbox_uuid=sandbox_uuid,
                message_type=message_type,
                direction=direction,
                user_id=user_id,
                user_nickname=user_nickname,
                group_id=group_id,
                group_name=group_name,
                content=content,
                raw_message=raw_message,
                processed_by_plugins=processed_by_plugins,
                processed_by_ai=processed_by_ai,
                plugin_responses=plugin_responses or [],
                ai_response=ai_response,
                has_error=has_error,
                error_message=error_message,
            )
            session.add(msg)
            await session.flush()
            await session.refresh(msg)
            sb = await session.get(Sandbox, sandbox_uuid)
            if sb:
                sb.message_count = (sb.message_count or 0) + 1
                sb.last_activity = datetime.utcnow()
            return msg

    async def update_sandbox_message(
        self,
        message_id: int,
        processed_by_plugins: Optional[bool] = None,
        processed_by_ai: Optional[bool] = None,
        plugin_responses: Optional[List[Any]] = None,
        ai_response: Optional[str] = None,
        has_error: Optional[bool] = None,
        error_message: Optional[str] = None,
    ) -> None:
        async with self.session() as session:
            msg = await session.get(SandboxMessage, message_id)
            if not msg:
                return
            if processed_by_plugins is not None:
                msg.processed_by_plugins = processed_by_plugins
            if processed_by_ai is not None:
                msg.processed_by_ai = processed_by_ai
            if plugin_responses is not None:
                msg.plugin_responses = plugin_responses
            if ai_response is not None:
                msg.ai_response = ai_response
            if has_error is not None:
                msg.has_error = has_error
            if error_message is not None:
                msg.error_message = error_message

    async def _monitor_connection_pool(self):
        """Monitor connection pool health in background."""
        try:
            while True:
                await asyncio.sleep(60)
        except asyncio.CancelledError:
            return

    async def close(self):
        """Close database connections."""
        # Stop monitoring task
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
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

