"""Protocol adapters for OneBot and other protocols."""

from .base import ProtocolAdapter, MessageEnvelope, MessageSegment
from .onebot import OneBotAdapter

__all__ = [
    "ProtocolAdapter",
    "MessageEnvelope",
    "MessageSegment",
    "OneBotAdapter",
]

