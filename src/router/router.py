"""Event and message router with rule-based matching."""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Pattern
from enum import Enum

from ..core.logger import get_logger
from ..protocol.base import MessageEnvelope

logger = get_logger(__name__)


class Priority(int, Enum):
    """Handler priority levels."""
    HIGHEST = 0
    HIGH = 10
    NORMAL = 50
    LOW = 100
    LOWEST = 200


class Rule(ABC):
    """Base rule for message matching."""

    @abstractmethod
    async def check(self, envelope: MessageEnvelope, context: Dict[str, Any]) -> bool:
        """Check if the rule matches."""
        pass

    def __and__(self, other: "Rule") -> "AndRule":
        """Combine rules with AND."""
        return AndRule(self, other)

    def __or__(self, other: "Rule") -> "OrRule":
        """Combine rules with OR."""
        return OrRule(self, other)


class AndRule(Rule):
    """Combine multiple rules with AND logic."""

    def __init__(self, *rules: Rule):
        self.rules = rules

    async def check(self, envelope: MessageEnvelope, context: Dict[str, Any]) -> bool:
        """Check if all rules match."""
        for rule in self.rules:
            if not await rule.check(envelope, context):
                return False
        return True


class OrRule(Rule):
    """Combine multiple rules with OR logic."""

    def __init__(self, *rules: Rule):
        self.rules = rules

    async def check(self, envelope: MessageEnvelope, context: Dict[str, Any]) -> bool:
        """Check if any rule matches."""
        for rule in self.rules:
            if await rule.check(envelope, context):
                return True
        return False


class CommandRule(Rule):
    """Match command messages."""

    def __init__(self, command: str, prefixes: Optional[List[str]] = None):
        self.command = command
        self.prefixes = prefixes or ["/", "!", ".", "#"]

    async def check(self, envelope: MessageEnvelope, context: Dict[str, Any]) -> bool:
        """Check if message is a command."""
        msg = envelope.raw_message.strip()
        
        for prefix in self.prefixes:
            if msg.startswith(prefix + self.command):
                # Extract arguments
                args_str = msg[len(prefix + self.command):].strip()
                context["command"] = self.command
                context["prefix"] = prefix
                context["args"] = args_str.split() if args_str else []
                context["args_str"] = args_str
                return True
        
        return False


class KeywordRule(Rule):
    """Match keyword in message."""

    def __init__(self, keyword: str, case_sensitive: bool = False):
        self.keyword = keyword
        self.case_sensitive = case_sensitive

    async def check(self, envelope: MessageEnvelope, context: Dict[str, Any]) -> bool:
        """Check if message contains keyword."""
        msg = envelope.raw_message
        keyword = self.keyword
        
        if not self.case_sensitive:
            msg = msg.lower()
            keyword = keyword.lower()
        
        return keyword in msg


class RegexRule(Rule):
    """Match message with regex pattern."""

    def __init__(self, pattern: str, flags: int = 0):
        self.pattern: Pattern = re.compile(pattern, flags)

    async def check(self, envelope: MessageEnvelope, context: Dict[str, Any]) -> bool:
        """Check if message matches regex."""
        match = self.pattern.search(envelope.raw_message)
        if match:
            context["regex_match"] = match
            context["regex_groups"] = match.groups()
            return True
        return False


class MessageTypeRule(Rule):
    """Match message type."""

    def __init__(self, message_type: str):
        self.message_type = message_type

    async def check(self, envelope: MessageEnvelope, context: Dict[str, Any]) -> bool:
        """Check message type."""
        return envelope.message_type == self.message_type


class UserRule(Rule):
    """Match specific user(s)."""

    def __init__(self, user_ids: List[str]):
        self.user_ids = set(user_ids)

    async def check(self, envelope: MessageEnvelope, context: Dict[str, Any]) -> bool:
        """Check if sender is in user list."""
        return envelope.user_id in self.user_ids


