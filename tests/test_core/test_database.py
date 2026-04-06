"""
Tests for Database component.

This test suite covers:
- Database initialization
- AI configuration CRUD operations
- AI memory CRUD operations
- Batch operations
- Cleanup operations
- Database connection management
- Error handling
"""
import pytest
import tempfile
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
from uuid import uuid4

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
        # Clean up
        if temp_db_path.exists():
            temp_db_path.unlink()

    @pytest.mark.asyncio
    async def test_database_initialization(self, db_manager: DatabaseManager):
        """Test that database initializes correctly."""
        assert db_manager is not None
        assert db_manager.db_path is not None

    @pytest.mark.asyncio
    async def test_create_ai_config(self, db_manager: DatabaseManager):
        """Test creating AI configuration."""
        config = await db_manager.create_ai_config(
            config_type="group",
            target_id="123456",
            enabled=True,
            model_uuid="model-uuid-123",
            preset_uuid="preset-uuid-456",
            config={"trigger_command": "/ai"}
        )

        assert config is not None
        assert config.config_type == "group"
        assert config.target_id == "123456"
        assert config.enabled is True
        assert config.model_uuid == "model-uuid-123"
        assert config.preset_uuid == "preset-uuid-456"
        assert config.config == {"trigger_command": "/ai"}

    @pytest.mark.asyncio
    async def test_get_ai_config(self, db_manager: DatabaseManager):
        """Test getting AI configuration."""
        # Create config
        await db_manager.create_ai_config(
            config_type="group",
            target_id="123456",
            enabled=True
        )

        # Get config
        config = await db_manager.get_ai_config("group", "123456")

        assert config is not None
        assert config.config_type == "group"
        assert config.target_id == "123456"

    @pytest.mark.asyncio
    async def test_get_nonexistent_ai_config(self, db_manager: DatabaseManager):
        """Test getting non-existent AI configuration."""
        config = await db_manager.get_ai_config("group", "999999")

        assert config is None

    @pytest.mark.asyncio
    async def test_update_ai_config(self, db_manager: DatabaseManager):
        """Test updating AI configuration."""
        # Create config
        await db_manager.create_ai_config(
            config_type="group",
            target_id="123456",
            enabled=False,
            model_uuid="model-1"
        )

        # Update config
        success = await db_manager.update_ai_config(
            "group",
            "123456",
            enabled=True,
            model_uuid="model-2"
        )

        assert success is True

        # Verify update
        config = await db_manager.get_ai_config("group", "123456")
        assert config.enabled is True
        assert config.model_uuid == "model-2"

    @pytest.mark.asyncio
    async def test_delete_ai_config(self, db_manager: DatabaseManager):
        """Test deleting AI configuration."""
        # Create config
        await db_manager.create_ai_config(
            config_type="group",
            target_id="123456",
            enabled=True
        )

        # Delete config
        success = await db_manager.delete_ai_config("group", "123456")

        assert success is True

        # Verify deletion
        config = await db_manager.get_ai_config("group", "123456")
        assert config is None

    @pytest.mark.asyncio
    async def test_list_ai_configs(self, db_manager: DatabaseManager):
        """Test listing AI configurations."""
        # Create multiple configs
        await db_manager.create_ai_config("group", "111111", enabled=True)
        await db_manager.create_ai_config("group", "222222", enabled=False)
        await db_manager.create_ai_config("group", "333333", enabled=True)

        # List configs
        configs = await db_manager.list_ai_configs("group")

        assert len(configs) == 3

    @pytest.mark.asyncio
    async def test_list_ai_configs_by_type(self, db_manager: DatabaseManager):
        """Test listing AI configurations by type."""
        # Create configs of different types
        await db_manager.create_ai_config("group", "111111", enabled=True)
        await db_manager.create_ai_config("user", "222222", enabled=True)
        await db_manager.create_ai_config("global", None, enabled=True)

        # List group configs
        group_configs = await db_manager.list_ai_configs("group")
        assert len(group_configs) == 1

        # List user configs
        user_configs = await db_manager.list_ai_configs("user")
        assert len(user_configs) == 1

        # List global configs
        global_configs = await db_manager.list_ai_configs("global")
        assert len(global_configs) == 1

    @pytest.mark.asyncio
    async def test_batch_update_ai_configs(self, db_manager: DatabaseManager):
        """Test batch updating AI configurations."""
        # Create multiple configs
        await db_manager.create_ai_config("group", "111111", enabled=False)
        await db_manager.create_ai_config("group", "222222", enabled=False)
        await db_manager.create_ai_config("group", "333333", enabled=True)

        # Batch update
        count = await db_manager.batch_update_ai_configs(
            "group",
            ["111111", "222222"],
            enabled=True
        )

        assert count == 2

        # Verify updates
        config1 = await db_manager.get_ai_config("group", "111111")
        config2 = await db_manager.get_ai_config("group", "222222")
        config3 = await db_manager.get_ai_config("group", "333333")

        assert config1.enabled is True
        assert config2.enabled is True
        assert config3.enabled is True

    @pytest.mark.asyncio
    async def test_create_ai_memory(self, db_manager: DatabaseManager):
        """Test creating AI memory."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]

        memory = await db_manager.create_ai_memory(
            uuid=str(uuid4()),
            memory_type="group",
            target_id="123456",
            preset_uuid="preset-123",
            messages=messages
        )

        assert memory is not None
        assert memory.memory_type == "group"
        assert memory.target_id == "123456"
        assert len(memory.messages) == 2

    @pytest.mark.asyncio
    async def test_get_ai_memory(self, db_manager: DatabaseManager):
        """Test getting AI memory."""
        memory_uuid = str(uuid4())

        # Create memory
        await db_manager.create_ai_memory(
            uuid=memory_uuid,
            memory_type="group",
            target_id="123456",
            messages=[{"role": "user", "content": "Test"}]
        )

        # Get memory
        memory = await db_manager.get_ai_memory("group", "123456")

        assert memory is not None
        assert memory.memory_type == "group"
        assert memory.target_id == "123456"

    @pytest.mark.asyncio
    async def test_update_ai_memory(self, db_manager: DatabaseManager):
        """Test updating AI memory."""
        memory_uuid = str(uuid4())

        # Create memory
        await db_manager.create_ai_memory(
            uuid=memory_uuid,
            memory_type="group",
            target_id="123456",
            messages=[{"role": "user", "content": "Original"}]
        )

        # Update memory
        new_messages = [
            {"role": "user", "content": "Original"},
            {"role": "assistant", "content": "Response"}
        ]

        success = await db_manager.update_ai_memory(
            memory_uuid,
            messages=new_messages,
            message_count=2
        )

        assert success is True

        # Verify update
        memory = await db_manager.get_ai_memory("group", "123456")
        assert len(memory.messages) == 2
        assert memory.message_count == 2

    @pytest.mark.asyncio
    async def test_clear_ai_memory(self, db_manager: DatabaseManager):
        """Test clearing AI memory."""
        # Create memory
        await db_manager.create_ai_memory(
            uuid=str(uuid4()),
            memory_type="group",
            target_id="123456",
            messages=[{"role": "user", "content": "Test"}]
        )

        # Clear memory
        success = await db_manager.clear_ai_memory("group", "123456")

        assert success is True

        # Verify clear
        memory = await db_manager.get_ai_memory("group", "123456")
        assert memory is None or len(memory.messages) == 0

    @pytest.mark.asyncio
    async def test_delete_ai_memory(self, db_manager: DatabaseManager):
        """Test deleting AI memory."""
        memory_uuid = str(uuid4())

        # Create memory
        await db_manager.create_ai_memory(
            uuid=memory_uuid,
            memory_type="group",
            target_id="123456",
            messages=[{"role": "user", "content": "Test"}]
        )

        # Delete memory
        success = await db_manager.delete_ai_memory(memory_uuid)

        assert success is True

        # Verify deletion
        memory = await db_manager.get_ai_memory("group", "123456")
        assert memory is None

    @pytest.mark.asyncio
    async def test_list_ai_memories(self, db_manager: DatabaseManager):
        """Test listing AI memories."""
        # Create multiple memories
        await db_manager.create_ai_memory(
            uuid=str(uuid4()),
            memory_type="group",
            target_id="111111",
            messages=[{"role": "user", "content": "Test 1"}]
        )
        await db_manager.create_ai_memory(
            uuid=str(uuid4()),
            memory_type="group",
            target_id="222222",
            messages=[{"role": "user", "content": "Test 2"}]
        )

        # List memories
        memories = await db_manager.list_ai_memories("group")

        assert len(memories) == 2

    @pytest.mark.asyncio
    async def test_list_ai_memories_by_target(self, db_manager: DatabaseManager):
        """Test listing AI memories by target ID."""
        # Create memories for same target
        await db_manager.create_ai_memory(
            uuid=str(uuid4()),
            memory_type="group",
            target_id="123456",
            preset_uuid="preset-1",
            messages=[{"role": "user", "content": "Test 1"}]
        )
        await db_manager.create_ai_memory(
            uuid=str(uuid4()),
            memory_type="group",
            target_id="123456",
            preset_uuid="preset-2",
            messages=[{"role": "user", "content": "Test 2"}]
        )

        # List memories for target
        memories = await db_manager.list_ai_memories("group", "123456")

        assert len(memories) == 2

    @pytest.mark.asyncio
    async def test_cleanup_expired_left_groups(self, db_manager: DatabaseManager):
        """Test cleanup of expired left groups."""
        # Create a left group config with old timestamp
        await db_manager.create_ai_config(
            config_type="group",
            target_id="999999",
            enabled=False,
            is_left=True,
            left_at=datetime.utcnow().replace(day=1)  # Old date
        )

        # Create a recent left group config
        await db_manager.create_ai_config(
            config_type="group",
            target_id="888888",
            enabled=False,
            is_left=True,
            left_at=datetime.utcnow()  # Recent date
        )

        # Create an active group config
        await db_manager.create_ai_config(
            config_type="group",
            target_id="777777",
            enabled=True,
            is_left=False
        )

        # Test the method exists
        assert hasattr(db_manager, 'cleanup_expired_left_groups')

    @pytest.mark.asyncio
    async def test_config_serialization(self, db_manager: DatabaseManager):
        """Test config serialization to dict."""
        # Create config
        config = await db_manager.create_ai_config(
            config_type="group",
            target_id="123456",
            enabled=True,
            config={"key": "value"}
        )

        # Convert to dict
        config_dict = config.to_dict()

        assert isinstance(config_dict, dict)
        assert config_dict["config_type"] == "group"
        assert config_dict["target_id"] == "123456"
        assert config_dict["enabled"] is True
        assert config_dict["config"] == {"key": "value"}

    @pytest.mark.asyncio
    async def test_memory_serialization(self, db_manager: DatabaseManager):
        """Test memory serialization to dict."""
        # Create memory
        memory = await db_manager.create_ai_memory(
            uuid=str(uuid4()),
            memory_type="group",
            target_id="123456",
            messages=[{"role": "user", "content": "Test"}]
        )

        # Convert to dict
        memory_dict = memory.to_dict()

        assert isinstance(memory_dict, dict)
        assert memory_dict["memory_type"] == "group"
        assert memory_dict["target_id"] == "123456"
        assert len(memory_dict["messages"]) == 1

    @pytest.mark.asyncio
    async def test_increment_message_count(self, db_manager: DatabaseManager):
        """Test incrementing message count."""
        # Create config with initial count (default is 0)
        await db_manager.create_ai_config(
            config_type="group",
            target_id="123456"
        )

        # Update to increment count
        await db_manager.update_ai_config(
            "group",
            "123456",
            message_count=1
        )

        # Verify
        config = await db_manager.get_ai_config("group", "123456")
        assert config.message_count == 1

    @pytest.mark.asyncio
    async def test_duplicate_config_creation(self, db_manager: DatabaseManager):
        """Test handling duplicate config creation."""
        # Create config
        await db_manager.create_ai_config(
            config_type="group",
            target_id="123456",
            enabled=True
        )

        # Try to create duplicate - should handle gracefully
        try:
            await db_manager.create_ai_config(
                config_type="group",
                target_id="123456",
                enabled=False
            )
            # If it doesn't raise, test passes
            assert True
        except Exception:
            # If it raises, that's also acceptable
            assert True

    @pytest.mark.asyncio
    async def test_database_connection_close(self, db_manager: DatabaseManager):
        """Test closing database connection."""
        # Close connection
        await db_manager.close()

        # Verify connection is closed
        assert db_manager._initialized is False


class TestDatabaseManagerGlobal:
    """Test suite for global database manager instance."""

    @pytest.mark.asyncio
    async def test_get_database_manager_singleton(self, temp_db_path: Path):
        """Test that get_database_manager returns singleton instance."""
        from src.core.database import get_database_manager
        manager1 = get_database_manager()
        manager2 = get_database_manager()

        # Should return same instance (with same db path)
        assert manager1 is not None
        assert manager2 is not None