"""Message builder for OneBot protocol."""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class MessageSegment:
    """Message segment base."""
    
    type: str
    data: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {"type": self.type, "data": self.data}


class Message:
    """Message builder with chain API."""
    
    def __init__(self):
        self.segments: List[MessageSegment] = []
    
    def text(self, content: str) -> "Message":
        """Add text segment."""
        self.segments.append(MessageSegment("text", {"text": content}))
        return self
    
    def at(self, user_id: str) -> "Message":
        """Add @ mention segment."""
        self.segments.append(MessageSegment("at", {"qq": user_id}))
        return self
    
    def image(self, file: str, **kwargs) -> "Message":
        """Add image segment."""
        data = {"file": file}
        data.update(kwargs)
        self.segments.append(MessageSegment("image", data))
        return self
    
    def video(self, file: str, **kwargs) -> "Message":
        """Add video segment."""
        data = {"file": file}
        data.update(kwargs)
        self.segments.append(MessageSegment("video", data))
        return self
    
    def voice(self, file: str, **kwargs) -> "Message":
        """Add voice segment."""
        data = {"file": file}
        data.update(kwargs)
        self.segments.append(MessageSegment("voice", data))
        return self
    
    def reply(self, message_id: str) -> "Message":
        """Add reply segment."""
        self.segments.append(MessageSegment("reply", {"id": message_id}))
        return self
    
    def to_array(self) -> List[Dict[str, Any]]:
        """Convert to OneBot array format."""
        return [seg.to_dict() for seg in self.segments]
    
    def to_string(self) -> str:
        """Convert to string representation."""
        result = []
        for seg in self.segments:
            if seg.type == "text":
                result.append(seg.data.get("text", ""))
            elif seg.type == "at":
                result.append(f"[@{seg.data.get('qq')}]")
            elif seg.type == "image":
                result.append("[图片]")
            elif seg.type == "video":
                result.append("[视频]")
            elif seg.type == "voice":
                result.append("[语音]")
        return "".join(result)
    
    def __str__(self) -> str:
        return self.to_string()
    
    @classmethod
    def from_array(cls, data: List[Dict[str, Any]]) -> "Message":
        """Create message from OneBot array format."""
        message = cls()
        for item in data:
            message.segments.append(MessageSegment(
                type=item.get("type", "text"),
                data=item.get("data", {})
            ))
        return message

