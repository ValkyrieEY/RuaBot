"""Plugin interceptor system for high-privilege plugins.

This module provides an interceptor system that allows plugins to:
- Intercept and modify messages before they are sent
- Intercept and modify events before they are dispatched
- Block messages or events
- Monitor all plugin operations
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple
from enum import Enum
from dataclasses import dataclass


class InterceptorType(str, Enum):
    """Interceptor type."""
    MESSAGE = "message"  # Intercept message sending
    EVENT = "event"  # Intercept event dispatching


@dataclass
class InterceptorResult:
    """Result of interceptor execution."""
    
    # Whether to continue processing (False = block)
    allow: bool = True
    
    # Modified data (None = no modification)
    modified_data: Optional[Dict[str, Any]] = None
    
    # Reason for blocking (if allow=False)
    block_reason: Optional[str] = None
    
    def is_blocked(self) -> bool:
        """Check if operation is blocked."""
        return not self.allow
    
    def is_modified(self) -> bool:
        """Check if data was modified."""
        return self.modified_data is not None


class MessageInterceptor(ABC):
    """Base class for message interceptors.
    
    Intercepts messages before they are sent to OneBot API.
    """
    
    def __init__(self, plugin_id: str, priority: int = 100):
        """Initialize interceptor.
        
        Args:
            plugin_id: ID of the plugin registering this interceptor (author/name)
            priority: Priority (lower = earlier execution)
        """
        self.plugin_id = plugin_id
        self.priority = priority
    
    @abstractmethod
    async def intercept_message(
        self,
        action: str,
        params: Dict[str, Any],
        source_plugin: Optional[str] = None
    ) -> InterceptorResult:
        """Intercept a message before sending.
        
        Args:
            action: API action name (e.g., 'send_group_msg', 'send_private_msg')
            params: Message parameters
            source_plugin: ID of plugin that initiated the message (if from plugin)
        
        Returns:
            InterceptorResult with allow/modified_data
        """
        pass


class EventInterceptor(ABC):
    """Base class for event interceptors.
    
    Intercepts events before they are dispatched to plugins.
    """
    
    def __init__(self, plugin_id: str, priority: int = 100):
        """Initialize interceptor.
        
        Args:
            plugin_id: ID of the plugin registering this interceptor (author/name)
            priority: Priority (lower = earlier execution)
        """
        self.plugin_id = plugin_id
        self.priority = priority
    
    @abstractmethod
    async def intercept_event(
        self,
        event_name: str,
        event_data: Dict[str, Any],
        source: Optional[str] = None
    ) -> InterceptorResult:
        """Intercept an event before dispatching.
        
        Args:
            event_name: Event name (e.g., 'onebot.message')
            event_data: Event data
            source: Event source
        
        Returns:
            InterceptorResult with allow/modified_data
        """
        pass


class InterceptorRegistry:
    """Registry for managing interceptors."""
    
    def __init__(self):
        """Initialize registry."""
        self._message_interceptors: list[MessageInterceptor] = []
        self._event_interceptors: list[EventInterceptor] = []
    
    def register_message_interceptor(self, interceptor: MessageInterceptor):
        """Register a message interceptor.
        
        Args:
            interceptor: MessageInterceptor instance
        """
        self._message_interceptors.append(interceptor)
        # Sort by priority (lower priority = earlier execution)
        self._message_interceptors.sort(key=lambda x: x.priority)
    
    def register_event_interceptor(self, interceptor: EventInterceptor):
        """Register an event interceptor.
        
        Args:
            interceptor: EventInterceptor instance
        """
        self._event_interceptors.append(interceptor)
        # Sort by priority (lower priority = earlier execution)
        self._event_interceptors.sort(key=lambda x: x.priority)
    
    def unregister_message_interceptor(self, plugin_id: str) -> bool:
        """Unregister all message interceptors for a plugin.
        
        Args:
            plugin_id: Plugin ID
        
        Returns:
            True if any interceptors were removed
        """
        before = len(self._message_interceptors)
        self._message_interceptors = [
            i for i in self._message_interceptors if i.plugin_id != plugin_id
        ]
        return len(self._message_interceptors) < before
    
    def unregister_event_interceptor(self, plugin_id: str) -> bool:
        """Unregister all event interceptors for a plugin.
        
        Args:
            plugin_id: Plugin ID
        
        Returns:
            True if any interceptors were removed
        """
        before = len(self._event_interceptors)
        self._event_interceptors = [
            i for i in self._event_interceptors if i.plugin_id != plugin_id
        ]
        return len(self._event_interceptors) < before
    
    def unregister_all(self, plugin_id: str):
        """Unregister all interceptors for a plugin.
        
        Args:
            plugin_id: Plugin ID
        """
        self.unregister_message_interceptor(plugin_id)
        self.unregister_event_interceptor(plugin_id)
    
    async def intercept_message(
        self,
        action: str,
        params: Dict[str, Any],
        source_plugin: Optional[str] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """Run all message interceptors.
        
        Args:
            action: API action name
            params: Message parameters
            source_plugin: Source plugin ID
        
        Returns:
            Tuple of (allow, modified_params)
        """
        current_params = params.copy()
        
        for interceptor in self._message_interceptors:
            try:
                result = await interceptor.intercept_message(action, current_params, source_plugin)
                
                if result.is_blocked():
                    return (False, current_params)
                
                if result.is_modified():
                    current_params = result.modified_data
                    
            except Exception as e:
                from ...core.logger import get_logger
                logger = get_logger(__name__)
                logger.error(
                    f"Error in message interceptor {interceptor.plugin_id}: {e}",
                    exc_info=True
                )
                # Continue to next interceptor on error
        
        return (True, current_params)
    
    async def intercept_event(
        self,
        event_name: str,
        event_data: Dict[str, Any],
        source: Optional[str] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """Run all event interceptors.
        
        Args:
            event_name: Event name
            event_data: Event data
            source: Event source
        
        Returns:
            Tuple of (allow, modified_event_data)
        """
        current_data = event_data.copy()
        
        for interceptor in self._event_interceptors:
            try:
                result = await interceptor.intercept_event(event_name, current_data, source)
                
                if result.is_blocked():
                    return (False, current_data)
                
                if result.is_modified():
                    current_data = result.modified_data
                    
            except Exception as e:
                from ...core.logger import get_logger
                logger = get_logger(__name__)
                logger.error(
                    f"Error in event interceptor {interceptor.plugin_id}: {e}",
                    exc_info=True
                )
                # Continue to next interceptor on error
        
        return (True, current_data)
    
    def get_message_interceptors(self) -> list[MessageInterceptor]:
        """Get all message interceptors."""
        return self._message_interceptors.copy()
    
    def get_event_interceptors(self) -> list[EventInterceptor]:
        """Get all event interceptors."""
        return self._event_interceptors.copy()

