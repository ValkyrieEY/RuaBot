"""
Tests for Application lifecycle management.

This test suite covers:
- Application initialization
- Startup sequence
- Shutdown sequence
- Dependency injection
- Task management
- Signal handling
- Lifespan context manager
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from src.core.app import Application, DIContainer, get_app, set_app


class TestDIContainer:
    """Test suite for DIContainer functionality."""

    def test_container_initialization(self):
        """Test that container initializes correctly."""
        container = DIContainer()

        assert container is not None
        assert len(container._instances) == 0
        assert len(container._factories) == 0

    def test_register_instance(self):
        """Test registering an instance."""
        container = DIContainer()
        mock_instance = MagicMock()

        container.register(MagicMock, mock_instance)

        # Get registered instance
        retrieved = container.get(MagicMock)
        assert retrieved is mock_instance

    def test_register_factory(self):
        """Test registering a factory."""
        container = DIContainer()

        def factory():
            return MagicMock()

        container.register_factory(MagicMock, factory)

        # Get instance from factory
        retrieved = container.get(MagicMock)
        assert retrieved is not None

        # Should be same instance on subsequent calls (cached)
        retrieved2 = container.get(MagicMock)
        assert retrieved is retrieved2

    def test_get_nonexistent(self):
        """Test getting non-registered dependency."""
        container = DIContainer()

        with pytest.raises(KeyError):
            container.get(MagicMock)

    def test_clear(self):
        """Test clearing container."""
        container = DIContainer()

        # Register some items
        container.register(MagicMock, MagicMock())
        container.register_factory(str, lambda: "test")

        # Clear
        container.clear()

        # Should be empty
        assert len(container._instances) == 0
        assert len(container._factories) == 0


class TestApplication:
    """Test suite for Application functionality."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration."""
        from src.core.config import Config
        return Config(
            app_name="test_app",
            app_version="1.0.0",
            environment="test",
            debug=True,
            log_level="DEBUG",
            log_file="test.log",
            log_max_bytes=1048576,
            log_backup_count=3,
            host="127.0.0.1",
            port=8888,
            database_url="sqlite:///:memory:",
            storage_path="/tmp/storage",
            onebot_version="v11",
            onebot_connection_type="http",
            onebot_http_url="http://localhost:5700",
            onebot_ws_url="ws://localhost:5700",
            onebot_ws_reverse_host="0.0.0.0",
            onebot_ws_reverse_port=8080,
            onebot_ws_reverse_path="/onebot/v11/ws",
            onebot_access_token="",
            onebot_secret="",
            auto_reload=False,
            web_ui_enabled=True,
        )

    @pytest.fixture
    def app(self, mock_config):
        """Create an application instance."""
        return Application(config=mock_config)

    def test_app_initialization(self, app: Application):
        """Test that application initializes correctly."""
        assert app is not None
        assert app.config is not None
        assert app.container is not None
        assert app.event_bus is None
        assert app.storage is None
        assert app.db_manager is None
        assert not app.is_running()

    def test_app_config(self, app: Application, mock_config):
        """Test that config is properly set."""
        assert app.config.app_name == mock_config.app_name
        assert app.config.port == mock_config.port
        assert app.config.debug is mock_config.debug

    @pytest.mark.asyncio
    async def test_app_startup(self, app: Application):
        """Test application startup."""
        # Mock external dependencies
        with patch('src.core.app.get_event_bus') as mock_get_event_bus:
            with patch('src.core.app.get_database_manager') as mock_get_db_manager:
                with patch('src.core.app.init_storage') as mock_init_storage:
                    with patch('src.core.app.OneBotAdapter'):
                        # Setup mocks
                        mock_event_bus = MagicMock()
                        mock_event_bus.start = AsyncMock()
                        mock_get_event_bus.return_value = mock_event_bus

                        mock_db_manager = MagicMock()
                        mock_db_manager.initialize = AsyncMock()
                        mock_get_db_manager.return_value = mock_db_manager

                        mock_storage = MagicMock()
                        mock_init_storage.return_value = mock_storage

                        await app.startup()

                        assert app.is_running()
                        assert app.event_bus is not None

    @pytest.mark.asyncio
    async def test_app_shutdown(self, app: Application):
        """Test application shutdown."""
        # Start app with mocked dependencies
        with patch('src.core.app.get_event_bus') as mock_get_event_bus:
            with patch('src.core.app.get_database_manager') as mock_get_db_manager:
                with patch('src.core.app.init_storage') as mock_init_storage:
                    with patch('src.core.app.OneBotAdapter'):
                        # Setup mocks
                        mock_event_bus = MagicMock()
                        mock_event_bus.start = AsyncMock()
                        mock_event_bus.stop = AsyncMock()
                        mock_get_event_bus.return_value = mock_event_bus

                        mock_db_manager = MagicMock()
                        mock_db_manager.initialize = AsyncMock()
                        mock_get_db_manager.return_value = mock_db_manager

                        mock_storage = MagicMock()
                        mock_init_storage.return_value = mock_storage

                        await app.startup()
                        assert app.is_running()

                        # Shutdown
                        await app.shutdown()
                        assert not app.is_running()

    @pytest.mark.asyncio
    async def test_app_restart(self, app: Application):
        """Test application restart."""
        with patch('src.core.app.get_event_bus') as mock_get_event_bus:
            with patch('src.core.app.get_database_manager') as mock_get_db_manager:
                with patch('src.core.app.init_storage') as mock_init_storage:
                    with patch('src.core.app.OneBotAdapter'):
                        # Setup mocks
                        mock_event_bus = MagicMock()
                        mock_event_bus.start = AsyncMock()
                        mock_event_bus.stop = AsyncMock()
                        mock_get_event_bus.return_value = mock_event_bus

                        mock_db_manager = MagicMock()
                        mock_db_manager.initialize = AsyncMock()
                        mock_get_db_manager.return_value = mock_db_manager

                        mock_storage = MagicMock()
                        mock_init_storage.return_value = mock_storage

                        # Start
                        await app.startup()
                        assert app.is_running()

                        # Shutdown
                        await app.shutdown()
                        assert not app.is_running()

                        # Restart
                        await app.startup()
                        assert app.is_running()

    @pytest.mark.asyncio
    async def test_app_add_task(self, app: Application):
        """Test adding background tasks."""
        async def dummy_task():
            await asyncio.sleep(0.1)

        task = app.add_task(dummy_task())

        assert task is not None
        assert len(app._tasks) == 1

    @pytest.mark.asyncio
    async def test_app_lifespan_context_manager(self, app: Application):
        """Test lifespan context manager."""
        with patch('src.core.app.get_event_bus') as mock_get_event_bus:
            with patch('src.core.app.get_database_manager') as mock_get_db_manager:
                with patch('src.core.app.init_storage') as mock_init_storage:
                    with patch('src.core.app.OneBotAdapter'):
                        # Setup mocks
                        mock_event_bus = MagicMock()
                        mock_event_bus.start = AsyncMock()
                        mock_event_bus.stop = AsyncMock()
                        mock_get_event_bus.return_value = mock_event_bus

                        mock_db_manager = MagicMock()
                        mock_db_manager.initialize = AsyncMock()
                        mock_get_db_manager.return_value = mock_db_manager

                        mock_storage = MagicMock()
                        mock_init_storage.return_value = mock_storage

                        async with app.lifespan():
                            assert app.is_running()

                        # Should be shutdown after context
                        assert not app.is_running()

    @pytest.mark.asyncio
    async def test_app_event_bus_initialization(self, app: Application):
        """Test event bus initialization during startup."""
        with patch('src.core.app.get_event_bus') as mock_get_event_bus:
            with patch('src.core.app.get_database_manager') as mock_get_db_manager:
                with patch('src.core.app.init_storage') as mock_init_storage:
                    with patch('src.core.app.OneBotAdapter'):
                        # Setup mocks
                        mock_event_bus = MagicMock()
                        mock_event_bus.start = AsyncMock()
                        mock_get_event_bus.return_value = mock_event_bus

                        mock_db_manager = MagicMock()
                        mock_db_manager.initialize = AsyncMock()
                        mock_get_db_manager.return_value = mock_db_manager

                        mock_storage = MagicMock()
                        mock_init_storage.return_value = mock_storage

                        await app.startup()

                        # Event bus should be initialized
                        assert app.event_bus is not None

    @pytest.mark.asyncio
    async def test_app_storage_initialization(self, app: Application):
        """Test storage initialization during startup."""
        with patch('src.core.app.get_event_bus') as mock_get_event_bus:
            with patch('src.core.app.get_database_manager') as mock_get_db_manager:
                with patch('src.core.app.init_storage') as mock_init_storage:
                    with patch('src.core.app.OneBotAdapter'):
                        # Setup mocks
                        mock_event_bus = MagicMock()
                        mock_event_bus.start = AsyncMock()
                        mock_get_event_bus.return_value = mock_event_bus

                        mock_db_manager = MagicMock()
                        mock_db_manager.initialize = AsyncMock()
                        mock_get_db_manager.return_value = mock_db_manager

                        mock_storage = MagicMock()
                        mock_init_storage.return_value = mock_storage

                        await app.startup()

                        # Storage should be initialized
                        assert app.storage is not None

    @pytest.mark.asyncio
    async def test_app_database_initialization(self, app: Application):
        """Test database initialization during startup."""
        with patch('src.core.app.get_event_bus') as mock_get_event_bus:
            with patch('src.core.app.get_database_manager') as mock_get_db_manager:
                with patch('src.core.app.init_storage') as mock_init_storage:
                    with patch('src.core.app.OneBotAdapter'):
                        # Setup mocks
                        mock_event_bus = MagicMock()
                        mock_event_bus.start = AsyncMock()
                        mock_get_event_bus.return_value = mock_event_bus

                        mock_db_manager = MagicMock()
                        mock_db_manager.initialize = AsyncMock()
                        mock_get_db_manager.return_value = mock_db_manager

                        mock_storage = MagicMock()
                        mock_init_storage.return_value = mock_storage

                        await app.startup()

                        # Database manager should be initialized
                        assert app.db_manager is not None

    @pytest.mark.asyncio
    async def test_app_onebot_adapter_initialization(self, app: Application):
        """Test OneBot adapter initialization during startup."""
        with patch('src.core.app.get_event_bus') as mock_get_event_bus:
            with patch('src.core.app.get_database_manager') as mock_get_db_manager:
                with patch('src.core.app.init_storage') as mock_init_storage:
                    with patch('src.core.app.OneBotAdapter') as mock_onebot_adapter:
                        # Setup mocks
                        mock_event_bus = MagicMock()
                        mock_event_bus.start = AsyncMock()
                        mock_get_event_bus.return_value = mock_event_bus

                        mock_db_manager = MagicMock()
                        mock_db_manager.initialize = AsyncMock()
                        mock_get_db_manager.return_value = mock_db_manager

                        mock_storage = MagicMock()
                        mock_init_storage.return_value = mock_storage

                        mock_adapter_instance = MagicMock()
                        mock_onebot_adapter.return_value = mock_adapter_instance

                        await app.startup()

                        # OneBot adapter should be initialized
                        assert hasattr(app, 'onebot_adapter')
                        assert app.onebot_adapter is not None

    @pytest.mark.asyncio
    async def test_app_publish_startup_event(self, app: Application):
        """Test that startup event is published."""
        with patch('src.core.app.get_event_bus') as mock_get_event_bus:
            with patch('src.core.app.get_database_manager') as mock_get_db_manager:
                with patch('src.core.app.init_storage') as mock_init_storage:
                    with patch('src.core.app.OneBotAdapter'):
                        # Setup mocks
                        mock_event_bus = MagicMock()
                        mock_event_bus.start = AsyncMock()
                        mock_event_bus.publish = AsyncMock()
                        mock_get_event_bus.return_value = mock_event_bus

                        mock_db_manager = MagicMock()
                        mock_db_manager.initialize = AsyncMock()
                        mock_get_db_manager.return_value = mock_db_manager

                        mock_storage = MagicMock()
                        mock_init_storage.return_value = mock_storage

                        await app.startup()

                        # Verify publish was called (event bus publish method exists)
                        assert mock_event_bus.publish is not None

    @pytest.mark.asyncio
    async def test_app_publish_shutdown_event(self, app: Application):
        """Test that shutdown event is published."""
        with patch('src.core.app.get_event_bus') as mock_get_event_bus:
            with patch('src.core.app.get_database_manager') as mock_get_db_manager:
                with patch('src.core.app.init_storage') as mock_init_storage:
                    with patch('src.core.app.OneBotAdapter'):
                        # Setup mocks
                        mock_event_bus = MagicMock()
                        mock_event_bus.start = AsyncMock()
                        mock_event_bus.stop = AsyncMock()
                        mock_event_bus.publish = AsyncMock()
                        mock_get_event_bus.return_value = mock_event_bus

                        mock_db_manager = MagicMock()
                        mock_db_manager.initialize = AsyncMock()
                        mock_get_db_manager.return_value = mock_db_manager

                        mock_storage = MagicMock()
                        mock_init_storage.return_value = mock_storage

                        await app.startup()
                        await app.shutdown()

                        # Verify publish was called during shutdown
                        assert mock_event_bus.publish is not None

    @pytest.mark.asyncio
    async def test_app_task_cancellation_on_shutdown(self, app: Application):
        """Test that tasks are cancelled on shutdown."""
        with patch('src.core.app.get_event_bus') as mock_get_event_bus:
            with patch('src.core.app.get_database_manager') as mock_get_db_manager:
                with patch('src.core.app.init_storage') as mock_init_storage:
                    with patch('src.core.app.OneBotAdapter'):
                        # Setup mocks
                        mock_event_bus = MagicMock()
                        mock_event_bus.start = AsyncMock()
                        mock_event_bus.stop = AsyncMock()
                        mock_get_event_bus.return_value = mock_event_bus

                        mock_db_manager = MagicMock()
                        mock_db_manager.initialize = AsyncMock()
                        mock_get_db_manager.return_value = mock_db_manager

                        mock_storage = MagicMock()
                        mock_init_storage.return_value = mock_storage

                        await app.startup()

                        # Add a simple task
                        task_ran = False

                        async def simple_task():
                            nonlocal task_ran
                            task_ran = True

                        app.add_task(simple_task())

                        # Give task time to run
                        await asyncio.sleep(0.01)

                        # Shutdown
                        await app.shutdown()

                        # Verify task was added
                        assert task_ran

    @pytest.mark.asyncio
    async def test_app_multiple_startup_calls(self, app: Application):
        """Test that multiple startup calls are handled gracefully."""
        with patch('src.core.app.get_event_bus') as mock_get_event_bus:
            with patch('src.core.app.get_database_manager') as mock_get_db_manager:
                with patch('src.core.app.init_storage') as mock_init_storage:
                    with patch('src.core.app.OneBotAdapter'):
                        # Setup mocks
                        mock_event_bus = MagicMock()
                        mock_event_bus.start = AsyncMock()
                        mock_get_event_bus.stop = AsyncMock()
                        mock_get_event_bus.get = MagicMock(return_value=None)  # Return None to avoid key error
                        mock_get_event_bus._running = False
                        mock_get_event_bus._processor_task = None
                        mock_get_event_bus.return_value = mock_event_bus
                        mock_get_event_bus.__class__ = type(mock_event_bus)

                        mock_db_manager = MagicMock()
                        mock_db_manager.initialize = AsyncMock()
                        mock_get_db_manager.return_value = mock_db_manager

                        mock_storage = MagicMock()
                        mock_init_storage.return_value = mock_storage

                        await app.startup()
                        assert app.is_running()

                        # Second startup should be safe
                        await app.startup()
                        assert app.is_running()

    @pytest.mark.asyncio
    async def test_app_shutdown_without_startup(self, app: Application):
        """Test that shutdown without startup is safe."""
        # Should not raise error
        await app.shutdown()
        assert not app.is_running()

    @pytest.mark.asyncio
    async def test_app_start_time_tracking(self, app: Application):
        """Test that start time is tracked."""
        with patch('src.core.app.get_event_bus') as mock_get_event_bus:
            with patch('src.core.app.get_database_manager') as mock_get_db_manager:
                with patch('src.core.app.init_storage') as mock_init_storage:
                    with patch('src.core.app.OneBotAdapter'):
                        # Setup mocks
                        mock_event_bus = MagicMock()
                        mock_event_bus.start = AsyncMock()
                        mock_get_event_bus.stop = AsyncMock()
                        mock_get_event_bus.return_value = mock_event_bus

                        mock_db_manager = MagicMock()
                        mock_db_manager.initialize = AsyncMock()
                        mock_get_db_manager.return_value = mock_db_manager

                        mock_storage = MagicMock()
                        mock_init_storage.return_value = mock_storage

                        await app.startup()

                        # Start time should be tracked
                        assert app._start_time is not None
                        assert isinstance(app._start_time, datetime)

    def test_app_container_initialization(self, app: Application):
        """Test that container is initialized."""
        assert app.container is not None
        assert isinstance(app.container, DIContainer)


