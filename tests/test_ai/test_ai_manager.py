"""
Tests for AI Manager component.

This test suite covers:
- AI configuration management
- AI memory management
- Configuration inheritance
- Batch operations
- Cache management
- Enable/disable functionality
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, List

from src.ai.ai_manager import AIManager


class TestAIManager:
    """Test suite for AIManager functionality."""

    @pytest.fixture
    def mock_db_manager(self):
        """Create a mock database manager."""
        db_manager = MagicMock()

        # AI Config methods
        db_manager.create_ai_config = AsyncMock()
        db_manager.get_ai_config = AsyncMock(return_value=None)
        db_manager.update_ai_config = AsyncMock(return_value=True)
        db_manager.delete_ai_config = AsyncMock(return_value=True)
        db_manager.list_ai_configs = AsyncMock(return_value=[])
        db_manager.batch_update_ai_configs = AsyncMock(return_value=0)

        # AI Memory methods
        db_manager.create_ai_memory = AsyncMock()
        db_manager.get_ai_memory = AsyncMock(return_value=None)
        db_manager.update_ai_memory = AsyncMock(return_value=True)
        db_manager.clear_ai_memory = AsyncMock(return_value=True)
        db_manager.delete_ai_memory = AsyncMock(return_value=True)
        db_manager.list_ai_memories = AsyncMock(return_value=[])

        return db_manager

    @pytest.fixture
    def ai_manager(self, mock_db_manager):
        """Create an AI manager instance."""
        return AIManager(db_manager=mock_db_manager)

    @pytest.mark.asyncio
    async def test_ai_manager_initialization(self, ai_manager: AIManager):
        """Test that AI manager initializes correctly."""
        assert ai_manager is not None
        assert ai_manager.db_manager is not None
        assert len(ai_manager._config_cache) == 0
        assert len(ai_manager._memory_cache) == 0

    @pytest.mark.asyncio
    async def test_ai_manager_initialize(self, ai_manager: AIManager):
        """Test AI manager initialization."""
        await ai_manager.initialize()

        # Should refresh config cache
        assert ai_manager is not None

    @pytest.mark.asyncio
    async def test_get_config_group(self, ai_manager: AIManager):
        """Test getting group configuration."""
        # Mock config
        mock_config = MagicMock()
        mock_config.config_type = "group"
        mock_config.target_id = "123456"
        mock_config.enabled = True
        mock_config.model_uuid = "model-123"
        mock_config.preset_uuid = "preset-123"
        mock_config.message_count = 5
        mock_config.config = {"trigger_command": "/ai"}

        mock_config.to_dict = MagicMock(return_value={
            "config_type": "group",
            "target_id": "123456",
            "enabled": True,
            "model_uuid": "model-123",
            "preset_uuid": "preset-123",
            "message_count": 5,
            "config": {"trigger_command": "/ai"}
        })

        ai_manager.db_manager.get_ai_config = AsyncMock(return_value=mock_config)

        config = await ai_manager.get_config("group", "123456")

        assert config is not None
        assert config["config_type"] == "group"
        assert config["target_id"] == "123456"
        assert config["enabled"] is True

    @pytest.mark.asyncio
    async def test_get_config_nonexistent(self, ai_manager: AIManager):
        """Test getting non-existent configuration."""
        config = await ai_manager.get_config("group", "999999")

        assert config is not None
        assert config["config_type"] == "group"
        assert config["target_id"] == "999999"
        assert config["enabled"] is False

    @pytest.mark.asyncio
    async def test_get_config_with_inheritance(self, ai_manager: AIManager):
        """Test config inheritance from global config."""
        # Mock global config
        global_config = MagicMock()
        global_config.config_type = "global"
        global_config.target_id = None
        global_config.enabled = True
        global_config.model_uuid = "global-model"
        global_config.preset_uuid = "global-preset"
        global_config.config = {"trigger_command": "/ai", "temperature": 0.7}

        global_config.to_dict = MagicMock(return_value={
            "config_type": "global",
            "target_id": None,
            "enabled": True,
            "model_uuid": "global-model",
            "preset_uuid": "global-preset",
            "message_count": 0,
            "config": {"trigger_command": "/ai", "temperature": 0.7}
        })

        # Mock group config (without model/preset, should inherit)
        group_config = MagicMock()
        group_config.config_type = "group"
        group_config.target_id = "123456"
        group_config.enabled = True
        group_config.model_uuid = None
        group_config.preset_uuid = None
        group_config.config = {"trigger_command": "/group-ai"}

        group_config.to_dict = MagicMock(return_value={
            "config_type": "group",
            "target_id": "123456",
            "enabled": True,
            "model_uuid": None,
            "preset_uuid": None,
            "message_count": 0,
            "config": {"trigger_command": "/group-ai"}
        })

        def get_config_mock(config_type, target_id):
            if config_type == "global":
                return global_config
            elif config_type == "group" and target_id == "123456":
                return group_config
            return None

        ai_manager.db_manager.get_ai_config = AsyncMock(side_effect=get_config_mock)

        config = await ai_manager.get_config("group", "123456")

        # Should inherit model and preset from global
        assert config["model_uuid"] == "global-model"
        assert config["preset_uuid"] == "global-preset"
        # Should use local config override
        assert config["config"]["trigger_command"] == "/group-ai"

    @pytest.mark.asyncio
    async def test_update_config(self, ai_manager: AIManager):
        """Test updating configuration."""
        ai_manager.db_manager.get_ai_config = AsyncMock(return_value=None)

        success = await ai_manager.update_config(
            "group",
            "123456",
            enabled=True,
            model_uuid="model-123"
        )

        assert success is True
        ai_manager.db_manager.create_ai_config.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_existing_config(self, ai_manager: AIManager):
        """Test updating existing configuration."""
        mock_config = MagicMock()

        ai_manager.db_manager.get_ai_config = AsyncMock(return_value=mock_config)
        ai_manager.db_manager.update_ai_config = AsyncMock(return_value=True)

        success = await ai_manager.update_config(
            "group",
            "123456",
            enabled=False
        )

        assert success is True
        ai_manager.db_manager.update_ai_config.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_group_configs(self, ai_manager: AIManager):
        """Test listing group configurations."""
        mock_configs = [
            MagicMock(to_dict=MagicMock(return_value={
                "config_type": "group",
                "target_id": "111111",
                "enabled": True
            })),
            MagicMock(to_dict=MagicMock(return_value={
                "config_type": "group",
                "target_id": "222222",
                "enabled": False
            })),
        ]

        ai_manager.db_manager.list_ai_configs = AsyncMock(return_value=mock_configs)

        configs = await ai_manager.list_group_configs()

        assert len(configs) == 2
        assert configs[0]["target_id"] == "111111"
        assert configs[1]["target_id"] == "222222"

    @pytest.mark.asyncio
    async def test_list_group_configs_exclude_left(self, ai_manager: AIManager):
        """Test listing group configs with exclude_left option."""
        ai_manager.db_manager.list_ai_configs = AsyncMock(return_value=[])

        # Test with exclude_left=True
        configs = await ai_manager.list_group_configs(exclude_left=True)
        ai_manager.db_manager.list_ai_configs.assert_called_with('group', exclude_left=True)

        # Test with exclude_left=False
        configs = await ai_manager.list_group_configs(exclude_left=False)
        ai_manager.db_manager.list_ai_configs.assert_called_with('group', exclude_left=False)

    @pytest.mark.asyncio
    async def test_batch_update_groups(self, ai_manager: AIManager):
        """Test batch updating group configurations."""
        ai_manager.db_manager.get_ai_config = AsyncMock(return_value=None)
        ai_manager.db_manager.batch_update_ai_configs = AsyncMock(return_value=3)

        count = await ai_manager.batch_update_groups(
            ["111111", "222222", "333333"],
            enabled=True,
            model_uuid="model-123"
        )

        assert count == 3

    @pytest.mark.asyncio
    async def test_is_enabled_global_disabled(self, ai_manager: AIManager):
        """Test is_enabled when global config is disabled."""
        global_config = MagicMock()
        global_config.enabled = False

        ai_manager.db_manager.get_ai_config = AsyncMock(return_value=global_config)

        enabled = await ai_manager.is_enabled("group", "123456")

        assert enabled is False

    @pytest.mark.asyncio
    async def test_is_enabled_global_enabled_specific_disabled(self, ai_manager: AIManager):
        """Test is_enabled when global enabled but specific disabled."""
        global_config = MagicMock()
        global_config.enabled = True

        specific_config = MagicMock()
        specific_config.enabled = False

        def get_config_mock(config_type, target_id):
            if config_type == "global":
                return global_config
            elif config_type == "group":
                return specific_config
            return None

        ai_manager.db_manager.get_ai_config = AsyncMock(side_effect=get_config_mock)

        enabled = await ai_manager.is_enabled("group", "123456")

        assert enabled is False

    @pytest.mark.asyncio
    async def test_is_enabled_no_config(self, ai_manager: AIManager):
        """Test is_enabled when no config exists."""
        ai_manager.db_manager.get_ai_config = AsyncMock(return_value=None)

        enabled = await ai_manager.is_enabled("group", "123456")

        assert enabled is False

    @pytest.mark.asyncio
    async def test_increment_message_count(self, ai_manager: AIManager):
        """Test incrementing message count."""
        mock_config = MagicMock()
        mock_config.message_count = 5

        ai_manager.db_manager.get_ai_config = AsyncMock(return_value=mock_config)
        ai_manager.db_manager.update_ai_config = AsyncMock(return_value=True)

        await ai_manager.increment_message_count("group", "123456")

        ai_manager.db_manager.update_ai_config.assert_called_with(
            "group", "123456", message_count=6
        )

    @pytest.mark.asyncio
    async def test_get_memory(self, ai_manager: AIManager):
        """Test getting AI memory."""
        mock_memory = MagicMock()
        mock_memory.uuid = "memory-uuid"
        mock_memory.memory_type = "group"
        mock_memory.target_id = "123456"
        mock_memory.preset_uuid = "preset-123"
        mock_memory.messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"}
        ]
        mock_memory.message_count = 2

        mock_memory.to_dict = MagicMock(return_value={
            "uuid": "memory-uuid",
            "memory_type": "group",
            "target_id": "123456",
            "preset_uuid": "preset-123",
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi!"}
            ],
            "message_count": 2
        })

        ai_manager.db_manager.get_ai_memory = AsyncMock(return_value=mock_memory)

        memory = await ai_manager.get_memory("group", "123456", "preset-123")

        assert memory is not None
        assert memory["memory_type"] == "group"
        assert len(memory["messages"]) == 2

    @pytest.mark.asyncio
    async def test_get_memory_nonexistent(self, ai_manager: AIManager):
        """Test getting non-existent memory."""
        ai_manager.db_manager.get_ai_memory = AsyncMock(return_value=None)

        memory = await ai_manager.get_memory("group", "123456")

        assert memory is not None
        assert memory["uuid"] is None
        assert len(memory["messages"]) == 0

    @pytest.mark.asyncio
    async def test_create_memory(self, ai_manager: AIManager):
        """Test creating AI memory."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"}
        ]

        mock_memory = MagicMock()
        mock_memory.uuid = "memory-uuid"
        mock_memory.to_dict = MagicMock(return_value={
            "uuid": "memory-uuid",
            "memory_type": "group",
            "target_id": "123456",
            "messages": messages,
            "message_count": 2
        })

        ai_manager.db_manager.get_ai_memory = AsyncMock(return_value=None)
        ai_manager.db_manager.create_ai_memory = AsyncMock(return_value=mock_memory)

        memory = await ai_manager.create_or_update_memory(
            "group",
            "123456",
            messages,
            "preset-123"
        )

        assert memory is not None
        assert memory["uuid"] == "memory-uuid"
        assert len(memory["messages"]) == 2

    @pytest.mark.asyncio
    async def test_update_memory(self, ai_manager: AIManager):
        """Test updating AI memory."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
            {"role": "user", "content": "How are you?"}
        ]

        mock_memory = MagicMock()
        mock_memory.uuid = "memory-uuid"
        mock_memory.to_dict = MagicMock(return_value={
            "uuid": "memory-uuid",
            "memory_type": "group",
            "target_id": "123456",
            "messages": messages,
            "message_count": 3
        })

        ai_manager.db_manager.get_ai_memory = AsyncMock(return_value=mock_memory)
        ai_manager.db_manager.update_ai_memory = AsyncMock(return_value=True)

        memory = await ai_manager.create_or_update_memory(
            "group",
            "123456",
            messages
        )

        assert memory is not None
        assert len(memory["messages"]) == 3

    @pytest.mark.asyncio
    async def test_clear_memory(self, ai_manager: AIManager):
        """Test clearing AI memory."""
        ai_manager.db_manager.clear_ai_memory = AsyncMock(return_value=True)

        success = await ai_manager.clear_memory("group", "123456")

        assert success is True
        ai_manager.db_manager.clear_ai_memory.assert_called_once_with("group", "123456", None)

    @pytest.mark.asyncio
    async def test_clear_memory_with_preset(self, ai_manager: AIManager):
        """Test clearing AI memory with preset."""
        ai_manager.db_manager.clear_ai_memory = AsyncMock(return_value=True)

        success = await ai_manager.clear_memory("group", "123456", "preset-123")

        assert success is True
        ai_manager.db_manager.clear_ai_memory.assert_called_once_with("group", "123456", "preset-123")

    @pytest.mark.asyncio
    async def test_list_memories(self, ai_manager: AIManager):
        """Test listing AI memories."""
        mock_memories = [
            MagicMock(to_dict=MagicMock(return_value={
                "uuid": "mem-1",
                "memory_type": "group",
                "target_id": "111111"
            })),
            MagicMock(to_dict=MagicMock(return_value={
                "uuid": "mem-2",
                "memory_type": "group",
                "target_id": "222222"
            })),
        ]

        ai_manager.db_manager.list_ai_memories = AsyncMock(return_value=mock_memories)

        memories = await ai_manager.list_memories()

        assert len(memories) == 2

    @pytest.mark.asyncio
    async def test_list_memories_by_type(self, ai_manager: AIManager):
        """Test listing memories by type."""
        ai_manager.db_manager.list_ai_memories = AsyncMock(return_value=[])

        memories = await ai_manager.list_memories(memory_type="group")

        ai_manager.db_manager.list_ai_memories.assert_called_once_with("group", None)

    @pytest.mark.asyncio
    async def test_list_memories_by_target(self, ai_manager: AIManager):
        """Test listing memories by target ID."""
        ai_manager.db_manager.list_ai_memories = AsyncMock(return_value=[])

        memories = await ai_manager.list_memories(target_id="123456")

        ai_manager.db_manager.list_ai_memories.assert_called_once_with(None, "123456")

    @pytest.mark.asyncio
    async def test_delete_memory(self, ai_manager: AIManager):
        """Test deleting AI memory."""
        ai_manager.db_manager.delete_ai_memory = AsyncMock(return_value=True)

        success = await ai_manager.delete_memory("memory-uuid")

        assert success is True
        ai_manager.db_manager.delete_ai_memory.assert_called_once_with("memory-uuid")

    @pytest.mark.asyncio
    async def test_config_cache_refresh(self, ai_manager: AIManager):
        """Test config cache refresh."""
        mock_config = MagicMock()
        mock_config.config_type = "group"
        mock_config.target_id = "123456"

        ai_manager.db_manager.list_ai_configs = AsyncMock(return_value=[mock_config])

        await ai_manager._refresh_config_cache()

        assert len(ai_manager._config_cache) > 0

    @pytest.mark.asyncio
    async def test_batch_update_empty_list(self, ai_manager: AIManager):
        """Test batch update with empty group list."""
        count = await ai_manager.batch_update_groups([])

        assert count == 0

    @pytest.mark.asyncio
    async def test_batch_update_no_updates(self, ai_manager: AIManager):
        """Test batch update with no parameters to update."""
        count = await ai_manager.batch_update_groups(["111111"])

        assert count == 0