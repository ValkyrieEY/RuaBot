"""Frequency control manager for AI message processing."""

from typing import Dict, Optional
from ..core.logger import get_logger

logger = get_logger(__name__)


class FrequencyControl:
    """Frequency control for a single chat stream."""
    
    def __init__(self, chat_id: str):
        self.chat_id = chat_id
        # 发言频率调整值，范围 0.1 - 5.0
        self.talk_frequency_adjust: float = 1.0
    
    def get_talk_frequency_adjust(self) -> float:
        """Get talk frequency adjustment value."""
        return self.talk_frequency_adjust
    
    def set_talk_frequency_adjust(self, value: float) -> None:
        """Set talk frequency adjustment value."""
        # 限制范围在 0.1 - 5.0
        self.talk_frequency_adjust = max(0.1, min(5.0, value))


class FrequencyControlManager:
    """Frequency control manager for multiple chat streams."""
    
    def __init__(self):
        self.frequency_control_dict: Dict[str, FrequencyControl] = {}
    
    def get_or_create_frequency_control(self, chat_id: str) -> FrequencyControl:
        """Get or create frequency control for a chat stream."""
        if chat_id not in self.frequency_control_dict:
            self.frequency_control_dict[chat_id] = FrequencyControl(chat_id)
        return self.frequency_control_dict[chat_id]
    
    def remove_frequency_control(self, chat_id: str) -> bool:
        """Remove frequency control for a chat stream."""
        if chat_id in self.frequency_control_dict:
            del self.frequency_control_dict[chat_id]
            return True
        return False
    
    def get_all_chat_ids(self) -> list:
        """Get all chat IDs with frequency control."""
        return list(self.frequency_control_dict.keys())


# Global frequency control manager instance
frequency_control_manager = FrequencyControlManager()

