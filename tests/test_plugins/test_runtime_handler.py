import base64
from unittest.mock import AsyncMock

import pytest

from src.plugins.runtime.handler import RuntimeConnectionHandler


@pytest.mark.asyncio
async def test_handle_get_config_upload_reads_plugin_private_blob():
    db_manager = AsyncMock()
    db_manager.get_binary.return_value = b"demo-bytes"
    handler = RuntimeConnectionHandler(db_manager)

    result = await handler._handle_get_config_upload(
        {
            "owner": "XQNEXT/settings_ui_showcase",
            "key": "plugin_config_demo.txt",
        }
    )

    assert result["success"] is True
    assert base64.b64decode(result["value"]) == b"demo-bytes"
    db_manager.get_binary.assert_awaited_once_with(
        "plugin",
        "XQNEXT/settings_ui_showcase",
        "plugin_config_demo.txt",
    )


@pytest.mark.asyncio
async def test_handle_get_config_upload_rejects_invalid_key():
    db_manager = AsyncMock()
    handler = RuntimeConnectionHandler(db_manager)

    result = await handler._handle_get_config_upload(
        {
            "owner": "XQNEXT/settings_ui_showcase",
            "key": "not_allowed.txt",
        }
    )

    assert result["success"] is False
    assert "Invalid" in result["error"]
    db_manager.get_binary.assert_not_called()
