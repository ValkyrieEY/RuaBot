"""Application lifecycle management and dependency injection."""

import asyncio
import sys
import tomllib
from pathlib import Path
from typing import Any, Dict, Optional, Type
from contextlib import asynccontextmanager
from datetime import datetime

from .config import Config, get_config, get_config_file_path
from .logger import setup_logger, get_logger
from .event_bus import EventBus, get_event_bus
from .storage import Storage, init_storage
from .database import DatabaseManager, get_database_manager

logger = get_logger(__name__)


class DIContainer:
    """Simple dependency injection container."""

    def __init__(self):
        self._instances: Dict[Type, Any] = {}
        self._factories: Dict[Type, Any] = {}

    def register(self, interface: Type, instance: Any) -> None:
        """Register an instance for an interface."""
        self._instances[interface] = instance
        logger.debug("Registered instance", interface=interface.__name__)

    def register_factory(self, interface: Type, factory: Any) -> None:
        """Register a factory function for an interface."""
        self._factories[interface] = factory
        logger.debug("Registered factory", interface=interface.__name__)

    def get(self, interface: Type) -> Any:
        """Get an instance for an interface."""
        if interface in self._instances:
            return self._instances[interface]
        
        if interface in self._factories:
            instance = self._factories[interface]()
            self._instances[interface] = instance
            return instance
        
        raise KeyError(f"No instance or factory registered for {interface.__name__}")

    def clear(self) -> None:
        """Clear all registered instances and factories."""
        self._instances.clear()
        self._factories.clear()


