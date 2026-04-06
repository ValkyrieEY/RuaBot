"""
Tests for OneBot protocol adapter.

This test suite covers:
- Adapter initialization
- HTTP connection
- WebSocket connection (forward and reverse)
- Message sending
- Event handling
- API calls
- Connection management
- Error handling
"""
import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from typing import Dict, Any

from src.protocol.onebot import OneBotAdapter


class TestOneBotAdapter:
    """Test suite for OneBotAdapter functionality."""

    @pytest.fixture
    def onebot_config(self) -> Dict[str, Any]:
        """Create OneBot adapter configuration."""
        return {
            "version": "v11",
            "connection_type": "http",
            "http_url": "http://localhost:5700",
            "ws_url": "ws://localhost:5700",
            "ws_reverse_host": "0.0.0.0",
            "ws_reverse_port": 8080,
            "ws_reverse_path": "/onebot/v11/ws",
            "access_token": "",
            "secret": "",
            "http_timeout": 120.0,
            "ws_api_timeout": 60.0,
        }

    @pytest.fixture
    def adapter(self, onebot_config: Dict[str, Any]):
        """Create a OneBot adapter instance."""
        return OneBotAdapter(onebot_config)

    def test_adapter_initialization(self, adapter: OneBotAdapter, onebot_config: Dict[str, Any]):
        """Test that adapter initializes correctly."""
        assert adapter is not None
        assert adapter.version == onebot_config["version"]
        assert adapter.connection_type == onebot_config["connection_type"]
        assert adapter.http_url == onebot_config["http_url"]
        assert adapter.ws_url == onebot_config["ws_url"]
        assert not adapter._running

    def test_adapter_with_access_token(self):
        """Test adapter initialization with access token."""
        config = {
            "version": "v11",
            "connection_type": "http",
            "http_url": "http://localhost:5700",
            "access_token": "test_token",
        }

        adapter = OneBotAdapter(config)

        assert adapter.access_token == "test_token"

    @pytest.mark.asyncio
    async def test_adapter_start_http(self, adapter: OneBotAdapter):
        """Test starting adapter with HTTP connection."""
        adapter.connection_type = "http"

        await adapter.start()

        assert adapter._running
        assert adapter._http_client is not None

        await adapter.stop()

    @pytest.mark.asyncio
    async def test_adapter_stop(self, adapter: OneBotAdapter):
        """Test stopping adapter."""
        await adapter.start()
        assert adapter._running

        await adapter.stop()
        assert not adapter._running

    @pytest.mark.asyncio
    async def test_adapter_start_already_running(self, adapter: OneBotAdapter):
        """Test starting adapter when already running."""
        await adapter.start()
        assert adapter._running

        # Should not raise error
        await adapter.start()

        await adapter.stop()

    @pytest.mark.asyncio
    async def test_adapter_stop_not_running(self, adapter: OneBotAdapter):
        """Test stopping adapter when not running."""
        # Should not raise error
        await adapter.stop()
        assert not adapter._running

    @pytest.mark.asyncio
    async def test_send_private_message_http(self, adapter: OneBotAdapter):
        """Test sending private message via HTTP."""
        adapter.connection_type = "http"

        # Mock HTTP client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value={
            "retcode": 0,
            "data": {"message_id": 12345}
        })

        adapter._http_client = MagicMock()
        adapter._http_client.post = AsyncMock(return_value=mock_response)

        await adapter.start()

        result = await adapter.send_private_message(111222, "Test message")

        assert result is not None
        assert result["retcode"] == 0

        await adapter.stop()

    @pytest.mark.asyncio
    async def test_send_group_message_http(self, adapter: OneBotAdapter):
        """Test sending group message via HTTP."""
        adapter.connection_type = "http"

        # Mock HTTP client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value={
            "retcode": 0,
            "data": {"message_id": 12345}
        })

        adapter._http_client = MagicMock()
        adapter._http_client.post = AsyncMock(return_value=mock_response)

        await adapter.start()

        result = await adapter.send_group_message(987654, "Test message")

        assert result is not None
        assert result["retcode"] == 0

        await adapter.stop()

    @pytest.mark.asyncio
    async def test_send_message_with_segments(self, adapter: OneBotAdapter):
        """Test sending message with segments."""
        adapter.connection_type = "http"

        # Mock HTTP client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value={
            "retcode": 0,
            "data": {"message_id": 12345}
        })

        adapter._http_client = MagicMock()
        adapter._http_client.post = AsyncMock(return_value=mock_response)

        await adapter.start()

        message = [
            {"type": "text", "data": {"text": "Hello "}},
            {"type": "at", "data": {"qq": 111222}},
            {"type": "text", "data": {"text": "!"}}
        ]

        result = await adapter.send_group_message(987654, message)

        assert result is not None

        await adapter.stop()

    def test_on_event(self, adapter: OneBotAdapter):
        """Test registering event handler."""
        handler = MagicMock()
        adapter.on_event(handler)

        assert handler in adapter._event_handlers

    def test_on_event_none(self, adapter: OneBotAdapter):
        """Test that None handler is ignored."""
        adapter.on_event(None)

        assert len(adapter._event_handlers) == 0

    def test_on_event_non_callable(self, adapter: OneBotAdapter):
        """Test that non-callable handler is ignored."""
        adapter.on_event("not_a_function")

        assert len(adapter._event_handlers) == 0

    @pytest.mark.asyncio
    async def test_handle_message_event(self, adapter: OneBotAdapter):
        """Test handling message event."""
        event_data = {
            "post_type": "message",
            "message_type": "group",
            "time": 1712345678,
            "self_id": 123456,
            "message_id": 7890,
            "group_id": 987654,
            "user_id": 111222,
            "raw_message": "Test message",
            "message": [
                {"type": "text", "data": {"text": "Test message"}}
            ],
            "sender": {
                "user_id": 111222,
                "nickname": "TestUser",
            }
        }

        published_events = []

        async def mock_emit(event):
            published_events.append(event)

        adapter._emit_event = mock_emit

        await adapter._handle_event(event_data)

        assert len(published_events) == 1
        assert published_events[0]["type"] == "message"

    @pytest.mark.asyncio
    async def test_handle_private_message_event(self, adapter: OneBotAdapter):
        """Test handling private message event."""
        event_data = {
            "post_type": "message",
            "message_type": "private",
            "time": 1712345678,
            "self_id": 123456,
            "message_id": 7890,
            "user_id": 111222,
            "raw_message": "Private message",
            "message": [
                {"type": "text", "data": {"text": "Private message"}}
            ],
            "sender": {
                "user_id": 111222,
                "nickname": "TestUser",
            }
        }

        published_events = []

        async def mock_emit(event):
            published_events.append(event)

        adapter._emit_event = mock_emit

        await adapter._handle_event(event_data)

        assert len(published_events) == 1
        assert published_events[0]["type"] == "message"

    @pytest.mark.asyncio
    async def test_handle_notice_event(self, adapter: OneBotAdapter):
        """Test handling notice event."""
        event_data = {
            "post_type": "notice",
            "notice_type": "group_increase",
            "time": 1712345678,
            "self_id": 123456,
            "group_id": 987654,
            "user_id": 111222,
            "operator_id": 123456,
        }

        published_events = []

        async def mock_emit(event):
            published_events.append(event)

        adapter._emit_event = mock_emit

        await adapter._handle_event(event_data)

        assert len(published_events) == 1
        assert published_events[0]["type"] == "notice"

    @pytest.mark.asyncio
    async def test_handle_request_event(self, adapter: OneBotAdapter):
        """Test handling request event."""
        event_data = {
            "post_type": "request",
            "request_type": "friend",
            "time": 1712345678,
            "self_id": 123456,
            "user_id": 111222,
            "comment": "Add me",
            "flag": "test_flag",
        }

        published_events = []

        async def mock_emit(event):
            published_events.append(event)

        adapter._emit_event = mock_emit

        await adapter._handle_event(event_data)

        assert len(published_events) == 1
        assert published_events[0]["type"] == "request"

    @pytest.mark.asyncio
    async def test_handle_meta_event(self, adapter: OneBotAdapter):
        """Test handling meta event (should be skipped)."""
        event_data = {
            "post_type": "meta_event",
            "meta_event_type": "heartbeat",
            "time": 1712345678,
            "interval": 5000,
        }

        published_events = []

        async def mock_emit(event):
            published_events.append(event)

        adapter._emit_event = mock_emit

        await adapter._handle_event(event_data)

        # Meta events should be skipped
        assert len(published_events) == 0

    @pytest.mark.asyncio
    async def test_handle_self_message(self, adapter: OneBotAdapter):
        """Test handling self message (should be skipped)."""
        event_data = {
            "post_type": "message",
            "message_type": "group",
            "time": 1712345678,
            "self_id": 123456,
            "user_id": 123456,  # Same as self_id
            "raw_message": "Self message",
            "message": [
                {"type": "text", "data": {"text": "Self message"}}
            ],
        }

        published_events = []

        async def mock_emit(event):
            published_events.append(event)

        adapter._emit_event = mock_emit

        await adapter._handle_event(event_data)

        # Self messages should be skipped
        assert len(published_events) == 0

    @pytest.mark.asyncio
    async def test_parse_message_event(self, adapter: OneBotAdapter):
        """Test parsing message event."""
        event_data = {
            "message_type": "group",
            "time": 1712345678,
            "message_id": 7890,
            "group_id": 987654,
            "user_id": 111222,
            "raw_message": "Test message",
            "message": [
                {"type": "text", "data": {"text": "Test message"}}
            ],
            "sender": {
                "user_id": 111222,
                "nickname": "TestUser",
            },
        }

        envelope = adapter._parse_message_event(event_data)

        assert envelope is not None
        assert envelope.message_type == "group"
        assert envelope.user_id == "111222"
        assert envelope.group_id == "987654"
        assert envelope.raw_message == "Test message"
        assert len(envelope.message) == 1

    @pytest.mark.asyncio
    async def test_parse_message_event_with_string(self, adapter: OneBotAdapter):
        """Test parsing message event with string message."""
        event_data = {
            "message_type": "group",
            "time": 1712345678,
            "message_id": 7890,
            "group_id": 987654,
            "user_id": 111222,
            "raw_message": "Test message",
            "message": "Test message",  # String instead of array
            "sender": {
                "user_id": 111222,
                "nickname": "TestUser",
            },
        }

        envelope = adapter._parse_message_event(event_data)

        assert envelope is not None
        assert len(envelope.message) == 1
        assert envelope.message[0].type == "text"

    def test_multiple_event_handlers(self, adapter: OneBotAdapter):
        """Test registering multiple event handlers."""
        handler1 = MagicMock()
        handler2 = MagicMock()
        handler3 = MagicMock()

        adapter.on_event(handler1)
        adapter.on_event(handler2)
        adapter.on_event(handler3)

        assert len(adapter._event_handlers) == 3

    @pytest.mark.asyncio
    async def test_adapter_connection_type_ws(self):
        """Test adapter with WebSocket forward connection."""
        config = {
            "version": "v11",
            "connection_type": "ws",
            "ws_url": "ws://localhost:5700",
        }

        adapter = OneBotAdapter(config)
        assert adapter.connection_type == "ws"

    @pytest.mark.asyncio
    async def test_adapter_connection_type_ws_reverse(self):
        """Test adapter with WebSocket reverse connection."""
        config = {
            "version": "v11",
            "connection_type": "ws_reverse",
            "ws_reverse_host": "0.0.0.0",
            "ws_reverse_port": 8080,
            "ws_reverse_path": "/onebot/v11/ws",
        }

        adapter = OneBotAdapter(config)
        assert adapter.connection_type == "ws_reverse"

    @pytest.mark.asyncio
    async def test_send_message_unknown_type(self, adapter: OneBotAdapter):
        """Test sending message with unknown type."""
        await adapter.start()

        with pytest.raises(ValueError):
            await adapter.send_message("123456", "Test", message_type="unknown")

        await adapter.stop()

    @pytest.mark.asyncio
    async def test_get_group_info(self, adapter: OneBotAdapter):
        """Test getting group info."""
        adapter.connection_type = "http"

        # Mock HTTP client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value={
            "retcode": 0,
            "data": {
                "group_id": 987654,
                "group_name": "Test Group",
                "member_count": 100
            }
        })

        adapter._http_client = MagicMock()
        adapter._http_client.get = AsyncMock(return_value=mock_response)

        await adapter.start()

        info = await adapter.get_group_info(987654)

        assert info is not None
        assert info["group_id"] == 987654
        assert info["group_name"] == "Test Group"

        await adapter.stop()

    @pytest.mark.asyncio
    async def test_get_user_info(self, adapter: OneBotAdapter):
        """Test getting user info."""
        adapter.connection_type = "http"

        # Mock HTTP client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value={
            "retcode": 0,
            "data": {
                "user_id": 111222,
                "nickname": "TestUser",
                "sex": "unknown",
                "age": 0
            }
        })

        adapter._http_client = MagicMock()
        adapter._http_client.get = AsyncMock(return_value=mock_response)

        await adapter.start()

        info = await adapter.get_user_info(111222)

        assert info is not None
        assert info["user_id"] == 111222
        assert info["nickname"] == "TestUser"

        await adapter.stop()