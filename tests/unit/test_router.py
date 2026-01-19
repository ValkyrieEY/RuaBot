"""Unit tests for router."""

import pytest
from src.router.router import Router, CommandRule, KeywordRule, Priority
from src.protocol.base import MessageEnvelope, MessageSegment
from datetime import datetime


def create_test_message(text: str, message_type: str = "private") -> MessageEnvelope:
    """Create a test message envelope."""
    return MessageEnvelope(
        message_id="123",
        message_type=message_type,
        user_id="user123",
        timestamp=datetime.now(),
        raw_message=text,
        message=[MessageSegment.text(text)]
    )


@pytest.mark.asyncio
async def test_command_rule():
    """Test command rule matching."""
    rule = CommandRule("test", prefixes=["/", "!"])
    context = {}
    
    # Test matching
    msg1 = create_test_message("/test arg1 arg2")
    assert await rule.check(msg1, context) == True
    assert context["command"] == "test"
    assert context["args"] == ["arg1", "arg2"]
    
    # Test non-matching
    msg2 = create_test_message("test without prefix")
    context = {}
    assert await rule.check(msg2, context) == False


@pytest.mark.asyncio
async def test_keyword_rule():
    """Test keyword rule matching."""
    rule = KeywordRule("hello", case_sensitive=False)
    
    msg1 = create_test_message("Hello world!")
    msg2 = create_test_message("Goodbye world!")
    
    assert await rule.check(msg1, {}) == True
    assert await rule.check(msg2, {}) == False


@pytest.mark.asyncio
async def test_router_command_decorator():
    """Test router command decorator."""
    router = Router()
    
    called = []
    
    @router.command("test")
    async def test_handler(envelope, context):
        called.append(envelope.raw_message)
        return "handled"
    
    msg = create_test_message("/test hello")
    results = await router.route(msg)
    
    assert len(called) == 1
    assert len(results) == 1
    assert results[0]["result"] == "handled"


@pytest.mark.asyncio
async def test_router_priority():
    """Test handler priority ordering."""
    router = Router()
    
    execution_order = []
    
    @router.keyword("test", priority=Priority.LOW)
    async def handler_low(envelope, context):
        execution_order.append("low")
    
    @router.keyword("test", priority=Priority.HIGH)
    async def handler_high(envelope, context):
        execution_order.append("high")
    
    msg = create_test_message("test message")
    await router.route(msg)
    
    # High priority should execute first
    assert execution_order == ["high", "low"]


@pytest.mark.asyncio
async def test_router_blocking():
    """Test blocking handler."""
    router = Router()
    
    called = []
    
    @router.keyword("test", block=True)
    async def handler1(envelope, context):
        called.append("handler1")
    
    @router.keyword("test")
    async def handler2(envelope, context):
        called.append("handler2")
    
    msg = create_test_message("test message")
    await router.route(msg)
    
    # Only first handler should be called
    assert called == ["handler1"]


@pytest.mark.asyncio
async def test_router_remove_handler():
    """Test removing handlers."""
    router = Router()
    
    @router.command("test")
    async def test_handler(envelope, context):
        return "handled"
    
    # Remove handler
    removed = router.remove_handler("test_handler")
    assert removed == True
    
    # Should not match anymore
    msg = create_test_message("/test")
    results = await router.route(msg)
    assert len(results) == 0

