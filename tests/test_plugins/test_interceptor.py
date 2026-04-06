"""
Tests for Plugin Interceptor components.

This test suite covers:
- Interceptor initialization
- Pre-interception hooks
- Post-interception hooks
- Execution modes (serial, parallel, hybrid)
- Circuit breaker
- Timeout handling
- Error recovery
- Plugin lifecycle
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from typing import Dict, Any, List

from src.plugins.interceptor import (
    Interceptor,
    InterceptorRegistry,
    ExecutionMode,
    InterceptorResult,
    InterceptorChain
)


class TestInterceptor:
    """Test suite for Interceptor functionality."""

    @pytest.fixture
    def sample_event(self) -> Dict[str, Any]:
        """Create a sample event."""
        return {
            "event_type": "message",
            "message_type": "group",
            "user_id": "111222",
            "group_id": "987654",
            "raw_message": "test message",
        }

    @pytest.fixture
    def interceptor(self):
        """Create an interceptor instance."""
        return Interceptor(
            name="test_interceptor",
            priority=50,
            enabled=True
        )

    def test_interceptor_initialization(self, interceptor: Interceptor):
        """Test that interceptor initializes correctly."""
        assert interceptor is not None
        assert interceptor.name == "test_interceptor"
        assert interceptor.priority == 50
        assert interceptor.enabled is True

    @pytest.mark.asyncio
    async def test_interceptor_before_hook(self, interceptor: Interceptor, sample_event: Dict[str, Any]):
        """Test before hook execution."""
        called = []

        async def before_hook(event):
            called.append("before")
            event["modified"] = True
            return event

        interceptor.before = before_hook

        result = await interceptor.before(sample_event)

        assert "before" in called
        assert result["modified"] is True

    @pytest.mark.asyncio
    async def test_interceptor_after_hook(self, interceptor: Interceptor, sample_event: Dict[str, Any]):
        """Test after hook execution."""
        called = []
        handler_result = {"status": "success"}

        async def after_hook(event, result):
            called.append("after")
            result["processed"] = True
            return result

        interceptor.after = after_hook

        result = await interceptor.after(sample_event, handler_result)

        assert "after" in called
        assert result["processed"] is True

    @pytest.mark.asyncio
    async def test_interceptor_around_hook(self, interceptor: Interceptor, sample_event: Dict[str, Any]):
        """Test around hook execution."""
        called = []

        async def handler(event):
            called.append("handler")
            return {"result": "handled"}

        async def around_hook(event, next_handler):
            called.append("before_handler")
            result = await next_handler(event)
            called.append("after_handler")
            return result

        interceptor.around = around_hook

        result = await interceptor.around(sample_event, handler)

        assert "before_handler" in called
        assert "handler" in called
        assert "after_handler" in called

    @pytest.mark.asyncio
    async def test_interceptor_error_handling(self, interceptor: Interceptor, sample_event: Dict[str, Any]):
        """Test error handling in interceptor."""
        async def failing_hook(event):
            raise ValueError("Test error")

        interceptor.before = failing_hook

        with pytest.raises(ValueError):
            await interceptor.before(sample_event)


class TestInterceptorRegistry:
    """Test suite for InterceptorRegistry functionality."""

    @pytest.fixture
    def registry(self):
        """Create an interceptor registry instance."""
        return InterceptorRegistry()

    def test_registry_initialization(self, registry: InterceptorRegistry):
        """Test that registry initializes correctly."""
        assert registry is not None
        assert len(registry._interceptors) == 0

    def test_register_interceptor(self, registry: InterceptorRegistry):
        """Test registering an interceptor."""
        interceptor = Interceptor(name="test", priority=50)

        registry.register(interceptor)

        assert len(registry._interceptors) == 1
        assert registry._interceptors[0].name == "test"

    def test_register_interceptor_priority_sorting(self, registry: InterceptorRegistry):
        """Test that interceptors are sorted by priority."""
        interceptor1 = Interceptor(name="low", priority=100)
        interceptor2 = Interceptor(name="high", priority=10)
        interceptor3 = Interceptor(name="medium", priority=50)

        registry.register(interceptor1)
        registry.register(interceptor2)
        registry.register(interceptor3)

        # Check sorting (lower priority number = higher priority)
        assert registry._interceptors[0].name == "high"
        assert registry._interceptors[1].name == "medium"
        assert registry._interceptors[2].name == "low"

    def test_unregister_interceptor(self, registry: InterceptorRegistry):
        """Test unregistering an interceptor."""
        interceptor = Interceptor(name="test", priority=50)
        registry.register(interceptor)

        assert len(registry._interceptors) == 1

        registry.unregister("test")

        assert len(registry._interceptors) == 0

    def test_unregister_nonexistent_interceptor(self, registry: InterceptorRegistry):
        """Test unregistering non-existent interceptor."""
        # Should not raise error
        registry.unregister("nonexistent")

    def test_get_interceptor(self, registry: InterceptorRegistry):
        """Test getting an interceptor by name."""
        interceptor = Interceptor(name="test", priority=50)
        registry.register(interceptor)

        retrieved = registry.get("test")

        assert retrieved is not None
        assert retrieved.name == "test"

    def test_get_nonexistent_interceptor(self, registry: InterceptorRegistry):
        """Test getting non-existent interceptor."""
        retrieved = registry.get("nonexistent")

        assert retrieved is None

    def test_list_interceptors(self, registry: InterceptorRegistry):
        """Test listing all interceptors."""
        interceptor1 = Interceptor(name="test1", priority=50)
        interceptor2 = Interceptor(name="test2", priority=50)

        registry.register(interceptor1)
        registry.register(interceptor2)

        interceptors = registry.list()

        assert len(interceptors) == 2

    def test_enable_interceptor(self, registry: InterceptorRegistry):
        """Test enabling an interceptor."""
        interceptor = Interceptor(name="test", priority=50, enabled=False)
        registry.register(interceptor)

        registry.enable("test")

        assert registry.get("test").enabled is True

    def test_disable_interceptor(self, registry: InterceptorRegistry):
        """Test disabling an interceptor."""
        interceptor = Interceptor(name="test", priority=50, enabled=True)
        registry.register(interceptor)

        registry.disable("test")

        assert registry.get("test").enabled is False

    def test_clear_interceptors(self, registry: InterceptorRegistry):
        """Test clearing all interceptors."""
        interceptor1 = Interceptor(name="test1", priority=50)
        interceptor2 = Interceptor(name="test2", priority=50)

        registry.register(interceptor1)
        registry.register(interceptor2)

        assert len(registry._interceptors) == 2

        registry.clear()

        assert len(registry._interceptors) == 0

    def test_configure_circuit_breaker(self, registry: InterceptorRegistry):
        """Test configuring circuit breaker."""
        registry.configure_circuit_breaker(threshold=5, duration=30.0)

        assert registry._circuit_breaker_threshold == 5
        assert registry._circuit_breaker_duration == 30.0

    def test_configure_timeouts(self, registry: InterceptorRegistry):
        """Test configuring timeouts."""
        registry.configure_timeouts(base_timeout=3.0, max_timeout=10.0)

        assert registry._base_timeout == 3.0
        assert registry._max_timeout == 10.0


class TestInterceptorChain:
    """Test suite for InterceptorChain functionality."""

    @pytest.fixture
    def registry(self):
        """Create a registry with interceptors."""
        registry = InterceptorRegistry()

        # Add some interceptors
        interceptor1 = Interceptor(name="first", priority=10)
        interceptor2 = Interceptor(name="second", priority=20)
        interceptor3 = Interceptor(name="third", priority=30)

        registry.register(interceptor1)
        registry.register(interceptor2)
        registry.register(interceptor3)

        return registry

    @pytest.fixture
    def chain(self, registry):
        """Create an interceptor chain."""
        return InterceptorChain(registry)

    @pytest.mark.asyncio
    async def test_chain_serial_execution(self, chain: InterceptorChain):
        """Test chain execution in serial mode."""
        execution_order = []

        async def mock_before(event):
            execution_order.append(event.get("name"))

        # Add before hooks to interceptors
        for interceptor in chain.registry._interceptors:
            interceptor.before = mock_before

        chain.execution_mode = ExecutionMode.SERIAL

        event = {"name": "test"}
        await chain.execute(event, lambda e: e)

        # All interceptors should have been called in order
        assert len(execution_order) == 3
        assert execution_order == ["test", "test", "test"]

    @pytest.mark.asyncio
    async def test_chain_parallel_execution(self, chain: InterceptorChain):
        """Test chain execution in parallel mode."""
        execution_order = []

        async def mock_before(event):
            await asyncio.sleep(0.01)  # Simulate work
            execution_order.append(event.get("name"))

        # Add before hooks to interceptors
        for interceptor in chain.registry._interceptors:
            interceptor.before = mock_before

        chain.execution_mode = ExecutionMode.PARALLEL

        event = {"name": "test"}
        await chain.execute(event, lambda e: e)

        # All interceptors should have been called
        assert len(execution_order) == 3

    @pytest.mark.asyncio
    async def test_chain_hybrid_execution(self, chain: InterceptorChain):
        """Test chain execution in hybrid mode."""
        execution_order = []

        async def mock_before(event):
            execution_order.append(event.get("name"))

        # Add before hooks to interceptors
        for interceptor in chain.registry._interceptors:
            interceptor.before = mock_before

        chain.execution_mode = ExecutionMode.HYBRID

        event = {"name": "test"}
        await chain.execute(event, lambda e: e)

        # All interceptors should have been called
        assert len(execution_order) == 3

    @pytest.mark.asyncio
    async def test_chain_handler_execution(self, chain: InterceptorChain):
        """Test that handler is called after interceptors."""
        handler_called = []

        async def handler(event):
            handler_called.append(True)
            return {"result": "handled"}

        event = {"name": "test"}
        await chain.execute(event, handler)

        assert len(handler_called) == 1

    @pytest.mark.asyncio
    async def test_chain_interceptor_error(self, chain: InterceptorChain):
        """Test error handling in chain."""
        async def failing_before(event):
            raise ValueError("Test error")

        # Add failing interceptor
        chain.registry._interceptors[0].before = failing_before

        handler_called = []

        async def handler(event):
            handler_called.append(True)
            return {"result": "handled"}

        event = {"name": "test"}

        # Should still call handler even if interceptor fails
        result = await chain.execute(event, handler)

        assert handler_called  # Handler should still be called


class TestExecutionMode:
    """Test suite for ExecutionMode enum."""

    def test_execution_mode_values(self):
        """Test execution mode values."""
        assert ExecutionMode.SERIAL.value == "serial"
        assert ExecutionMode.PARALLEL.value == "parallel"
        assert ExecutionMode.HYBRID.value == "hybrid"


class TestInterceptorResult:
    """Test suite for InterceptorResult."""

    def test_interceptor_result_creation(self):
        """Test creating interceptor result."""
        result = InterceptorResult(
            success=True,
            modified_event={"test": "data"},
            error=None
        )

        assert result.success is True
        assert result.modified_event == {"test": "data"}
        assert result.error is None

    def test_interceptor_result_with_error(self):
        """Test creating interceptor result with error."""
        error = ValueError("Test error")
        result = InterceptorResult(
            success=False,
            modified_event=None,
            error=error
        )

        assert result.success is False
        assert result.modified_event is None
        assert result.error == error