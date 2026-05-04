"""Tests for the current plugin interceptor registry."""

import asyncio
from typing import Any, Dict, Optional

import pytest

from src.plugins.interceptor import (
    EventInterceptor,
    ExecutionMode,
    InterceptorRegistry,
    InterceptorResult,
    MessageInterceptor,
)


class SampleMessageInterceptor(MessageInterceptor):
    def __init__(
        self,
        plugin_id: str,
        priority: int = 100,
        *,
        result: Optional[InterceptorResult] = None,
        delay: float = 0.0,
        fail: bool = False,
    ):
        super().__init__(plugin_id, priority)
        self.result = result or InterceptorResult()
        self.delay = delay
        self.fail = fail
        self.calls = 0

    async def intercept_message(
        self,
        action: str,
        params: Dict[str, Any],
        source_plugin: Optional[str] = None,
    ) -> InterceptorResult:
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.fail:
            raise ValueError("interceptor failed")
        return self.result


class SampleEventInterceptor(EventInterceptor):
    def __init__(
        self,
        plugin_id: str,
        priority: int = 100,
        *,
        result: Optional[InterceptorResult] = None,
    ):
        super().__init__(plugin_id, priority)
        self.result = result or InterceptorResult()
        self.calls = 0

    async def intercept_event(
        self,
        event_name: str,
        event_data: Dict[str, Any],
        source: Optional[str] = None,
    ) -> InterceptorResult:
        self.calls += 1
        return self.result


def test_interceptor_result_helpers():
    result = InterceptorResult(modified_data={"message": "changed"})
    blocked = InterceptorResult(allow=False, block_reason="blocked")

    assert result.is_modified() is True
    assert result.is_blocked() is False
    assert blocked.is_blocked() is True


def test_registry_registers_and_sorts_interceptors():
    registry = InterceptorRegistry()
    low = SampleMessageInterceptor("low", priority=100)
    high = SampleMessageInterceptor("high", priority=10)
    event = SampleEventInterceptor("event", priority=50)

    registry.register_message_interceptor(low)
    registry.register_message_interceptor(high)
    registry.register_event_interceptor(event)

    assert [item.plugin_id for item in registry.get_message_interceptors()] == ["high", "low"]
    assert [item.plugin_id for item in registry.get_event_interceptors()] == ["event"]


@pytest.mark.asyncio
async def test_serial_message_interception_applies_priority_order():
    registry = InterceptorRegistry(execution_mode=ExecutionMode.SERIAL)
    registry.register_message_interceptor(
        SampleMessageInterceptor(
            "first",
            priority=10,
            result=InterceptorResult(modified_data={"message": "first", "count": 1}),
        )
    )
    registry.register_message_interceptor(
        SampleMessageInterceptor(
            "second",
            priority=20,
            result=InterceptorResult(modified_data={"message": "second", "count": 2}),
        )
    )

    allow, params = await registry.intercept_message("send_group_msg", {"message": "original"})

    assert allow is True
    assert params == {"message": "second", "count": 2}


@pytest.mark.asyncio
async def test_parallel_message_interception_merges_same_priority_results():
    registry = InterceptorRegistry(execution_mode=ExecutionMode.PARALLEL)
    registry.register_message_interceptor(
        SampleMessageInterceptor(
            "a",
            priority=10,
            result=InterceptorResult(modified_data={"message": "changed"}),
        )
    )
    registry.register_message_interceptor(
        SampleMessageInterceptor(
            "b",
            priority=10,
            result=InterceptorResult(modified_data={"extra": {"ok": True}}),
        )
    )

    allow, params = await registry.intercept_message("send_private_msg", {"message": "original"})

    assert allow is True
    assert params == {"message": "changed", "extra": {"ok": True}}


@pytest.mark.asyncio
async def test_message_interceptor_can_block():
    registry = InterceptorRegistry()
    registry.register_message_interceptor(
        SampleMessageInterceptor(
            "blocker",
            result=InterceptorResult(allow=False, block_reason="blocked"),
        )
    )

    allow, params = await registry.intercept_message("send_group_msg", {"message": "original"})

    assert allow is False
    assert params == {"message": "original"}


@pytest.mark.asyncio
async def test_event_interception_modifies_payload():
    registry = InterceptorRegistry(execution_mode=ExecutionMode.SERIAL)
    registry.register_event_interceptor(
        SampleEventInterceptor(
            "event-plugin",
            result=InterceptorResult(modified_data={"raw_message": "changed"}),
        )
    )

    allow, event = await registry.intercept_event(
        "message.received",
        {"raw_message": "original"},
        source="onebot",
    )

    assert allow is True
    assert event == {"raw_message": "changed"}


@pytest.mark.asyncio
async def test_failing_interceptor_updates_stats_and_continues():
    registry = InterceptorRegistry()
    registry.register_message_interceptor(SampleMessageInterceptor("bad", fail=True))
    registry.register_message_interceptor(
        SampleMessageInterceptor(
            "good",
            priority=200,
            result=InterceptorResult(modified_data={"message": "ok"}),
        )
    )

    allow, params = await registry.intercept_message("send_msg", {"message": "original"})
    stats = registry.get_stats()

    assert allow is True
    assert params == {"message": "ok"}
    assert stats["bad"].total_failures == 1
    assert stats["good"].total_calls == 1


def test_unregister_and_summary():
    registry = InterceptorRegistry()
    registry.register_message_interceptor(SampleMessageInterceptor("plugin"))
    registry.register_event_interceptor(SampleEventInterceptor("plugin"))

    registry.unregister_all("plugin")
    summary = registry.get_stats_summary()

    assert registry.get_message_interceptors() == []
    assert registry.get_event_interceptors() == []
    assert summary["execution_mode"] == ExecutionMode.HYBRID.value


def test_execution_mode_values():
    assert ExecutionMode.SERIAL.value == "serial"
    assert ExecutionMode.PARALLEL.value == "parallel"
    assert ExecutionMode.HYBRID.value == "hybrid"
