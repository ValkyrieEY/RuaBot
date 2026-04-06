"""
Tests for Router and Rules components.

This test suite covers:
- Router initialization
- Handler registration
- Rule matching
- Message routing
- Priority handling
- Blocking handlers
- Rule composition (AND/OR)
- Command rules
- Keyword rules
- Regex rules
- User/Group rules
"""
import pytest
import re
from datetime import datetime
from typing import Dict, Any

from src.router.router import (
    Router,
    Handler,
    Priority,
    Rule,
    CommandRule,
    KeywordRule,
    RegexRule,
    MessageTypeRule,
    UserRule,
    GroupRule,
    AndRule,
    OrRule,
)
from src.protocol.base import MessageEnvelope, MessageSegment


class TestRouter:
    """Test suite for Router functionality."""

    @pytest.fixture
    def router(self) -> Router:
        """Create a router instance."""
        return Router()

    @pytest.fixture
    def sample_envelope(self) -> MessageEnvelope:
        """Create a sample message envelope."""
        return MessageEnvelope(
            message_id="123456",
            message_type="group",
            user_id="111222",
            timestamp=datetime.now(),
            raw_message="Hello, this is a test message",
            message=[
                MessageSegment(type="text", data={"text": "Hello, this is a test message"})
            ],
            group_id="987654",
            sender={"user_id": "111222", "nickname": "TestUser"},
        )

    def test_router_initialization(self, router: Router):
        """Test that router initializes correctly."""
        assert router is not None
        assert len(router._handlers) == 0

    def test_add_handler(self, router: Router):
        """Test adding a handler."""
        async def handler(envelope, context):
            return "handled"

        router.add_handler(
            name="test_handler",
            rule=KeywordRule("test"),
            callback=handler,
            priority=Priority.NORMAL
        )

        assert len(router._handlers) == 1
        assert router._handlers[0].name == "test_handler"

    def test_add_handler_priority_sorting(self, router: Router):
        """Test that handlers are sorted by priority."""
        async def handler1(envelope, context):
            return "1"

        async def handler2(envelope, context):
            return "2"

        async def handler3(envelope, context):
            return "3"

        # Add handlers in random priority order
        router.add_handler("handler2", KeywordRule("test"), handler2, Priority.NORMAL)
        router.add_handler("handler1", KeywordRule("test"), handler1, Priority.HIGH)
        router.add_handler("handler3", KeywordRule("test"), handler3, Priority.LOW)

        # Check sorting
        assert router._handlers[0].name == "handler1"  # HIGH priority
        assert router._handlers[1].name == "handler2"  # NORMAL priority
        assert router._handlers[2].name == "handler3"  # LOW priority

    @pytest.mark.asyncio
    async def test_route_single_handler(self, router: Router, sample_envelope: MessageEnvelope):
        """Test routing to a single handler."""
        called = []

        async def handler(envelope, context):
            called.append(handler.__name__)
            return "result"

        router.add_handler(
            name="test_handler",
            rule=KeywordRule("test"),
            callback=handler
        )

        # Message doesn't match
        results = await router.route(sample_envelope)
        assert len(called) == 0

        # Message matches
        sample_envelope.raw_message = "test message"
        results = await router.route(sample_envelope)
        assert len(called) == 1

    @pytest.mark.asyncio
    async def test_route_multiple_handlers(self, router: Router, sample_envelope: MessageEnvelope):
        """Test routing to multiple handlers."""
        called = []

        async def handler1(envelope, context):
            called.append("handler1")
            return "result1"

        async def handler2(envelope, context):
            called.append("handler2")
            return "result2"

        router.add_handler("handler1", KeywordRule("hello"), handler1)
        router.add_handler("handler2", KeywordRule("test"), handler2)

        sample_envelope.raw_message = "hello test"
        results = await router.route(sample_envelope)

        assert len(called) == 2
        assert "handler1" in called
        assert "handler2" in called

    @pytest.mark.asyncio
    async def test_blocking_handler(self, router: Router, sample_envelope: MessageEnvelope):
        """Test that blocking handler stops further processing."""
        called = []

        async def handler1(envelope, context):
            called.append("handler1")
            return "result1"

        async def handler2(envelope, context):
            called.append("handler2")
            return "result2"

        router.add_handler("handler1", KeywordRule("test"), handler1, block=True)
        router.add_handler("handler2", KeywordRule("test"), handler2)

        sample_envelope.raw_message = "test message"
        results = await router.route(sample_envelope)

        # Only handler1 should be called
        assert len(called) == 1
        assert "handler1" in called
        assert "handler2" not in called

    @pytest.mark.asyncio
    async def test_remove_handler(self, router: Router):
        """Test removing a handler."""
        async def handler(envelope, context):
            return "result"

        router.add_handler("test_handler", KeywordRule("test"), handler)
        assert len(router._handlers) == 1

        router.remove_handler("test_handler")
        assert len(router._handlers) == 0

    def test_remove_nonexistent_handler(self, router: Router):
        """Test removing non-existent handler."""
        success = router.remove_handler("nonexistent")
        assert success is False

    def test_clear_handlers(self, router: Router):
        """Test clearing all handlers."""
        async def handler1(envelope, context):
            return "1"

        async def handler2(envelope, context):
            return "2"

        router.add_handler("handler1", KeywordRule("test1"), handler1)
        router.add_handler("handler2", KeywordRule("test2"), handler2)

        assert len(router._handlers) == 2

        router.clear_handlers()
        assert len(router._handlers) == 0

    def test_get_handlers(self, router: Router):
        """Test getting all handlers."""
        async def handler(envelope, context):
            return "result"

        router.add_handler("test_handler", KeywordRule("test"), handler)

        handlers = router.get_handlers()
        assert len(handlers) == 1
        assert handlers[0].name == "test_handler"

    @pytest.mark.asyncio
    async def test_handler_error(self, router: Router, sample_envelope: MessageEnvelope):
        """Test that handler errors don't stop routing."""
        called = []

        async def failing_handler(envelope, context):
            called.append("failing")
            raise ValueError("Test error")

        async def working_handler(envelope, context):
            called.append("working")
            return "result"

        router.add_handler("failing", KeywordRule("test"), failing_handler)
        router.add_handler("working", KeywordRule("test"), working_handler)

        sample_envelope.raw_message = "test message"
        await router.route(sample_envelope)

        # Both handlers should be attempted
        assert "failing" in called
        assert "working" in called

    @pytest.mark.asyncio
    async def test_sync_handler(self, router: Router, sample_envelope: MessageEnvelope):
        """Test synchronous handler."""
        called = []

        def sync_handler(envelope, context):
            called.append("sync")
            return "result"

        router.add_handler("sync", KeywordRule("test"), sync_handler)

        sample_envelope.raw_message = "test message"
        await router.route(sample_envelope)

        assert len(called) == 1

    @pytest.mark.asyncio
    async def test_route_results(self, router: Router, sample_envelope: MessageEnvelope):
        """Test that route returns results."""
        async def handler1(envelope, context):
            return "result1"

        async def handler2(envelope, context):
            return "result2"

        router.add_handler("handler1", KeywordRule("hello"), handler1)
        router.add_handler("handler2", KeywordRule("test"), handler2)

        sample_envelope.raw_message = "hello test"
        results = await router.route(sample_envelope)

        assert len(results) == 2
        assert any(r["handler"] == "handler1" for r in results)
        assert any(r["handler"] == "handler2" for r in results)


