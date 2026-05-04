"""
Tests for the current DatabaseManager surface.

This intentionally covers the live plugin, binary storage, and sandbox paths.
The legacy AI configuration/memory APIs were removed with the old AI framework.
"""
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest

from src.core.database import DatabaseManager, get_database_manager


class TestDatabaseManager:
    """Test suite for DatabaseManager functionality."""

    @pytest.fixture
    def temp_db_path(self) -> Path:
        """Create a temporary database path."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            return Path(f.name)

    @pytest.fixture
    async def db_manager(self, temp_db_path: Path) -> DatabaseManager:
        """Create a database manager instance."""
        manager = DatabaseManager(db_path=str(temp_db_path))
        await manager.initialize()
        yield manager
        await manager.close()
        if temp_db_path.exists():
            temp_db_path.unlink()

    @pytest.mark.asyncio
    async def test_database_initialization(self, db_manager: DatabaseManager):
        """Test that database initializes correctly."""
        assert db_manager is not None
        assert db_manager.db_path is not None

    @pytest.mark.asyncio
    async def test_plugin_setting_crud(self, db_manager: DatabaseManager):
        """Test creating, updating, fetching, listing, and deleting plugin settings."""
        created = await db_manager.create_plugin_setting(
            "XQNEXT",
            "sample_plugin",
            enabled=True,
            priority=50,
            config={"mode": "test"},
        )

        assert created.plugin_author == "XQNEXT"
        assert created.plugin_name == "sample_plugin"
        assert created.config == {"mode": "test"}

        assert await db_manager.update_plugin_setting(
            "XQNEXT",
            "sample_plugin",
            enabled=False,
            priority=10,
        )

        fetched = await db_manager.get_plugin_setting("XQNEXT", "sample_plugin")
        assert fetched is not None
        assert fetched.enabled is False
        assert fetched.priority == 10

        listed = await db_manager.list_plugin_settings()
        assert [row.plugin_name for row in listed] == ["sample_plugin"]

        assert await db_manager.delete_plugin_setting("XQNEXT", "sample_plugin")
        assert await db_manager.get_plugin_setting("XQNEXT", "sample_plugin") is None

    @pytest.mark.asyncio
    async def test_binary_storage_lifecycle(self, db_manager: DatabaseManager):
        """Test binary storage helpers used by plugin uploads."""
        assert await db_manager.set_binary("plugin", "XQNEXT/sample", "avatar", b"one")
        assert await db_manager.get_binary("plugin", "XQNEXT/sample", "avatar") == b"one"

        assert await db_manager.set_binary("plugin", "XQNEXT/sample", "avatar", b"two")
        assert await db_manager.get_binary("plugin", "XQNEXT/sample", "avatar") == b"two"
        assert await db_manager.list_binary_keys("plugin", "XQNEXT/sample") == ["avatar"]

        assert await db_manager.delete_binary("plugin", "XQNEXT/sample", "avatar")
        assert await db_manager.get_binary("plugin", "XQNEXT/sample", "avatar") is None

    @pytest.mark.asyncio
    async def test_prune_orphaned_plugin_settings(self, db_manager: DatabaseManager, tmp_path: Path):
        """Test pruning plugin DB rows whose manifest files are missing."""
        plugin_base = tmp_path / "plugins"
        plugin_base.mkdir()

        existing_dir = plugin_base / "existing_plugin"
        existing_dir.mkdir()
        (existing_dir / "metadata.yaml").write_text(
            "name: existing_plugin\nversion: 1.0.0\nauthor: XQNEXT\n",
            encoding="utf-8",
        )
        (existing_dir / "settings.json").write_text(
            '{"config_schema": {}, "default_config": {}}',
            encoding="utf-8",
        )

        await db_manager.create_plugin_setting(
            "XQNEXT",
            "missing_plugin",
            config={"avatar": "plugin_config_avatar"},
        )
        await db_manager.create_plugin_setting("XQNEXT", "existing_plugin")
        await db_manager.set_binary(
            "plugin",
            "XQNEXT/missing_plugin",
            "plugin_config_avatar",
            b"avatar",
        )
        await db_manager.set_binary("plugin", "XQNEXT/missing_plugin", "leftover", b"data")

        pruned = await db_manager.prune_orphaned_plugin_settings(plugin_base)

        assert pruned == ["XQNEXT/missing_plugin"]
        assert await db_manager.get_plugin_setting("XQNEXT", "missing_plugin") is None
        assert await db_manager.get_plugin_setting("XQNEXT", "existing_plugin") is not None
        assert await db_manager.list_binary_keys("plugin", "XQNEXT/missing_plugin") == []

    @pytest.mark.asyncio
    async def test_sandbox_lifecycle(self, db_manager: DatabaseManager):
        """Test sandbox and sandbox-message helpers without legacy AI fields."""
        sandbox_uuid = str(uuid4())
        sandbox = await db_manager.create_sandbox(
            uuid=sandbox_uuid,
            name="Plugin Sandbox",
            description="Current sandbox path",
            mock_user_id="10001",
            mock_user_nickname="Tester",
            mock_group_id="20002",
            mock_group_name="Test Group",
            use_plugins=True,
        )

        assert sandbox.to_dict()["use_plugins"] is True

        message = await db_manager.create_sandbox_message(
            sandbox_uuid=sandbox_uuid,
            message_type="group",
            direction="inbound",
            user_id="10001",
            user_nickname="Tester",
            group_id="20002",
            group_name="Test Group",
            content="hello",
            processed_by_plugins=True,
            plugin_responses=[{"plugin": "sample", "content": "ok"}],
        )
        message_dict = message.to_dict()

        assert message_dict["processed_by_plugins"] is True
        assert message_dict["plugin_responses"] == [{"plugin": "sample", "content": "ok"}]

        await db_manager.update_sandbox_message(
            message.id,
            processed_by_plugins=False,
            plugin_responses=[],
            has_error=True,
            error_message="boom",
        )
        messages = await db_manager.list_sandbox_messages(sandbox_uuid)
        assert len(messages) == 1
        assert messages[0].processed_by_plugins is False
        assert messages[0].has_error is True
        assert messages[0].error_message == "boom"

        await db_manager.clear_sandbox_messages(sandbox_uuid)
        assert await db_manager.list_sandbox_messages(sandbox_uuid) == []

        await db_manager.delete_sandbox(sandbox_uuid)
        assert await db_manager.get_sandbox(sandbox_uuid) is None

    @pytest.mark.asyncio
    async def test_database_connection_close(self, db_manager: DatabaseManager):
        """Test closing database connection."""
        await db_manager.close()


class TestDatabaseManagerGlobal:
    """Test suite for global database manager instance."""

    def test_get_database_manager_singleton(self):
        """Test that get_database_manager returns an initialized singleton handle."""
        manager1 = get_database_manager()
        manager2 = get_database_manager()

        assert manager1 is not None
        assert manager1 is manager2
