"""OneBot event types."""

from typing import Dict, Any, Optional
from dataclasses import dataclass
from .message import Message


@dataclass
class Sender:
    """Message sender info."""
    
    user_id: str
    nickname: str
    card: Optional[str] = None
    role: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Sender":
        return cls(
            user_id=str(data.get("user_id", "")),
            nickname=data.get("nickname", ""),
            card=data.get("card"),
            role=data.get("role")
        )


@dataclass
class Event:
    """Base event."""
    
    time: int
    self_id: str
    post_type: str
    raw_event: Dict[str, Any]
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        return cls(
            time=data.get("time", 0),
            self_id=str(data.get("self_id", "")),
            post_type=data.get("post_type", ""),
            raw_event=data
        )


@dataclass
class MessageEvent(Event):
    """Message event base."""
    
    message_type: str
    message_id: str
    user_id: str
    message: Message
    raw_message: str
    sender: Sender
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MessageEvent":
        return cls(
            time=data.get("time", 0),
            self_id=str(data.get("self_id", "")),
            post_type=data.get("post_type", "message"),
            raw_event=data,
            message_type=data.get("message_type", ""),
            message_id=str(data.get("message_id", "")),
            user_id=str(data.get("user_id", "")),
            message=Message.from_array(data.get("message", [])),
            raw_message=data.get("raw_message", ""),
            sender=Sender.from_dict(data.get("sender", {}))
        )


@dataclass
class GroupMessageEvent(MessageEvent):
    """Group message event."""
    
    group_id: str
    is_mentioned: bool = False
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GroupMessageEvent":
        event = super().from_dict(data)
        return cls(
            **event.__dict__,
            group_id=str(data.get("group_id", "")),
            is_mentioned="at" in str(data.get("message", []))
        )


@dataclass
class PrivateMessageEvent(MessageEvent):
    """Private message event."""
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PrivateMessageEvent":
        event = super().from_dict(data)
        return cls(**event.__dict__)


def parse_event(data: Dict[str, Any]) -> Event:
    """Parse raw event data to Event object."""
    post_type = data.get("post_type", "")
    
    if post_type == "message":
        message_type = data.get("message_type", "")
        if message_type == "group":
            return GroupMessageEvent.from_dict(data)
        elif message_type == "private":
            return PrivateMessageEvent.from_dict(data)
        return MessageEvent.from_dict(data)
    
    return Event.from_dict(data)