class TestRules:
    """Test suite for Rule functionality."""

    @pytest.fixture
    def envelope(self) -> MessageEnvelope:
        """Create a sample envelope."""
        return MessageEnvelope(
            message_id="123",
            message_type="group",
            user_id="111222",
            timestamp=datetime.now(),
            raw_message="test message",
            message=[MessageSegment(type="text", data={"text": "test message"})],
            group_id="987654",
        )

    @pytest.mark.asyncio
    async def test_command_rule_match(self, envelope: MessageEnvelope):
        """Test command rule matching."""
        rule = CommandRule("test", prefixes=["/", "!", "."])

        envelope.raw_message = "/test"
        context = {}
        assert await rule.check(envelope, context) is True
        assert context["command"] == "test"
        assert context["prefix"] == "/"

        envelope.raw_message = "!test"
        context = {}
        assert await rule.check(envelope, context) is True
        assert context["prefix"] == "!"

    @pytest.mark.asyncio
    async def test_command_rule_with_args(self, envelope: MessageEnvelope):
        """Test command rule with arguments."""
        rule = CommandRule("test")

        envelope.raw_message = "/test arg1 arg2"
        context = {}
        assert await rule.check(envelope, context) is True
        assert context["args"] == ["arg1", "arg2"]
        assert context["args_str"] == "arg1 arg2"

    @pytest.mark.asyncio
    async def test_command_rule_no_match(self, envelope: MessageEnvelope):
        """Test command rule not matching."""
        rule = CommandRule("test")

        envelope.raw_message = "other command"
        context = {}
        assert await rule.check(envelope, context) is False

    @pytest.mark.asyncio
    async def test_keyword_rule_match(self, envelope: MessageEnvelope):
        """Test keyword rule matching."""
        rule = KeywordRule("test")

        envelope.raw_message = "this is a test message"
        assert await rule.check(envelope, {}) is True

        envelope.raw_message = "no match here"
        assert await rule.check(envelope, {}) is False

    @pytest.mark.asyncio
    async def test_keyword_rule_case_sensitive(self, envelope: MessageEnvelope):
        """Test keyword rule with case sensitivity."""
        rule = KeywordRule("Test", case_sensitive=True)

        envelope.raw_message = "Test message"
        assert await rule.check(envelope, {}) is True

        envelope.raw_message = "test message"
        assert await rule.check(envelope, {}) is False

    @pytest.mark.asyncio
    async def test_keyword_rule_case_insensitive(self, envelope: MessageEnvelope):
        """Test keyword rule case insensitive."""
        rule = KeywordRule("Test", case_sensitive=False)

        envelope.raw_message = "Test message"
        assert await rule.check(envelope, {}) is True

        envelope.raw_message = "test message"
        assert await rule.check(envelope, {}) is True

    @pytest.mark.asyncio
    async def test_regex_rule_match(self, envelope: MessageEnvelope):
        """Test regex rule matching."""
        rule = RegexRule(r"\d{4}-\d{2}-\d{2}")

        envelope.raw_message = "Date: 2024-03-22"
        context = {}
        assert await rule.check(envelope, context) is True
        assert "regex_match" in context

        envelope.raw_message = "No date here"
        assert await rule.check(envelope, {}) is False

    @pytest.mark.asyncio
    async def test_regex_rule_groups(self, envelope: MessageEnvelope):
        """Test regex rule with groups."""
        rule = RegexRule(r"(\d{4})-(\d{2})-(\d{2})")

        envelope.raw_message = "2024-03-22"
        context = {}
        await rule.check(envelope, context)

        assert context["regex_groups"] == ("2024", "03", "22")

    @pytest.mark.asyncio
    async def test_message_type_rule(self, envelope: MessageEnvelope):
        """Test message type rule."""
        rule = MessageTypeRule("group")

        envelope.message_type = "group"
        assert await rule.check(envelope, {}) is True

        envelope.message_type = "private"
        assert await rule.check(envelope, {}) is False

    @pytest.mark.asyncio
    async def test_user_rule(self, envelope: MessageEnvelope):
        """Test user rule."""
        rule = UserRule(["111222", "333444"])

        envelope.user_id = "111222"
        assert await rule.check(envelope, {}) is True

        envelope.user_id = "999999"
        assert await rule.check(envelope, {}) is False

    @pytest.mark.asyncio
    async def test_group_rule(self, envelope: MessageEnvelope):
        """Test group rule."""
        rule = GroupRule(["987654", "555666"])

        envelope.group_id = "987654"
        assert await rule.check(envelope, {}) is True

        envelope.group_id = None
        assert await rule.check(envelope, {}) is False

        envelope.group_id = "999999"
        assert await rule.check(envelope, {}) is False

    @pytest.mark.asyncio
    async def test_and_rule(self, envelope: MessageEnvelope):
        """Test AND rule composition."""
        rule1 = KeywordRule("test")
        rule2 = UserRule(["111222"])

        and_rule = rule1 & rule2

        envelope.raw_message = "test message"
        envelope.user_id = "111222"
        assert await and_rule.check(envelope, {}) is True

        envelope.user_id = "999999"
        assert await and_rule.check(envelope, {}) is False

    @pytest.mark.asyncio
    async def test_or_rule(self, envelope: MessageEnvelope):
        """Test OR rule composition."""
        rule1 = KeywordRule("hello")
        rule2 = KeywordRule("world")

        or_rule = rule1 | rule2

        envelope.raw_message = "hello there"
        assert await or_rule.check(envelope, {}) is True

        envelope.raw_message = "world peace"
        assert await or_rule.check(envelope, {}) is True

        envelope.raw_message = "test message"
        assert await or_rule.check(envelope, {}) is False

    @pytest.mark.asyncio
    async def test_complex_rule_composition(self, envelope: MessageEnvelope):
        """Test complex rule composition."""
        # (keyword OR command) AND (user OR group)
        keyword_rule = KeywordRule("help")
        command_rule = CommandRule("help")
        user_rule = UserRule(["111222"])
        group_rule = GroupRule(["987654"])

        complex_rule = (keyword_rule | command_rule) & (user_rule | group_rule)

        # Match: keyword + user
        envelope.raw_message = "help me"
        envelope.user_id = "111222"
        envelope.group_id = "000000"
        assert await complex_rule.check(envelope, {}) is True

        # Match: command + group
        envelope.raw_message = "/help"
        envelope.user_id = "999999"
        envelope.group_id = "987654"
        assert await complex_rule.check(envelope, {}) is True

        # No match: keyword + neither user nor group
        envelope.raw_message = "help me"
        envelope.user_id = "999999"
        envelope.group_id = "000000"
        assert await complex_rule.check(envelope, {}) is False


