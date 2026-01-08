"""Base protocol adapter interface."""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime
from enum import Enum


class MessageType(str, Enum):
    """Message types."""
    TEXT = "text"
    IMAGE = "image"
    VOICE = "voice"
    VIDEO = "video"
    FILE = "file"
    AT = "at"
    REPLY = "reply"
    FACE = "face"
    JSON = "json"
    XML = "xml"


@dataclass
class MessageSegment:
    """Message segment for structured messages."""
    
    type: str
    data: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "type": self.type,
            "data": self.data
        }

    @classmethod
    def text(cls, text: str) -> "MessageSegment":
        """Create a text segment."""
        return cls(type="text", data={"text": text})

    @classmethod
    def image(cls, file: str, **kwargs) -> "MessageSegment":
        """Create an image segment."""
        return cls(type="image", data={"file": file, **kwargs})

    @classmethod
    def at(cls, qq: str) -> "MessageSegment":
        """Create an @mention segment."""
        return cls(type="at", data={"qq": qq})

    @classmethod
    def reply(cls, message_id: str) -> "MessageSegment":
        """Create a reply segment."""
        return cls(type="reply", data={"id": message_id})


@dataclass
class MessageEnvelope:
    """
    Unified message envelope for cross-protocol communication.
    """
    
    message_id: str
    message_type: str  # private, group, guild
    user_id: str
    timestamp: datetime
    raw_message: str
    message: List[MessageSegment] = field(default_factory=list)
    group_id: Optional[str] = None
    guild_id: Optional[str] = None
    channel_id: Optional[str] = None
    sender: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "message_id": self.message_id,
            "message_type": self.message_type,
            "user_id": self.user_id,
            "timestamp": self.timestamp.isoformat(),
            "raw_message": self.raw_message,
            "message": [seg.to_dict() for seg in self.message],
            "group_id": self.group_id,
            "guild_id": self.guild_id,
            "channel_id": self.channel_id,
            "sender": self.sender,
            "metadata": self.metadata,
        }


class ProtocolAdapter(ABC):
    """Base protocol adapter interface."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._event_callbacks: List[Callable] = []
        self._running = False

    @abstractmethod
    async def start(self) -> None:
        """Start the protocol adapter."""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop the protocol adapter."""
        pass

    @abstractmethod
    async def send_message(
        self,
        target: str,
        message: Any,
        message_type: str = "private"
    ) -> Dict[str, Any]:
        """
        Send a message.
        
        Args:
            target: Target ID (user_id for private, group_id for group)
            message: Message content (string or list of segments)
            message_type: Type of message (private/group)
            
        Returns:
            Response with message_id and other info
        """
        pass

    @abstractmethod
    async def delete_message(self, message_id: str) -> bool:
        """Delete a message."""
        pass

    @abstractmethod
    async def get_message(self, message_id: str) -> Optional[MessageEnvelope]:
        """Get message by ID."""
        pass

    def on_event(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Register an event callback."""
        self._event_callbacks.append(callback)

    async def _emit_event(self, event: Dict[str, Any]) -> None:
        """Emit an event to all callbacks."""
        for callback in self._event_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception as e:
                print(f"Error in event callback: {e}")

    def is_running(self) -> bool:
        """Check if adapter is running."""
        return self._running

    @abstractmethod
    def get_protocol_name(self) -> str:
        """Get the protocol name."""
        pass

    @abstractmethod
    def get_protocol_version(self) -> str:
        """Get the protocol version."""
        pass