class GroupRule(Rule):
    """Match specific group(s)."""

    def __init__(self, group_ids: List[str]):
        self.group_ids = set(group_ids)

    async def check(self, envelope: MessageEnvelope, context: Dict[str, Any]) -> bool:
        """Check if group is in group list."""
        return envelope.group_id in self.group_ids if envelope.group_id else False


@dataclass
class Handler:
    """Message handler with rule and callback."""
    
    name: str
    rule: Rule
    callback: Callable
    priority: Priority = Priority.NORMAL
    block: bool = False  # If True, stop processing after this handler


class Router:
    """Event and message router."""

    def __init__(self):
        self._handlers: List[Handler] = []

    def add_handler(
        self,
        name: str,
        rule: Rule,
        callback: Callable,
        priority: Priority = Priority.NORMAL,
        block: bool = False
    ) -> None:
        """Add a message handler."""
        handler = Handler(
            name=name,
            rule=rule,
            callback=callback,
            priority=priority,
            block=block
        )
        self._handlers.append(handler)
        self._handlers.sort(key=lambda h: h.priority.value)
        
        logger.debug(
            "Handler registered",
            name=name,
            priority=priority.name,
            block=block
        )

    def command(
        self,
        command: str,
        prefixes: Optional[List[str]] = None,
        priority: Priority = Priority.NORMAL,
        block: bool = False
    ):
        """Decorator for command handlers."""
        def decorator(func: Callable):
            rule = CommandRule(command, prefixes)
            self.add_handler(
                name=func.__name__,
                rule=rule,
                callback=func,
                priority=priority,
                block=block
            )
            return func
        return decorator

    def keyword(
        self,
        keyword: str,
        case_sensitive: bool = False,
        priority: Priority = Priority.NORMAL,
        block: bool = False
    ):
        """Decorator for keyword handlers."""
        def decorator(func: Callable):
            rule = KeywordRule(keyword, case_sensitive)
            self.add_handler(
                name=func.__name__,
                rule=rule,
                callback=func,
                priority=priority,
                block=block
            )
            return func
        return decorator

    def regex(
        self,
        pattern: str,
        flags: int = 0,
        priority: Priority = Priority.NORMAL,
        block: bool = False
    ):
        """Decorator for regex handlers."""
        def decorator(func: Callable):
            rule = RegexRule(pattern, flags)
            self.add_handler(
                name=func.__name__,
                rule=rule,
                callback=func,
                priority=priority,
                block=block
            )
            return func
        return decorator

    async def route(self, envelope: MessageEnvelope) -> List[Any]:
        """Route message to matching handlers."""
        results = []
        context: Dict[str, Any] = {}

        logger.debug(
            "Routing message",
            message_id=envelope.message_id,
            message_type=envelope.message_type,
            user_id=envelope.user_id
        )

        for handler in self._handlers:
            try:
                # Check if rule matches
                if await handler.rule.check(envelope, context):
                    logger.info(
                        "Handler matched",
                        handler_name=handler.name,
                        message_id=envelope.message_id
                    )

                    # Call handler
                    import asyncio
                    if asyncio.iscoroutinefunction(handler.callback):
                        result = await handler.callback(envelope, context)
                    else:
                        result = handler.callback(envelope, context)
                    
                    results.append({
                        "handler": handler.name,
                        "result": result
                    })

                    # Stop if blocking
                    if handler.block:
                        logger.debug("Handler blocked further processing")
                        break

            except Exception as e:
                logger.error(
                    "Error in handler",
                    handler_name=handler.name,
                    error=str(e),
                    exc_info=True
                )

        return results

    def get_handlers(self) -> List[Handler]:
        """Get all registered handlers."""
        return self._handlers.copy()

    def remove_handler(self, name: str) -> bool:
        """Remove a handler by name."""
        for i, handler in enumerate(self._handlers):
            if handler.name == name:
                self._handlers.pop(i)
                logger.debug("Handler removed", name=name)
                return True
        return False

    def clear_handlers(self) -> None:
        """Clear all handlers."""
        self._handlers.clear()
        logger.debug("All handlers cleared")