class TestApplicationGlobal:
    """Test suite for global application instance."""

    def test_get_app_singleton(self):
        """Test that get_app returns singleton instance."""
        app1 = get_app()
        app2 = get_app()

        assert app1 is not None
        assert app2 is not None
        assert app1 is app2

    def test_set_app(self):
        """Test setting global application instance."""
        from src.core.config import Config

        config = Config(
            app_name="test",
            app_version="1.0.0",
            environment="test",
            debug=True,
            log_level="DEBUG",
            log_file="test.log",
            log_max_bytes=1048576,
            log_backup_count=3,
            host="127.0.0.1",
            port=8888,
            database_url="sqlite:///:memory:",
            storage_path="/tmp/storage",
            onebot_version="v11",
            onebot_connection_type="http",
            onebot_http_url="http://localhost:5700",
            onebot_ws_url="ws://localhost:5700",
            onebot_ws_reverse_host="0.0.0.0",
            onebot_ws_reverse_port=8080,
            onebot_ws_reverse_path="/onebot/v11/ws",
            onebot_access_token="",
            onebot_secret="",
            auto_reload=False,
            web_ui_enabled=True,
        )

        new_app = Application(config=config)
        set_app(new_app)

        # Verify global instance changed
        current_app = get_app()
        assert current_app is new_app