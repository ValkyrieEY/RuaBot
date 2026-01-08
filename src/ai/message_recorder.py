"""Message Recorder - records and manages chat messages.

Inspired by RuaBot's message recording system, this module:
1. Records all messages to database
2. Provides message history retrieval
3. Supports filtering and pagination
4. Manages message lifecycle
"""

import time
from typing import List, Dict, Optional, Any

from ..core.logger import get_logger
from .ai_database import get_ai_database

logger = get_logger(__name__)


class MessageRecorder:
    """Records and manages chat messages."""
    
    def __init__(self):
        """Initialize message recorder."""
        self.ai_db = get_ai_database()
    
    async def record_message(
        self,
        message_id: Optional[str],
        chat_id: str,
        user_id: str,
        plain_text: Optional[str],
        display_message: Optional[str] = None,
        user_nickname: Optional[str] = None,
        user_cardname: Optional[str] = None,
        group_id: Optional[str] = None,
        group_name: Optional[str] = None,
        is_bot_message: bool = False,
        timestamp: Optional[float] = None
    ) -> bool:
        """Record a message to database.
        
        Args:
            message_id: OneBot message ID
            chat_id: Chat ID (format: "group:群号" or "user:QQ号")
            user_id: User ID (QQ number)
            plain_text: Plain text message
            display_message: Display message (with CQ codes)
            user_nickname: User nickname
            user_cardname: Group card name
            group_id: Group ID (if group message)
            group_name: Group name (if group message)
            is_bot_message: Whether this is bot's own message
            timestamp: Message timestamp (default: current time)
            
        Returns:
            True if recorded successfully
        """
        try:
            if not plain_text or not plain_text.strip():
                logger.debug("Skipping empty message")
                return False
            
            msg_time = timestamp if timestamp is not None else time.time()
            
            await self.ai_db.save_message_record(
                message_id=message_id,
                chat_id=chat_id,
                user_id=user_id,
                plain_text=plain_text,
                display_message=display_message,
                user_nickname=user_nickname,
                user_cardname=user_cardname,
                group_id=group_id,
                group_name=group_name,
                is_bot_message=is_bot_message,
                time=msg_time
            )
            
            logger.debug(f"Recorded message {message_id} in {chat_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to record message: {e}", exc_info=True)
            return False
    
    async def get_recent_messages(
        self,
        chat_id: str,
        limit: int = 50,
        exclude_bot: bool = True
    ) -> List[Dict[str, Any]]:
        """Get recent messages for a chat.
        
        Args:
            chat_id: Chat ID
            limit: Maximum number of messages to return
            exclude_bot: Whether to exclude bot's own messages
            
        Returns:
            List of message dicts
        """
        try:
            messages = await self.ai_db.get_recent_messages(
                chat_id=chat_id,
                limit=limit,
                exclude_bot=exclude_bot
            )
            
            # Convert to dict
            result = []
            for msg in messages:
                result.append({
                    'message_id': msg.message_id,
                    'user_id': msg.user_id,
                    'user_name': msg.user_cardname or msg.user_nickname or msg.user_id,
                    'user_nickname': msg.user_nickname,
                    'content': msg.plain_text,
                    'display_message': msg.display_message,
                    'time': msg.time,
                    'is_bot_message': msg.is_bot_message
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get recent messages: {e}", exc_info=True)
            return []
    
    async def get_messages_for_learning(
        self,
        chat_id: str,
        limit: int = 30,
        exclude_bot: bool = True
    ) -> List[Dict[str, Any]]:
        """Get messages for learning (expression/jargon).
        
        Args:
            chat_id: Chat ID
            limit: Maximum number of messages
            exclude_bot: Whether to exclude bot messages
            
        Returns:
            List of message dicts suitable for learning
        """
        try:
            messages = await self.get_recent_messages(
                chat_id=chat_id,
                limit=limit,
                exclude_bot=exclude_bot
            )
            
            # Filter out very short messages
            filtered = [
                msg for msg in messages
                if len(msg.get('content', '')) >= 2
            ]
            
            return filtered
            
        except Exception as e:
            logger.error(f"Failed to get messages for learning: {e}", exc_info=True)
            return []


# Global message recorder instance
_message_recorder_instance: Optional[MessageRecorder] = None


def get_message_recorder() -> MessageRecorder:
    """Get or create global message recorder instance."""
    global _message_recorder_instance
    if _message_recorder_instance is None:
        _message_recorder_instance = MessageRecorder()
    return _message_recorder_instance

