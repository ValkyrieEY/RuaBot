"""Finish Maintenance Tool - Signal that maintenance is complete."""

from typing import Optional
from src.core.logger import get_logger

logger = get_logger(__name__)


def make_finish_maintenance(chat_id: str):
    """Factory function to create finish_maintenance tool bound to a specific chat_id."""
    
    async def finish_maintenance(reason: Optional[str] = None) -> str:
        """Signal that the maintenance work is complete.
        
        Args:
            reason: Optional reason for finishing (e.g., 'All records are organized')
            
        Returns:
            Confirmation message
        """
        reason_text = reason or "维护工作已完成"
        logger.info(f"[Dream] {chat_id} 维护结束: {reason_text}")
        return f"维护结束: {reason_text}"
    
    return finish_maintenance

