"""Event bus for asynchronous event-driven communication."""

import asyncio
from typing import Any, Callable, Dict, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
import uuid

from .logger import get_logger

logger = get_logger(__name__)


@dataclass
class Event:
    """Event data structure."""
    
    name: str
    payload: Any
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    source: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        return {
            "event_id": self.event_id,
            "name": self.name,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "metadata": self.metadata,
        }


class EventBus:
    """Asynchronous event bus for publish-subscribe pattern."""

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._wildcard_subscribers: List[Callable] = []
        self._event_history: List[Event] = []
        self._max_history: int = 1000
        self._running: bool = False
        self._event_queue: asyncio.Queue = asyncio.Queue()
        self._processor_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the event bus processor."""
        if self._running:
            logger.warning("Event bus already running")
            return

        self._running = True
        self._processor_task = asyncio.create_task(self._process_events())
        logger.info("Event bus started")

    async def stop(self) -> None:
        """Stop the event bus processor."""
        if not self._running:
            return

        self._running = False
        
        # Wait for queue to be processed
        await self._event_queue.join()
        
        # Cancel processor task
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass

        logger.info("Event bus stopped")

    async def _process_events(self) -> None:
        """Process events from the queue."""
        while self._running:
            try:
                event = await asyncio.wait_for(
                    self._event_queue.get(),
                    timeout=1.0
                )
                await self._dispatch_event(event)
                self._event_queue.task_done()
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error("Error processing event", error=str(e), exc_info=True)

    async def _dispatch_event(self, event: Event) -> None:
        """Dispatch event to all subscribers."""
        # Add to history
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history.pop(0)

        # Get subscribers for this event
        subscribers = self._subscribers.get(event.name, []).copy()
        subscribers.extend(self._wildcard_subscribers)

        logger.debug(
            "Dispatching event",
            event_name=event.name,
            event_id=event.event_id,
            subscriber_count=len(subscribers)
        )

        # Call all subscribers
        tasks = []
        for subscriber in subscribers:
            task = asyncio.create_task(self._call_subscriber(subscriber, event))
            tasks.append(task)

        # Wait for all subscribers to complete
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _call_subscriber(self, subscriber: Callable, event: Event) -> None:
        """Call a single subscriber with error handling."""
        try:
            if asyncio.iscoroutinefunction(subscriber):
                await subscriber(event)
            else:
                subscriber(event)
        except Exception as e:
            logger.error(
                "Error in event subscriber",
                event_name=event.name,
                subscriber=subscriber.__name__,
                error=str(e),
                exc_info=True
            )

    async def publish(
        self,
        event_name: str,
        payload: Any,
        source: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Publish an event to the bus.
        
        Args:
            event_name: Name of the event
            payload: Event payload data
            source: Source of the event (optional)
            metadata: Additional metadata (optional)
            
        Returns:
            Event ID
        """
        event = Event(
            name=event_name,
            payload=payload,
            source=source,
            metadata=metadata or {}
        )

        await self._event_queue.put(event)
        
        logger.debug(
            "Event published",
            event_name=event_name,
            event_id=event.event_id
        )
        
        return event.event_id

    def subscribe(self, event_name: str, handler: Callable) -> None:
        """
        Subscribe to an event.
        
        Args:
            event_name: Name of the event to subscribe to
            handler: Callback function (can be async)
        """
        if event_name not in self._subscribers:
            self._subscribers[event_name] = []
        
        self._subscribers[event_name].append(handler)
        
        logger.debug(
            "Subscribed to event",
            event_name=event_name,
            handler=handler.__name__
        )

    def subscribe_all(self, handler: Callable) -> None:
        """
        Subscribe to all events (wildcard subscription).
        
        Args:
            handler: Callback function (can be async)
        """
        self._wildcard_subscribers.append(handler)
        logger.debug("Subscribed to all events", handler=handler.__name__)

    def unsubscribe(self, event_name: str, handler: Callable) -> None:
        """
        Unsubscribe from an event.
        
        Args:
            event_name: Name of the event
            handler: Handler to remove
        """
        if event_name in self._subscribers:
            try:
                self._subscribers[event_name].remove(handler)
                logger.debug(
                    "Unsubscribed from event",
                    event_name=event_name,
                    handler=handler.__name__
                )
            except ValueError:
                pass

    def unsubscribe_all(self, handler: Callable) -> None:
        """
        Unsubscribe from all events.
        
        Args:
            handler: Handler to remove
        """
        try:
            self._wildcard_subscribers.remove(handler)
            logger.debug("Unsubscribed from all events", handler=handler.__name__)
        except ValueError:
            pass

    def get_subscribers(self, event_name: Optional[str] = None) -> List[Callable]:
        """Get list of subscribers for an event."""
        if event_name is None:
            # Return all subscribers
            all_subscribers = []
            for subscribers in self._subscribers.values():
                all_subscribers.extend(subscribers)
            all_subscribers.extend(self._wildcard_subscribers)
            return all_subscribers
        return self._subscribers.get(event_name, []).copy()

    def get_event_history(self, limit: int = 100) -> List[Event]:
        """Get recent event history."""
        return self._event_history[-limit:]

    def clear_history(self) -> None:
        """Clear event history."""
        self._event_history.clear()
        logger.debug("Event history cleared")

    def get_stats(self) -> Dict[str, Any]:
        """Get event bus statistics."""
        return {
            "running": self._running,
            "queue_size": self._event_queue.qsize(),
            "event_types": len(self._subscribers),
            "total_subscribers": sum(len(subs) for subs in self._subscribers.values()),
            "wildcard_subscribers": len(self._wildcard_subscribers),
            "history_size": len(self._event_history),
        }


# Global event bus instance
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get the global event bus instance."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus

