"""Sticker Integration - provides easy-to-use interface for AI to use stickers.

This module provides high-level functions that can be easily integrated into
AI reply generation, making it simple to add sticker support to responses.
"""

from typing import List, Optional, Dict, Any

from ..core.logger import get_logger
from .sticker_manager import get_sticker_manager
from .llm_client import LLMClient

logger = get_logger(__name__)


async def add_stickers_to_reply(
    chat_id: str,
    reply_text: str,
    chat_context: Optional[str] = None,
    llm_client: Optional[LLMClient] = None,
    sticker_count: int = 1,
    position: str = 'end'
) -> str:
    """Add appropriate stickers to an AI reply.
    
    This is the main function for integrating stickers into AI responses.
    
    Args:
        chat_id: Chat ID
        reply_text: The AI's reply text (without stickers)
        chat_context: Current chat context
        llm_client: Optional LLM client for smart selection
        sticker_count: Number of stickers to add (0-3)
        position: Where to add stickers ('start', 'end', or 'both')
        
    Returns:
        Reply text with stickers added
        
    Example:
        >>> reply = "好的，我明白了"
        >>> enhanced = await add_stickers_to_reply(
        ...     chat_id="group:12345",
        ...     reply_text=reply,
        ...     sticker_count=1
        ... )
        >>> print(enhanced)
        "好的，我明白了 [CQ:face,id=178]"
    """
    try:
        if sticker_count <= 0:
            return reply_text
        
        manager = get_sticker_manager()
        
        # Get appropriate stickers
        stickers = await manager.get_stickers_for_reply(
            chat_id=chat_id,
            reply_content=reply_text,
            chat_context=chat_context,
            llm_client=llm_client,
            max_count=sticker_count
        )
        
        if not stickers:
            logger.debug(f"No stickers selected for reply in chat {chat_id}")
            return reply_text
        
        # Add stickers to reply based on position
        if position == 'start':
            # Add all stickers at the start
            sticker_str = ' '.join(stickers)
            return f"{sticker_str} {reply_text}"
        
        elif position == 'end':
            # Add all stickers at the end
            sticker_str = ' '.join(stickers)
            return f"{reply_text} {sticker_str}"
        
        elif position == 'both':
            # Split stickers between start and end
            mid = len(stickers) // 2
            start_stickers = stickers[:mid]
            end_stickers = stickers[mid:]
            
            result = reply_text
            if start_stickers:
                result = f"{' '.join(start_stickers)} {result}"
            if end_stickers:
                result = f"{result} {' '.join(end_stickers)}"
            
            return result
        
        else:
            # Default to end
            sticker_str = ' '.join(stickers)
            return f"{reply_text} {sticker_str}"
        
    except Exception as e:
        logger.error(f"Failed to add stickers to reply: {e}", exc_info=True)
        return reply_text


async def get_emotion_sticker(
    chat_id: str,
    emotion: str
) -> Optional[str]:
    """Get a single sticker for a specific emotion.
    
    Useful for quick emotional responses or reactions.
    
    Args:
        chat_id: Chat ID
        emotion: Emotion keyword (e.g., "开心", "无语", "赞同")
        
    Returns:
        Formatted sticker string or None
        
    Example:
        >>> sticker = await get_emotion_sticker("group:12345", "开心")
        >>> print(sticker)
        "[CQ:face,id=178]"
    """
    try:
        manager = get_sticker_manager()
        
        stickers = await manager.get_stickers_by_emotion(
            chat_id=chat_id,
            emotion=emotion,
            max_count=1
        )
        
        if stickers:
            return stickers[0]
        
        return None
        
    except Exception as e:
        logger.error(f"Failed to get emotion sticker: {e}", exc_info=True)
        return None


async def learn_stickers_from_conversation(
    chat_id: str,
    messages: List[Any],
    llm_client: Optional[LLMClient] = None
) -> int:
    """Learn sticker usage patterns from a conversation.
    
    Call this periodically or after significant conversations to improve
    the system's understanding of sticker usage.
    
    Args:
        chat_id: Chat ID
        messages: List of message objects
        llm_client: Optional LLM client for intelligent learning
        
    Returns:
        Number of stickers learned
        
    Example:
        >>> messages = [msg1, msg2, msg3, ...]
        >>> count = await learn_stickers_from_conversation(
        ...     chat_id="group:12345",
        ...     messages=messages
        ... )
        >>> print(f"Learned {count} sticker usages")
    """
    try:
        manager = get_sticker_manager()
        
        count = await manager.process_messages_for_learning(
            chat_id=chat_id,
            messages=messages,
            llm_client=llm_client
        )
        
        return count
        
    except Exception as e:
        logger.error(f"Failed to learn stickers: {e}", exc_info=True)
        return 0


