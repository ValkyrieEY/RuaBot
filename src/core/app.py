"""Application lifecycle management and dependency injection."""

import asyncio
from typing import Any, Dict, Optional, Type
from contextlib import asynccontextmanager
from datetime import datetime

from .config import Config, get_config
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
        self._running = False
        self._tasks: list[asyncio.Task] = []
        self._start_time: Optional[datetime] = None

        # Setup logger
        setup_logger(
            name="xiaoyi_qq",
            level=self.config.log_level,
            log_file=self.config.log_file
        )
        
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
            
            await self.event_bus.publish(
                event_name,
                plugin_payload,  # Pass raw OneBot format to plugins
                source="onebot"
            )
            logger.debug(f"Event published: {event_name}")
        
        self.onebot_adapter.on_event(handle_onebot_event)
        
        # Start adapter
        await self.onebot_adapter.start()
        
        # Initialize AI message handler
        try:
            from ..ai.message_handler import AIMessageHandler
            self.ai_message_handler = AIMessageHandler()
            await self.ai_message_handler.initialize()
            logger.info("AI message handler initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize AI message handler: {e}", exc_info=True)
            logger.info("AI message handler disabled due to initialization error")
        
        # Initialize plugin system
        try:
            from ..plugins.runtime import PluginRuntimeConnector
            self.plugin_connector = PluginRuntimeConnector(
                event_bus=self.event_bus,
                db_manager=self.db_manager,
                app=self  # Pass app instance for OneBot access
            )
            await self.plugin_connector.initialize()
            logger.info("Plugin system initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize plugin system: {e}", exc_info=True)
            logger.info("Plugin system disabled due to initialization error")

        # Initialize and start maintenance tasks (Dream, Expression Check, Expression Reflect)
        try:
            from ..ai.model_manager import ModelManager
            from ..ai.dream import init_dream_scheduler
            from ..ai.expression_auto_checker import start_expression_auto_check_scheduler
            from ..ai.expression_reflector import get_expression_reflector
            
            model_manager = ModelManager()
            await model_manager.initialize()
            
            # Get default model for maintenance tasks
            default_model = await model_manager.get_default_model()
            if default_model:
                model_with_secret = await model_manager.get_model_with_secret(default_model['uuid'])
                if model_with_secret:
                    from ..ai.llm_client import LLMClient
                    llm_client = LLMClient(
                        api_key=model_with_secret.get('api_key', ''),
                        base_url=model_with_secret.get('base_url', ''),
                        model_name=model_with_secret.get('model_name', ''),
                        provider=model_with_secret.get('provider', 'openai')
                    )
                    
                    # Start Dream Scheduler
                    try:
                        dream_scheduler = init_dream_scheduler(
                            llm_client=llm_client,
                            bot_name="AI助手",
                            enabled=True,
                            first_delay_seconds=300,  # 5分钟后首次运行
                            interval_minutes=30  # 每30分钟运行一次
                        )
                        self.add_task(dream_scheduler.start_background())
                        logger.info("Dream scheduler started")
                    except Exception as e:
                        logger.error(f"Failed to start dream scheduler: {e}", exc_info=True)
                    
                    # Start Expression Auto Check Scheduler
                    try:
                        self.add_task(start_expression_auto_check_scheduler(
                            llm_client=llm_client,
                            interval_minutes=60,  # 每小时检查一次
                            batch_size=10
                        ))
                        logger.info("Expression auto check scheduler started")
                    except Exception as e:
                        logger.error(f"Failed to start expression auto check: {e}", exc_info=True)
                    
                    # Start Expression Reflector (periodic)
                    try:
                        reflector = get_expression_reflector()
                        async def periodic_reflect():
                            while True:
                                await asyncio.sleep(7200)  # 每2小时反思一次
                                try:
                                    await reflector.reflect_on_expressions(
                                        llm_client=llm_client,
                                        min_usage_count=5,
                                        limit=30
                                    )
                                except Exception as e:
                                    logger.error(f"Expression reflection failed: {e}", exc_info=True)
                        self.add_task(periodic_reflect())
                        logger.info("Expression reflector started")
                    except Exception as e:
                        logger.error(f"Failed to start expression reflector: {e}", exc_info=True)
                else:
                    logger.warning("Default model not found with secret, maintenance tasks disabled")
            else:
                logger.warning("No default model configured, maintenance tasks disabled")
        except Exception as e:
            logger.error(f"Failed to start maintenance tasks: {e}", exc_info=True)
            logger.info("Maintenance tasks disabled due to error")

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

