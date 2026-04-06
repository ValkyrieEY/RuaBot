"""
Tests for EventBus component.

This test suite covers:
- Event publishing and subscription
- Wildcard subscriptions
- Event history tracking
- Statistics tracking
- Event queue management
- Async event processing
- Error handling in subscribers
"""
import asyncio
import pytest
from datetime import datetime
from typing import Any, Dict

from src.core.event_bus import EventBus, Event, get_event_bus


class TestEventBus:
    """Test suite for EventBus functionality."""

    @pytest.fixture
    def event_bus(self) -> EventBus:
        """Create a fresh event bus for each test."""
        return EventBus(max_queue_size=100)

    @pytest.mark.asyncio
    async def test_event_bus_initialization(self, event_bus: EventBus):
        """Test that event bus initializes correctly."""
        assert event_bus is not None
        assert not event_bus._running
        assert event_bus._max_queue_size == 100
        assert len(event_bus._subscribers) == 0
        assert len(event_bus._wildcard_subscribers) == 0
        assert len(event_bus._event_history) == 0

    @pytest.mark.asyncio
    async def test_event_bus_start_stop(self, event_bus: EventBus):
        """Test starting and stopping the event bus."""
        # Start event bus
        await event_bus.start()
        assert event_bus._running
        assert event_bus._processor_task is not None

        # Stop event bus
        await event_bus.stop()
        assert not event_bus._running

    @pytest.mark.asyncio
    async def test_publish_and_subscribe_single_handler(self, event_bus: EventBus):
        """Test publishing an event to a single subscriber."""
        received_events = []

        async def handler(event: Event):
            received_events.append(event)

        # Subscribe to event
        event_bus.subscribe("test.event", handler)

        # Start event bus
        await event_bus.start()

        # Publish event
        event_id = await event_bus.publish(
            "test.event",
            {"message": "test"},
            source="test"
        )

        # Wait for event to be processed
        await asyncio.sleep(0.1)

        # Verify event was received
        assert len(received_events) == 1
        assert received_events[0].name == "test.event"
        assert received_events[0].payload == {"message": "test"}
        assert received_events[0].event_id == event_id

        # Stop event bus
        await event_bus.stop()

    @pytest.mark.asyncio
    async def test_publish_and_subscribe_multiple_handlers(self, event_bus: EventBus):
        """Test publishing an event to multiple subscribers."""
        received_events_1 = []
        received_events_2 = []
        received_events_3 = []

        async def handler1(event: Event):
            received_events_1.append(event)

        async def handler2(event: Event):
            received_events_2.append(event)

        async def handler3(event: Event):
            received_events_3.append(event)

        # Subscribe handlers
        event_bus.subscribe("test.event", handler1)
        event_bus.subscribe("test.event", handler2)
        event_bus.subscribe("test.event", handler3)

        # Start event bus
        await event_bus.start()

        # Publish event
        await event_bus.publish(
            "test.event",
            {"message": "test"},
            source="test"
        )

        # Wait for event to be processed
        await asyncio.sleep(0.1)

        # Verify all handlers received the event
        assert len(received_events_1) == 1
        assert len(received_events_2) == 1
        assert len(received_events_3) == 1

        # Stop event bus
        await event_bus.stop()

    @pytest.mark.asyncio
    async def test_wildcard_subscription(self, event_bus: EventBus):
        """Test wildcard subscription to all events."""
        received_events = []

        async def wildcard_handler(event: Event):
            received_events.append(event.name)

        # Subscribe to all events
        event_bus.subscribe_all(wildcard_handler)

        # Start event bus
        await event_bus.start()

        # Publish multiple events
        await event_bus.publish("event.1", {"data": 1})
        await event_bus.publish("event.2", {"data": 2})
        await event_bus.publish("event.3", {"data": 3})

        # Wait for events to be processed
        await asyncio.sleep(0.1)

        # Verify wildcard handler received all events
        assert len(received_events) == 3
        assert "event.1" in received_events
        assert "event.2" in received_events
        assert "event.3" in received_events

        # Stop event bus
        await event_bus.stop()

    @pytest.mark.asyncio
    async def test_unsubscribe(self, event_bus: EventBus):
        """Test unsubscribing from events."""
        received_events = []

        async def handler(event: Event):
            received_events.append(event)

        # Subscribe
        event_bus.subscribe("test.event", handler)

        # Unsubscribe
        event_bus.unsubscribe("test.event", handler)

        # Start event bus
        await event_bus.start()

        # Publish event
        await event_bus.publish("test.event", {"message": "test"})

        # Wait for event to be processed
        await asyncio.sleep(0.1)

        # Verify handler did not receive event
        assert len(received_events) == 0

        # Stop event bus
        await event_bus.stop()

    @pytest.mark.asyncio
    async def test_unsubscribe_all(self, event_bus: EventBus):
        """Test unsubscribing from all events."""
        received_events = []

        async def handler(event: Event):
            received_events.append(event)

        # Subscribe to all events
        event_bus.subscribe_all(handler)

        # Unsubscribe from all events
        event_bus.unsubscribe_all(handler)

        # Start event bus
        await event_bus.start()

        # Publish events
        await event_bus.publish("event.1", {"data": 1})
        await event_bus.publish("event.2", {"data": 2})

        # Wait for events to be processed
        await asyncio.sleep(0.1)

        # Verify handler did not receive events
        assert len(received_events) == 0

        # Stop event bus
        await event_bus.stop()

    @pytest.mark.asyncio
    async def test_event_history(self, event_bus: EventBus):
        """Test event history tracking."""
        # Start event bus
        await event_bus.start()

        # Publish events
        await event_bus.publish("event.1", {"data": 1})
        await event_bus.publish("event.2", {"data": 2})
        await event_bus.publish("event.3", {"data": 3})

        # Wait for events to be processed
        await asyncio.sleep(0.1)

        # Get event history
        history = event_bus.get_event_history(limit=10)

        # Verify history
        assert len(history) == 3
        assert history[0].name == "event.1"
        assert history[1].name == "event.2"
        assert history[2].name == "event.3"

        # Stop event bus
        await event_bus.stop()

    @pytest.mark.asyncio
    async def test_event_history_limit(self, event_bus: EventBus):
        """Test event history size limit."""
        # Set small history limit
        event_bus._max_history = 5

        # Start event bus
        await event_bus.start()

        # Publish more events than history limit
        for i in range(10):
            await event_bus.publish(f"event.{i}", {"data": i})

        # Wait for events to be processed
        await asyncio.sleep(0.1)

        # Get event history
        history = event_bus.get_event_history(limit=10)

        # Verify only last 5 events are kept
        assert len(history) == 5
        assert history[0].name == "event.5"
        assert history[4].name == "event.9"

        # Stop event bus
        await event_bus.stop()

    @pytest.mark.asyncio
    async def test_clear_history(self, event_bus: EventBus):
        """Test clearing event history."""
        # Start event bus
        await event_bus.start()

        # Publish events
        await event_bus.publish("event.1", {"data": 1})
        await event_bus.publish("event.2", {"data": 2})

        # Wait for events to be processed
        await asyncio.sleep(0.1)

        # Verify history has events
        assert len(event_bus._event_history) > 0

        # Clear history
        event_bus.clear_history()

        # Verify history is cleared
        assert len(event_bus._event_history) == 0

        # Stop event bus
        await event_bus.stop()

    @pytest.mark.asyncio
    async def test_get_stats(self, event_bus: EventBus):
        """Test getting event bus statistics."""
        received_events = []

        async def handler(event: Event):
            received_events.append(event)

        # Subscribe to events
        event_bus.subscribe("event.1", handler)
        event_bus.subscribe("event.2", handler)
        event_bus.subscribe_all(handler)

        # Start event bus
        await event_bus.start()

        # Publish events
        await event_bus.publish("event.1", {"data": 1})
        await event_bus.publish("event.2", {"data": 2})

        # Wait for events to be processed
        await asyncio.sleep(0.1)

        # Get stats
        stats = event_bus.get_stats()

        # Verify stats
        assert stats["running"] is True
        assert stats["event_types"] == 2
        assert stats["total_subscribers"] == 2
        assert stats["wildcard_subscribers"] == 1
        assert stats["total_events_processed"] == 2
        assert stats["history_size"] == 2

        # Stop event bus
        await event_bus.stop()

    @pytest.mark.asyncio
    async def test_message_stats(self, event_bus: EventBus):
        """Test message statistics tracking."""
        # Start event bus
        await event_bus.start()

        # Publish message events
        await event_bus.publish("onebot.message", {"type": "received"})
        await event_bus.publish("onebot.message", {"type": "received"})
        await event_bus.publish("onebot.message_sent", {"type": "sent"})

        # Wait for events to be processed
        await asyncio.sleep(0.1)

        # Get stats
        stats = event_bus.get_stats()

        # Verify message stats
        assert stats["today_received"] == 2
        assert stats["today_sent"] == 1

        # Stop event bus
        await event_bus.stop()

    @pytest.mark.asyncio
    async def test_handler_error_handling(self, event_bus: EventBus):
        """Test that errors in handlers don't stop event processing."""
        received_events = []

        async def failing_handler(event: Event):
            raise ValueError("Test error")

        async def working_handler(event: Event):
            received_events.append(event)

        # Subscribe handlers
        event_bus.subscribe("test.event", failing_handler)
        event_bus.subscribe("test.event", working_handler)

        # Start event bus
        await event_bus.start()

        # Publish event
        await event_bus.publish("test.event", {"message": "test"})

        # Wait for event to be processed
        await asyncio.sleep(0.1)

        # Verify working handler still received event
        assert len(received_events) == 1

        # Stop event bus
        await event_bus.stop()

    @pytest.mark.asyncio
    async def test_sync_handler(self, event_bus: EventBus):
        """Test synchronous handlers."""
        received_events = []

        def sync_handler(event: Event):
            received_events.append(event)

        # Subscribe sync handler
        event_bus.subscribe("test.event", sync_handler)

        # Start event bus
        await event_bus.start()

        # Publish event
        await event_bus.publish("test.event", {"message": "test"})

        # Wait for event to be processed
        await asyncio.sleep(0.1)

        # Verify handler received event
        assert len(received_events) == 1

        # Stop event bus
        await event_bus.stop()

    @pytest.mark.asyncio
    async def test_event_queue_full_handling(self, event_bus: EventBus):
        """Test handling when event queue is full."""
        # Create event bus with small queue
        small_bus = EventBus(max_queue_size=2)

        # Start event bus
        await small_bus.start()

        # Don't process events (no subscribers)
        # Fill queue
        await small_bus.publish("event.1", {"data": 1})
        await small_bus.publish("event.2", {"data": 2})
        await small_bus.publish("event.3", {"data": 3})  # Should drop oldest

        # Wait a bit
        await asyncio.sleep(0.1)

        # Get history
        history = small_bus.get_event_history()

        # Verify oldest event was dropped
        assert len(history) == 2
        assert history[0].name == "event.2"
        assert history[1].name == "event.3"

        # Stop event bus
        await small_bus.stop()

    @pytest.mark.asyncio
    async def test_event_metadata(self, event_bus: EventBus):
        """Test event metadata."""
        received_events = []

        async def handler(event: Event):
            received_events.append(event)

        # Subscribe handler
        event_bus.subscribe("test.event", handler)

        # Start event bus
        await event_bus.start()

        # Publish event with metadata
        await event_bus.publish(
            "test.event",
            {"message": "test"},
            source="test_source",
            metadata={"key1": "value1", "key2": "value2"}
        )

        # Wait for event to be processed
        await asyncio.sleep(0.1)

        # Verify metadata
        assert len(received_events) == 1
        assert received_events[0].source == "test_source"
        assert received_events[0].metadata == {"key1": "value1", "key2": "value2"}

        # Stop event bus
        await event_bus.stop()

    @pytest.mark.asyncio
    async def test_emit_event_with_context(self, event_bus: EventBus):
        """Test emitting events with context."""
        # Start event bus
        await event_bus.start()

        # Emit event with context
        ctx = await event_bus.emit_event_with_context(
            "test.event",
            {"message": "test"},
            source="test_source",
            metadata={"key": "value"}
        )

        # Verify context
        assert ctx is not None
        assert ctx.event_name == "test.event"
        assert ctx.event_data == {"message": "test"}
        assert ctx.source == "test_source"

        # Stop event bus
        await event_bus.stop()

    @pytest.mark.asyncio
    async def test_get_subscribers(self, event_bus: EventBus):
        """Test getting list of subscribers."""
        async def handler1(event: Event):
            pass

        async def handler2(event: Event):
            pass

        # Subscribe to specific event
        event_bus.subscribe("event.1", handler1)

        # Subscribe to all events
        event_bus.subscribe_all(handler2)

        # Get subscribers for specific event
        subscribers_1 = event_bus.get_subscribers("event.1")
        assert len(subscribers_1) == 1

        # Get all subscribers
        all_subscribers = event_bus.get_subscribers()
        assert len(all_subscribers) == 2

    @pytest.mark.asyncio
    async def test_event_to_dict(self, event_bus: EventBus):
        """Test converting event to dictionary."""
        # Create event
        event = Event(
            name="test.event",
            payload={"message": "test"},
            source="test_source",
            metadata={"key": "value"}
        )

        # Convert to dict
        event_dict = event.to_dict()

        # Verify dict
        assert event_dict["name"] == "test.event"
        assert event_dict["payload"] == {"message": "test"}
        assert event_dict["source"] == "test_source"
        assert event_dict["metadata"] == {"key": "value"}
        assert "event_id" in event_dict
        assert "timestamp" in event_dict


class TestEventBusGlobal:
    """Test suite for global event bus instance."""

    @pytest.mark.asyncio
    async def test_get_event_bus_singleton(self):
        """Test that get_event_bus returns singleton instance."""
        bus1 = get_event_bus()
        bus2 = get_event_bus()

        assert bus1 is bus2

    @pytest.mark.asyncio
    async def test_global_event_bus_functionality(self):
        """Test that global event bus works correctly."""
        bus = get_event_bus()

        received_events = []

        async def handler(event: Event):
            received_events.append(event)

        # Subscribe
        bus.subscribe("test.event", handler)

        # Start
        await bus.start()

        # Publish
        await bus.publish("test.event", {"message": "test"})

        # Wait
        await asyncio.sleep(0.1)

        # Verify
        assert len(received_events) == 1

        # Stop
        await bus.stop()