async def get_sticker_stats(chat_id: str) -> Dict[str, Any]:
    """Get statistics about learned stickers for a chat.
    
    Args:
        chat_id: Chat ID
        
    Returns:
        Dictionary with sticker statistics
        
    Example:
        >>> stats = await get_sticker_stats("group:12345")
        >>> print(f"Total stickers: {stats['total_count']}")
        >>> print(f"By type: {stats['by_type']}")
    """
    try:
        manager = get_sticker_manager()
        return await manager.get_sticker_statistics(chat_id)
        
    except Exception as e:
        logger.error(f"Failed to get sticker stats: {e}", exc_info=True)
        return {}


async def should_use_sticker(
    reply_text: str,
    chat_context: Optional[str] = None,
    probability: float = 0.3
) -> bool:
    """Decide whether to add a sticker to a reply.
    
    Uses heuristics to determine if adding a sticker would be appropriate.
    
    Args:
        reply_text: The reply text
        chat_context: Chat context
        probability: Base probability of using sticker (0.0-1.0)
        
    Returns:
        True if should use sticker
        
    Example:
        >>> if await should_use_sticker("好的！", probability=0.5):
        ...     reply = await add_stickers_to_reply(...)
    """
    import random
    
    try:
        # Base decision on probability
        if random.random() > probability:
            return False
        
        # Increase probability for short, emotional messages
        if len(reply_text) < 20:
            return random.random() < 0.6
        
        # Increase probability if reply contains emotional words
        emotional_words = [
            '哈哈', '笑', '开心', '高兴',
            '无语', '服了', '醉了',
            '赞', '厉害', '牛', '强',
            '难过', '伤心', '哭',
            '卧槽', '天啊', '惊'
        ]
        
        if any(word in reply_text for word in emotional_words):
            return random.random() < 0.7
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to decide sticker usage: {e}")
        return False


# Convenience function for quick integration
async def enhance_reply_with_sticker(
    chat_id: str,
    reply_text: str,
    chat_context: Optional[str] = None,
    llm_client: Optional[LLMClient] = None,
    auto_decide: bool = True
) -> str:
    """Automatically enhance a reply with stickers if appropriate.
    
    This is the simplest way to add sticker support to AI replies.
    It automatically decides whether to add stickers and adds them appropriately.
    
    Args:
        chat_id: Chat ID
        reply_text: The AI's reply text
        chat_context: Chat context
        llm_client: Optional LLM client
        auto_decide: If True, automatically decide whether to add stickers
        
    Returns:
        Enhanced reply text (with or without stickers)
        
    Example:
        >>> # Simple usage - just wrap your reply generation
        >>> reply = generate_ai_reply(...)
        >>> enhanced = await enhance_reply_with_sticker(
        ...     chat_id="group:12345",
        ...     reply_text=reply
        ... )
        >>> send_message(enhanced)
    """
    try:
        # Decide whether to use sticker
        if auto_decide:
            use_sticker = await should_use_sticker(
                reply_text=reply_text,
                chat_context=chat_context
            )
            
            if not use_sticker:
                return reply_text
        
        # Decide sticker count based on reply length
        if len(reply_text) < 10:
            sticker_count = 1
        elif len(reply_text) < 50:
            sticker_count = 1
        else:
            sticker_count = 1  # Keep it simple, rarely use more than 1
        
        # Add stickers
        enhanced = await add_stickers_to_reply(
            chat_id=chat_id,
            reply_text=reply_text,
            chat_context=chat_context,
            llm_client=llm_client,
            sticker_count=sticker_count,
            position='end'
        )
        
        return enhanced
        
    except Exception as e:
        logger.error(f"Failed to enhance reply with sticker: {e}", exc_info=True)
        return reply_text

