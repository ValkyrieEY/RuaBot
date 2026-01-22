"""Learning Scheduler - Manages periodic learning triggers.

Similar to MaiBot's MessageRecorder, this module:
1. Tracks message counts per chat
2. Triggers learning when thresholds are met (30 messages, 60 seconds)
3. Prevents duplicate/concurrent learning
"""

import time
import asyncio
from typing import Dict, Optional, List, Any

from ..core.logger import get_logger
from .message_recorder import get_message_recorder
from .expression_learner import get_expression_learner
from .jargon_miner import get_jargon_miner
from .sticker_manager import get_sticker_manager
from .learning_config import get_learning_config
from .llm_client import LLMClient

logger = get_logger(__name__)


class LearningScheduler:
    """Schedules and triggers learning tasks based on message volume and time."""
    
    def __init__(self):
        """Initialize learning scheduler."""
        self.message_recorder = get_message_recorder()
        self.expression_learner = get_expression_learner()
        self.jargon_miner = get_jargon_miner()
        self.sticker_manager = get_sticker_manager()
        self.learning_config = get_learning_config()
        
        # Track last learning time per chat
        self._last_learning_time: Dict[str, float] = {}
        
        # Track message count since last learning per chat
        self._message_count: Dict[str, int] = {}
        
        # Lock to prevent concurrent learning for same chat
        self._learning_locks: Dict[str, asyncio.Lock] = {}
        
        # Thresholds (same as MaiBot)
        self.min_messages_for_learning = 30
        self.min_learning_interval = 60  # seconds
    
    def _get_lock(self, chat_id: str) -> asyncio.Lock:
        """Get or create lock for a chat."""
        if chat_id not in self._learning_locks:
            self._learning_locks[chat_id] = asyncio.Lock()
        return self._learning_locks[chat_id]
    
    def should_trigger_learning(self, chat_id: str) -> bool:
        """Check if learning should be triggered for this chat.
        
        Args:
            chat_id: Chat identifier
            
        Returns:
            True if learning should be triggered
        """
        # Check time interval
        current_time = time.time()
        last_time = self._last_learning_time.get(chat_id, 0)
        time_diff = current_time - last_time
        
        if time_diff < self.min_learning_interval:
            return False
        
        # Check message count
        msg_count = self._message_count.get(chat_id, 0)
        if msg_count < self.min_messages_for_learning:
            return False
        
        return True
    
    def record_message(self, chat_id: str):
        """Record a message for this chat.
        
        Args:
            chat_id: Chat identifier
        """
        self._message_count[chat_id] = self._message_count.get(chat_id, 0) + 1
    
    async def trigger_learning(
        self,
        chat_id: str,
        llm_client: LLMClient,
        bot_name: Optional[str] = None
    ):
        """Trigger learning cycle for a chat.
        
        Args:
            chat_id: Chat identifier
            llm_client: LLM client for learning
            bot_name: Bot name for context
        """
        lock = self._get_lock(chat_id)
        
        # Try to acquire lock (non-blocking)
        if lock.locked():
            logger.debug(f"Learning already in progress for {chat_id}, skipping")
            return
        
        async with lock:
            # Double-check after acquiring lock
            if not self.should_trigger_learning(chat_id):
                return
            
            # Update tracking
            current_time = time.time()
            last_time = self._last_learning_time.get(chat_id, 0)
            msg_count = self._message_count.get(chat_id, 0)
            
            # Reset counters
            self._last_learning_time[chat_id] = current_time
            self._message_count[chat_id] = 0
            
            logger.info(
                f"Triggering learning for {chat_id}: "
                f"{msg_count} messages, {current_time - last_time:.1f}s since last learning"
            )
            
            try:
                # Get messages from the time window
                messages = await self.message_recorder.get_messages_since(
                    chat_id=chat_id,
                    since_time=last_time
                )
                
                if not messages:
                    logger.debug(f"No messages to learn from for {chat_id}")
                    return
                
                logger.info(f"Got {len(messages)} messages for learning in {chat_id}")
                
                # Get learning config
                if chat_id.startswith('group_'):
                    config_type = 'group'
                    target_id = chat_id.replace('group_', '', 1)
                elif chat_id.startswith('private_'):
                    config_type = 'private'
                    target_id = chat_id.replace('private_', '', 1)
                else:
                    config_type = 'global'
                    target_id = None
                
                learning_config = await self.learning_config.get_config(config_type, target_id)
                
                # Trigger learning tasks
                tasks = []
                
                # 1. Expression learning
                if self.learning_config.is_feature_enabled('expression_learning', learning_config):
                    tasks.append(
                        self.expression_learner.learn_from_messages(
                            chat_id=chat_id,
                            messages=messages,
                            llm_client=llm_client,
                            bot_name=bot_name
                        )
                    )
                
                # 2. Jargon mining
                if self.learning_config.is_feature_enabled('jargon_learning', learning_config):
                    tasks.append(
                        self.jargon_miner.extract_jargons_from_messages(
                            chat_id=chat_id,
                            messages=messages,
                            llm_client=llm_client,
                            bot_name=bot_name
                        )
                    )
                
                # 3. Sticker learning
                if self.learning_config.is_feature_enabled('sticker_learning', learning_config):
                    tasks.append(
                        self.sticker_manager.process_messages_for_learning(
                            chat_id=chat_id,
                            messages=messages,
                            llm_client=llm_client
                        )
                    )
                
                # Run all learning tasks concurrently
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
                    logger.info(f"Learning tasks completed for {chat_id}")
                
            except Exception as e:
                logger.error(f"Learning failed for {chat_id}: {e}", exc_info=True)


# Global singleton
_learning_scheduler: Optional[LearningScheduler] = None


def get_learning_scheduler() -> LearningScheduler:
    """Get global learning scheduler instance."""
    global _learning_scheduler
    if _learning_scheduler is None:
        _learning_scheduler = LearningScheduler()
    return _learning_scheduler

