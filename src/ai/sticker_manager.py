"""Sticker Manager - orchestrates sticker learning and selection.

This module provides a high-level interface for sticker learning and usage,
coordinating between the learner, selector, and database.
"""

import asyncio
from typing import List, Optional, Dict, Any

from ..core.logger import get_logger
from .ai_database import get_ai_database
from .sticker_learner import get_sticker_learner
from .sticker_selector import get_sticker_selector
from .llm_client import LLMClient

logger = get_logger(__name__)


class StickerManager:
    """Manages sticker learning and selection."""
    
    def __init__(self):
        """Initialize sticker manager."""
        self.ai_db = get_ai_database()
        self.learner = get_sticker_learner()
        self.selector = get_sticker_selector()
        self._learning_tasks = {}
    
    async def process_messages_for_learning(
        self,
        chat_id: str,
        messages: List[Any],
        llm_client: Optional[LLMClient] = None
    ) -> int:
        """Process messages to learn sticker usage patterns.
        
        Args:
            chat_id: Chat ID
            messages: List of message objects
            llm_client: Optional LLM client for intelligent learning
            
        Returns:
            Number of stickers learned
        """
        try:
            # Learn from messages
            learned = await self.learner.learn_from_messages(
                chat_id=chat_id,
                messages=messages,
                llm_client=llm_client
            )
            
            logger.info(f"Learned {len(learned)} sticker usages from {len(messages)} messages in chat {chat_id}")
            return len(learned)
            
        except Exception as e:
            logger.error(f"Failed to process messages for learning: {e}", exc_info=True)
            return 0
    
    async def get_stickers_for_reply(
        self,
        chat_id: str,
        reply_content: str,
        chat_context: Optional[str] = None,
        reply_reason: Optional[str] = None,
        llm_client: Optional[LLMClient] = None,
        max_count: int = 2
    ) -> List[str]:
        """Get appropriate stickers for an AI reply.
        
        Args:
            chat_id: Chat ID
            reply_content: The AI's reply text
            chat_context: Current chat context
            reply_reason: Reasoning for the reply
            llm_client: Optional LLM client for smart selection
            max_count: Maximum number of stickers
            
        Returns:
            List of formatted sticker strings (CQ codes or emoji)
        """
        try:
            # Detect emotion from reply content
            emotion = None
            if llm_client:
                emotion = await self.selector.detect_emotion_from_text(
                    text=reply_content,
                    llm_client=llm_client
                )
            
            # Select stickers
            selected = await self.selector.select_stickers(
                chat_id=chat_id,
                situation=None,
                emotion=emotion,
                chat_context=chat_context,
                reply_content=reply_content,
                llm_client=llm_client,
                max_count=max_count
            )
            
            if not selected:
                logger.debug(f"No stickers selected for chat {chat_id}")
                return []
            
            # Format stickers for message
            formatted = []
            for sticker in selected:
                formatted_str = self.selector.format_sticker_for_message(sticker)
                if formatted_str:
                    formatted.append(formatted_str)
            
            logger.debug(f"Selected {len(formatted)} stickers for reply in chat {chat_id}")
            return formatted
            
        except Exception as e:
            logger.error(f"Failed to get stickers for reply: {e}", exc_info=True)
            return []
    
    async def get_stickers_by_emotion(
        self,
        chat_id: str,
        emotion: str,
        max_count: int = 3
    ) -> List[str]:
        """Get stickers by specific emotion.
        
        Args:
            chat_id: Chat ID
            emotion: Target emotion (e.g., "开心", "无语")
            max_count: Maximum number of stickers
            
        Returns:
            List of formatted sticker strings
        """
        try:
            selected = await self.selector.select_stickers(
                chat_id=chat_id,
                emotion=emotion,
                max_count=max_count
            )
            
            formatted = []
            for sticker in selected:
                formatted_str = self.selector.format_sticker_for_message(sticker)
                if formatted_str:
                    formatted.append(formatted_str)
            
            return formatted
            
        except Exception as e:
            logger.error(f"Failed to get stickers by emotion: {e}", exc_info=True)
            return []
    
    async def get_sticker_statistics(
        self,
        chat_id: str
    ) -> Dict[str, Any]:
        """Get statistics about learned stickers.
        
        Args:
            chat_id: Chat ID
            
        Returns:
            Dictionary with statistics
        """
        try:
            # Get all stickers for this chat
            stickers = await self.ai_db.get_stickers(
                chat_id=chat_id,
                rejected=False
            )
            
            if not stickers:
                return {
                    'total_count': 0,
                    'by_type': {},
                    'by_emotion': {},
                    'top_used': []
                }
            
            # Count by type
            by_type = {}
            by_emotion = {}
            
            for sticker in stickers:
                # Count by type
                sticker_type = sticker.sticker_type
                by_type[sticker_type] = by_type.get(sticker_type, 0) + 1
                
                # Count by emotion
                if sticker.emotion:
                    emotion = sticker.emotion
                    by_emotion[emotion] = by_emotion.get(emotion, 0) + 1
            
            # Get top used stickers
            sorted_stickers = sorted(stickers, key=lambda s: s.count or 0, reverse=True)
            top_used = [
                {
                    'type': s.sticker_type,
                    'situation': s.situation,
                    'emotion': s.emotion,
                    'count': s.count
                }
                for s in sorted_stickers[:10]
            ]
            
            return {
                'total_count': len(stickers),
                'by_type': by_type,
                'by_emotion': by_emotion,
                'top_used': top_used
            }
            
        except Exception as e:
            logger.error(f"Failed to get sticker statistics: {e}", exc_info=True)
            return {}
    
    async def start_background_learning(
        self,
        chat_id: str,
        interval_seconds: int = 300
    ):
        """Start background learning task for a chat.
        
        Args:
            chat_id: Chat ID
            interval_seconds: Learning interval in seconds
        """
        if chat_id in self._learning_tasks:
            logger.debug(f"Background learning already running for chat {chat_id}")
            return
        
        async def learning_loop():
            """Background learning loop."""
            while True:
                try:
                    await asyncio.sleep(interval_seconds)
                    
                    # Get recent messages (would need to integrate with message storage)
                    # For now, this is a placeholder
                    logger.debug(f"Background learning check for chat {chat_id}")
                    
                except asyncio.CancelledError:
                    logger.info(f"Background learning cancelled for chat {chat_id}")
                    break
                except Exception as e:
                    logger.error(f"Error in background learning for chat {chat_id}: {e}")
                    await asyncio.sleep(60)  # Wait before retry
        
        task = asyncio.create_task(learning_loop())
        self._learning_tasks[chat_id] = task
        logger.info(f"Started background learning for chat {chat_id}")
    
    async def stop_background_learning(self, chat_id: str):
        """Stop background learning task for a chat.
        
        Args:
            chat_id: Chat ID
        """
        if chat_id not in self._learning_tasks:
            return
        
        task = self._learning_tasks[chat_id]
        task.cancel()
        
        try:
            await task
        except asyncio.CancelledError:
            pass
        
        del self._learning_tasks[chat_id]
        logger.info(f"Stopped background learning for chat {chat_id}")
    
    async def cleanup(self):
        """Cleanup resources."""
        # Stop all background tasks
        for chat_id in list(self._learning_tasks.keys()):
            await self.stop_background_learning(chat_id)
        
        logger.info("Sticker manager cleanup complete")


# Global sticker manager instance
_sticker_manager_instance: Optional[StickerManager] = None


def get_sticker_manager() -> StickerManager:
    """Get or create global sticker manager instance."""
    global _sticker_manager_instance
    if _sticker_manager_instance is None:
        _sticker_manager_instance = StickerManager()
    return _sticker_manager_instance