class Application:
    """Main application class with lifecycle management."""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()
        self.container = DIContainer()
        self.event_bus: Optional[EventBus] = None
        self.storage: Optional[Storage] = None
        self.db_manager: Optional[DatabaseManager] = None
        self.plugin_connector: Optional[Any] = None
        self.blocking_task_pool: Optional[Any] = None
        self._running = False
        self._tasks: list[asyncio.Task] = []
        self._start_time: Optional[datetime] = None
        
        # Setup signal handlers for graceful shutdown
        self._setup_signal_handlers()

        # Logger is already setup in src/main.py, no need to setup again
        # This avoids overwriting the log level configuration
        
        logger.info(
            "Application initialized",
            app_name=self.config.app_name,
            version=self.config.app_version,
            environment=self.config.environment
        )

    async def startup(self) -> None:
        """Initialize all application components."""
        if self._running:
            logger.warning("Application already running")
            return

        logger.info("Starting application...")
        
        # Initialize blocking task pool early (before plugins load)
        if getattr(self.config, 'blocking_task_pool_enabled', True):
            try:
                from .blocking_task_pool import get_blocking_task_pool_manager

                self.blocking_task_pool = get_blocking_task_pool_manager(
                    getattr(self.config, 'blocking_task_pool_max_workers', 0)
                )
                logger.info(
                    "Blocking task pool initialized",
                    configured_max_workers=getattr(self.config, 'blocking_task_pool_max_workers', 0),
                )
            except Exception as e:
                logger.warning(f"Failed to initialize blocking task pool: {e}")

        # Initialize event bus
        self.event_bus = get_event_bus()
        await self.event_bus.start()
        self.container.register(EventBus, self.event_bus)

        # Initialize storage
        db_path = None
        if "sqlite" in self.config.database_url:
            db_path = self.config.database_url.split("///")[-1]
        
        self.storage = await init_storage(db_path)
        self.container.register(Storage, self.storage)

        # Initialize database for plugins
        self.db_manager = get_database_manager()
        await self.db_manager.initialize()
        logger.info("Plugin database initialized")

        # Initialize OneBot adapter
        from ..protocol.onebot import OneBotAdapter
        onebot_config = {
            "version": self.config.onebot_version,
            "connection_type": self.config.onebot_connection_type,
            "http_url": self.config.onebot_http_url,
            "ws_url": self.config.onebot_ws_url,
            "ws_reverse_host": self.config.onebot_ws_reverse_host,
            "ws_reverse_port": self.config.onebot_ws_reverse_port,
            "ws_reverse_path": self.config.onebot_ws_reverse_path,
            "access_token": self.config.onebot_access_token,
            "secret": self.config.onebot_secret,
        }
        self.onebot_adapter = OneBotAdapter(onebot_config)
        
        # Register event handler
        async def handle_onebot_event(event):
            # Forward OneBot events to event bus
            event_name = f"onebot.{event['type']}"
            logger.debug(f"Publishing OneBot event to EventBus: {event_name}, payload: {event}")
            
            # For plugins, use the raw OneBot format (not our wrapped format)
            # Plugins expect: {'message_type': 'group', 'raw_message': '...', ...}
            # Not: {'type': 'message', 'envelope': {...}, 'raw': {...}}
            plugin_payload = event.get('raw', event)  # Use raw OneBot data if available
            
            # For message events, use event context system (allows plugins to modify/block)
            if event.get('type') == 'message':
                from ..core.event_context import EventContext
                
                # Cache images in message (non-blocking)
                try:
                    from ..ui.image_cache import get_image_cache_manager
                    image_cache = get_image_cache_manager()
                    raw_message = plugin_payload.get('raw_message', '')
                    if raw_message and '[CQ:image' in raw_message:
                        # Extract and cache images asynchronously (don't wait)
                        asyncio.create_task(
                            image_cache.extract_and_cache_images(
                                raw_message,
                                self.onebot_adapter if hasattr(self, 'onebot_adapter') else None
                            )
                        )
                except Exception as e:
                    logger.debug(f"Failed to cache images in message: {e}")
                
                # Create event context for message received
                ctx = EventContext(
                    event_name='message.received',
                    event_data=plugin_payload,
                    source="onebot"
                )
                
                # Emit with context (allows plugins to modify/block)
                modified_ctx = ctx  # Default to original context
                if not hasattr(self, 'plugin_connector') or not self.plugin_connector:
                    logger.warning("plugin_connector not available, skipping plugin event processing")
                else:
                    logger.debug(f"Emitting message.received event to plugins: {plugin_payload.get('raw_message', '')[:50]}")
                    try:
                        modified_ctx = await self.plugin_connector.emit_event_with_context(
                            ctx,
                            bound_plugins=None  # All enabled plugins
                        )
                        
                        # If None is returned, it means event was blocked or error occurred
                        if modified_ctx is None:
                            logger.info("Message blocked by plugin or error occurred")
                            return
                    except Exception as e:
                        logger.error(f"Error emitting event to plugins: {e}", exc_info=True)
                        # Continue processing even if plugin handling fails
                        modified_ctx = ctx  # Use original context on error
                    
                    # Check if default behavior was prevented
                    if modified_ctx.is_prevented_default():
                        logger.info("Message blocked by plugin (prevent_default)")
                        return
                    
                    # Use modified data if changed
                    if modified_ctx.is_modified():
                        plugin_payload = modified_ctx.event_data

                try:
                    from ..assistant.runtime import get_assistant_runtime

                    asyncio.create_task(
                        get_assistant_runtime().handle_message(
                            plugin_payload if isinstance(plugin_payload, dict) else {},
                            self.onebot_adapter,
                        )
                    )
                except Exception as e:
                    logger.warning(f"Failed to schedule Assistant runtime: {e}")

            # For notice events, also use event context system (but don't block by default)
            elif event.get('type') == 'notice':
                from ..core.event_context import EventContext
                
                # Create event context for notice received
                ctx = EventContext(
                    event_name='notice.received',
                    event_data=plugin_payload,
                    source="onebot"
                )
                
                # Emit with context (allows plugins to modify, but notices usually shouldn't be blocked)
                if hasattr(self, 'plugin_connector') and self.plugin_connector:
                    modified_ctx = await self.plugin_connector.emit_event_with_context(
                        ctx,
                        bound_plugins=None  # All enabled plugins
                    )
                    
                    # Use modified data if changed (but don't block notices)
                    if modified_ctx and modified_ctx.is_modified():
                        plugin_payload = modified_ctx.event_data
            
            # Also publish to regular event bus subscribers
            published_event_id = await self.event_bus.publish(
                event_name,
                plugin_payload,  # Pass raw OneBot format to plugins
                source="onebot"
            )
            # Persist message log events for WebUI history recovery across WS disconnects.
            if event.get('type') in ('message', 'notice', 'request') and self.db_manager:
                try:
                    await self.db_manager.create_message_event(
                        event_id=published_event_id,
                        event_name=event_name,
                        payload=plugin_payload if isinstance(plugin_payload, dict) else {},
                        source="onebot",
                    )
                except Exception as e:
                    logger.warning(f"Failed to persist message event: {e}")
            logger.debug(f"Event published: {event_name}")
        
        self.onebot_adapter.on_event(handle_onebot_event)
        
        # Start adapter
        await self.onebot_adapter.start()
        
        # Initialize image cache manager and cleanup on startup
        try:
            from ..ui.image_cache import get_image_cache_manager
            image_cache = get_image_cache_manager()
            retention_days = max(1, int(getattr(self.config, "message_event_retention_days", 30)))
            await image_cache.cleanup_old_images(max_age_hours=retention_days * 24)
            logger.info("Media cache manager initialized", retention_days=retention_days)
        except Exception as e:
            logger.warning(f"Failed to initialize image cache manager: {e}")
        
        # Initialize plugin system
        if not getattr(self.config, 'plugin_auto_load', True):
            logger.info("Plugin auto-load is disabled (plugins.auto_load = false in config.toml), skipping plugin system initialization")
        else:
            try:
                from ..plugins.runtime import PluginRuntimeConnector
                from ..plugins.interceptor import ExecutionMode
                
                # Read interceptor configuration from TOML file directly
                # since Config is a Pydantic model and doesn't support .get() method
                interceptor_config = {}
                try:
                    toml_file = get_config_file_path()
                    if toml_file.exists():
                        with open(toml_file, "rb") as f:
                            toml_data = tomllib.load(f)
                            plugins_config = toml_data.get('plugins', {})
                            interceptor_config = plugins_config.get('interceptor', {})
                except Exception as e:
                    logger.warning(f"Failed to read interceptor config from TOML: {e}")
                
                execution_mode_str = interceptor_config.get('execution_mode', 'hybrid')
                
                # Convert string to ExecutionMode enum
                execution_mode_map = {
                    'serial': ExecutionMode.SERIAL,
                    'parallel': ExecutionMode.PARALLEL,
                    'hybrid': ExecutionMode.HYBRID
                }
                execution_mode = execution_mode_map.get(
                    execution_mode_str.lower(),
                    ExecutionMode.HYBRID
                )
                
                self.plugin_connector = PluginRuntimeConnector(
                    event_bus=self.event_bus,
                    db_manager=self.db_manager,
                    app=self,  # Pass app instance for OneBot access
                    interceptor_mode=execution_mode
                )
                
                # Configure circuit breaker and timeouts if specified
                if 'circuit_breaker_threshold' in interceptor_config:
                    self.plugin_connector.interceptor_registry.configure_circuit_breaker(
                        threshold=interceptor_config.get('circuit_breaker_threshold', 3),
                        duration=interceptor_config.get('circuit_breaker_duration', 30.0)
                    )
                
                if 'base_timeout' in interceptor_config:
                    self.plugin_connector.interceptor_registry.configure_timeouts(
                        base_timeout=interceptor_config.get('base_timeout', 3.0),
                        max_timeout=interceptor_config.get('max_timeout', 10.0)
                    )
                
                await self.plugin_connector.initialize()
                logger.info(
                    f"Plugin system initialized successfully "
                    f"(interceptor mode: {execution_mode.value})"
                )
            except Exception as e:
                logger.error(f"Failed to initialize plugin system: {e}", exc_info=True)
                logger.info("Plugin system disabled due to initialization error")

        # Wire sandbox manager to plugins (for Web UI sandbox testing)
        try:
            from .sandbox.sandbox_manager import get_sandbox_manager
            _sm = get_sandbox_manager()
            if getattr(self, "plugin_connector", None):
                _sm.set_plugin_connector(self.plugin_connector)
            logger.info("Sandbox manager connected to plugin runtime")
        except Exception as e:
            logger.warning(f"Sandbox manager wiring skipped: {e}")
        
        # Start group data cleanup scheduler (runs daily)
        try:
            async def cleanup_expired_groups():
                """Cleanup expired left group data daily."""
                while True:
                    await asyncio.sleep(86400)  # 24
                    try:
                        count = await self.db_manager.cleanup_expired_left_groups(days=30)
                        if count > 0:
                            logger.info(f"Auto cleanup: deleted {count} expired left group configurations")
                    except Exception as e:
                        logger.error(f"Failed to cleanup expired groups: {e}", exc_info=True)
            
            self.add_task(cleanup_expired_groups())
            logger.info("Group data cleanup scheduler started (runs daily)")
        except Exception as e:
            logger.error(f"Failed to start group cleanup scheduler: {e}", exc_info=True)

        # Cleanup persisted message events daily to control DB size.
        try:
            retention_days = max(1, int(getattr(self.config, "message_event_retention_days", 30)))
            max_rows = int(getattr(self.config, "message_event_max_rows", 0))
            interval_seconds = max(
                300,
                int(getattr(self.config, "message_event_cleanup_interval_seconds", 86400))
            )

            async def cleanup_message_events():
                while True:
                    try:
                        deleted_by_days = await self.db_manager.cleanup_message_events(
                            retention_days=retention_days
                        )
                        deleted_by_cap = 0
                        if max_rows > 0:
                            deleted_by_cap = await self.db_manager.truncate_message_events(
                                max_rows=max_rows
                            )
                        deleted_cached_media = 0
                        try:
                            from ..ui.image_cache import get_image_cache_manager

                            image_cache = get_image_cache_manager()
                            deleted_cached_media = await image_cache.cleanup_old_images(
                                max_age_hours=retention_days * 24
                            )
                        except Exception as media_cleanup_error:
                            logger.warning(
                                f"Failed to cleanup cached media: {media_cleanup_error}"
                            )
                        deleted = deleted_by_days + deleted_by_cap
                        if deleted > 0 or deleted_cached_media > 0:
                            logger.info(
                                "Message event/media cleanup done",
                                deleted=deleted,
                                deleted_by_days=deleted_by_days,
                                deleted_by_cap=deleted_by_cap,
                                deleted_cached_media=deleted_cached_media,
                                retention_days=retention_days,
                                max_rows=max_rows,
                            )
                    except Exception as e:
                        logger.error(f"Failed to cleanup message events: {e}", exc_info=True)
                    await asyncio.sleep(interval_seconds)

            self.add_task(cleanup_message_events())
            logger.info(
                "Message event cleanup scheduler started",
                retention_days=retention_days,
                max_rows=max_rows if max_rows > 0 else "disabled",
                interval_seconds=interval_seconds,
            )
        except Exception as e:
            logger.error(f"Failed to start message event cleanup scheduler: {e}", exc_info=True)

        # Publish startup event
        await self.event_bus.publish(
            "app.startup",
            {"config": self.config.model_dump()},
            source="app"
        )

        self._running = True
        self._start_time = datetime.now()
        logger.info("Application started successfully")

    async def shutdown(self) -> None:
        """Cleanup all application components."""
        if not self._running:
            return

        logger.info("Shutting down application...")

        # Publish shutdown event
        if self.event_bus:
            await self.event_bus.publish(
                "app.shutdown",
                {},
                source="app"
            )

        # Stop OneBot adapter
        if hasattr(self, 'onebot_adapter'):
            await self.onebot_adapter.stop()

        # Stop plugin system
        if self.plugin_connector:
            await self.plugin_connector.dispose()
        
        # Cancel all tasks
        for task in self._tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Stop event bus
        if self.event_bus:
            await self.event_bus.stop()

        # Close storage
        if self.storage:
            await self.storage.close()

        # Shutdown blocking task pool
        if self.blocking_task_pool:
            try:
                from .blocking_task_pool import shutdown_blocking_task_pool

                shutdown_blocking_task_pool(wait=True)
                self.blocking_task_pool = None
            except Exception as e:
                logger.warning(f"Failed to shutdown blocking task pool: {e}")

        self._running = False
        logger.info("Application shut down successfully")

    def add_task(self, coro) -> asyncio.Task:
        """Add a background task."""
        task = asyncio.create_task(coro)
        self._tasks.append(task)
        return task

    @asynccontextmanager
    async def lifespan(self):
        """Application lifespan context manager."""
        await self.startup()
        try:
            yield self
        finally:
            await self.shutdown()

    def is_running(self) -> bool:
        """Check if application is running."""
        return self._running
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        import signal
        
        def signal_handler(signum, frame):
            """Handle termination signals."""
            logger.info(f"Received signal {signum}, initiating shutdown...")
            # Create a task to shutdown gracefully
            if self._running:
                asyncio.create_task(self.shutdown())
        
        # Register signal handlers (Unix only, Windows uses different mechanism)
        if sys.platform != 'win32':
            signal.signal(signal.SIGTERM, signal_handler)
            signal.signal(signal.SIGINT, signal_handler)


# Global application instance
_app: Optional[Application] = None


def get_app() -> Application:
    """Get the global application instance."""
    global _app
    if _app is None:
        _app = Application()
    return _app


def set_app(app: Application) -> None:
    """Set the global application instance."""
    global _app
    _app = app