class TestRouterDecorators:
    """Test suite for Router decorator methods."""

    @pytest.fixture
    def router(self) -> Router:
        """Create a router instance."""
        return Router()

    def test_command_decorator(self, router: Router):
        """Test command decorator."""
        @router.command("test", prefixes=["/"])
        async def test_handler(envelope, context):
            return "handled"

        assert len(router._handlers) == 1
        assert router._handlers[0].name == "test_handler"

    def test_keyword_decorator(self, router: Router):
        """Test keyword decorator."""
        @router.keyword("hello")
        async def hello_handler(envelope, context):
            return "hello"

        assert len(router._handlers) == 1
        assert router._handlers[0].name == "hello_handler"

    def test_regex_decorator(self, router: Router):
        """Test regex decorator."""
        @router.regex(r"\d+")
        async def number_handler(envelope, context):
            return "number"

        assert len(router._handlers) == 1
        assert router._handlers[0].name == "number_handler"

    def test_decorator_with_block(self, router: Router):
        """Test decorator with block parameter."""
        @router.keyword("stop", block=True)
        async def stop_handler(envelope, context):
            return "stopped"

        assert router._handlers[0].block is True

    def test_decorator_with_priority(self, router: Router):
        """Test decorator with priority parameter."""
        @router.keyword("high", priority=Priority.HIGH)
        async def high_handler(envelope, context):
            return "high"

        assert router._handlers[0].priority == Priority.HIGH