"""Unit tests for event bus."""

import pytest
from src.core.event_bus import EventBus, Event


@pytest.mark.asyncio
async def test_event_bus_publish_subscribe():
    """Test event publishing and subscription."""
    bus = EventBus()
    await bus.start()
    
    received_events = []
    
    def handler(event: Event):
        received_events.append(event)
    
    # Subscribe to event
    bus.subscribe("test.event", handler)
    
    # Publish event
    await bus.publish("test.event", {"data": "test"})
    
    # Wait for processing
    await bus._event_queue.join()
    
    # Verify
    assert len(received_events) == 1
    assert received_events[0].name == "test.event"
    assert received_events[0].payload == {"data": "test"}
    
    await bus.stop()


@pytest.mark.asyncio
async def test_event_bus_wildcard_subscribe():
    """Test wildcard subscription."""
    bus = EventBus()
    await bus.start()
    
    received_events = []
    
    def handler(event: Event):
        received_events.append(event)
    
    # Subscribe to all events
    bus.subscribe_all(handler)
    
    # Publish multiple events
    await bus.publish("event1", {"data": "1"})
    await bus.publish("event2", {"data": "2"})
    
    # Wait for processing
    await bus._event_queue.join()
    
    # Verify
    assert len(received_events) == 2
    
    await bus.stop()


@pytest.mark.asyncio
async def test_event_bus_unsubscribe():
    """Test unsubscribing from events."""
    bus = EventBus()
    await bus.start()
    
    received_events = []
    
    def handler(event: Event):
        received_events.append(event)
    
    # Subscribe and publish
    bus.subscribe("test.event", handler)
    await bus.publish("test.event", {"data": "1"})
    await bus._event_queue.join()
    
    # Unsubscribe and publish again
    bus.unsubscribe("test.event", handler)
    await bus.publish("test.event", {"data": "2"})
    await bus._event_queue.join()
    
    # Should only receive first event
    assert len(received_events) == 1
    
    await bus.stop()


@pytest.mark.asyncio
async def test_event_bus_history():
    """Test event history."""
    bus = EventBus()
    await bus.start()
    
    # Publish events
    await bus.publish("event1", {"data": "1"})
    await bus.publish("event2", {"data": "2"})
    await bus._event_queue.join()
    
    # Get history
    history = bus.get_event_history()
    
    assert len(history) == 2
    assert history[0].name == "event1"
    assert history[1].name == "event2"
    
    await bus.stop()


@pytest.mark.asyncio
async def test_event_bus_stats():
    """Test event bus statistics."""
    bus = EventBus()
    await bus.start()
    
    def handler(event: Event):
        pass
    
    bus.subscribe("event1", handler)
    bus.subscribe("event2", handler)
    
    stats = bus.get_stats()
    
    assert stats["running"] == True
    assert stats["event_types"] == 2
    assert stats["total_subscribers"] == 2
    
    await bus.stop()

