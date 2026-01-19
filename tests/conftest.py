"""Pytest configuration and fixtures."""

import pytest
import asyncio
from pathlib import Path
import tempfile
import shutil

from src.core.app import Application
from src.core.config import Config
from src.core.event_bus import EventBus
from src.core.storage import MemoryStorage
from src.plugins.manager import PluginManager


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_config():
    """Create test configuration."""
    return Config(
        app_name="Test App",
        environment="test",
        debug=True,
        database_url="sqlite+aiosqlite:///:memory:",
        log_level="DEBUG",
        plugin_dir="./test_plugins",
    )


@pytest.fixture
async def app(test_config):
    """Create test application."""
    application = Application(config=test_config)
    await application.startup()
    yield application
    await application.shutdown()


@pytest.fixture
async def event_bus():
    """Create test event bus."""
    bus = EventBus()
    await bus.start()
    yield bus
    await bus.stop()


@pytest.fixture
def storage():
    """Create test storage."""
    return MemoryStorage()


@pytest.fixture
def temp_plugin_dir():
    """Create temporary plugin directory."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
async def plugin_manager(temp_plugin_dir, event_bus):
    """Create test plugin manager."""
    manager = PluginManager(str(temp_plugin_dir), event_bus=event_bus)
    yield manager

