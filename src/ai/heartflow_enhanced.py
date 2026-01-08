"""HeartFlow Enhanced - Complete conversation flow and emotional state management.

Complete implementation inspired by RuaBot's HeartFlow system.
Features:
1. Emotional state tracking and management
2. Dynamic conversation rhythm control
3. Group chat atmosphere detection
4. Intelligent silence strategy
5. Multi-party conversation coordination
6. Topic activity assessment
7. Response frequency optimization
"""

import time
from typing import Dict, List, Optional, Any, Tuple
from collections import deque, defaultdict
from dataclasses import dataclass
from enum import Enum

from src.core.logger import get_logger

logger = get_logger(__name__)


class EmotionalState(Enum):
    """Emotional states."""
    NEUTRAL = "neutral"
    HAPPY = "happy"
    EXCITED = "excited"
    SAD = "sad"
    ANGRY = "angry"
    CONFUSED = "confused"
    THOUGHTFUL = "thoughtful"


class AtmosphereLevel(Enum):
    """Conversation atmosphere levels."""
    SILENT = "silent"
    CALM = "calm"
    ACTIVE = "active"
    HEATED = "heated"
    CHAOTIC = "chaotic"


@dataclass
class EmotionMetrics:
    """Emotion metrics for a conversation."""
    current_state: EmotionalState
    intensity: float  # 0.0 to 1.0
    stability: float  # 0.0 to 1.0, higher = more stable
    last_update: float
    history: List[Tuple[EmotionalState, float]]  # (state, timestamp)


@dataclass
class ConversationMetrics:
    """Metrics for conversation flow."""
    message_count: int
    messages_per_minute: float
    active_participants: int
    topic_changes: int
    last_message_time: float
    atmosphere: AtmosphereLevel


class HeartFlowEnhanced:
    """Enhanced HeartFlow system for conversation management."""
    
    def __init__(self):
        """Initialize HeartFlow Enhanced."""
        # Emotional states per chat
        self.emotion_states: Dict[str, EmotionMetrics] = {}
        
        # Conversation metrics per chat
        self.conversation_metrics: Dict[str, ConversationMetrics] = {}
        
        # Message history per chat (for atmosphere detection)
        self.message_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=50))
        
        # Reply tracking
        self.last_reply_time: Dict[str, float] = {}
        self.reply_count: Dict[str, int] = defaultdict(int)
        self.message_count: Dict[str, int] = defaultdict(int)
        
        # Topic tracking
        self.current_topics: Dict[str, List[str]] = defaultdict(list)
        self.topic_start_times: Dict[str, float] = {}
        
        # Participant tracking
        self.active_participants: Dict[str, set] = defaultdict(set)
        self.participant_last_seen: Dict[str, Dict[str, float]] = defaultdict(dict)
        
        logger.info("[HeartFlowEnhanced] 初始化完成")
    
    def record_message(
        self,
        chat_id: str,
        user_id: str,
        content: str,
        is_bot: bool = False
    ):
        """Record a message in the conversation.
        
        Args:
            chat_id: Chat ID
            user_id: User ID
            content: Message content
            is_bot: Whether message is from bot
        """
        now = time.time()
        
        # Add to history
        self.message_history[chat_id].append({
            'user_id': user_id,
            'content': content,
            'is_bot': is_bot,
            'timestamp': now
        })
        
        # Update participant tracking
        self.active_participants[chat_id].add(user_id)
        self.participant_last_seen[chat_id][user_id] = now
        
        # Update message count
        self.message_count[chat_id] += 1
        
        # Clean up old participants (not seen in 5 minutes)
        inactive_threshold = now - 300
        inactive = [
            pid for pid, last_seen in self.participant_last_seen[chat_id].items()
            if last_seen < inactive_threshold
        ]
        for pid in inactive:
            self.active_participants[chat_id].discard(pid)
    
    def update_emotional_state(
        self,
        chat_id: str,
        new_state: EmotionalState,
        intensity: float = 0.5
    ):
        """Update emotional state for a chat.
        
        Args:
            chat_id: Chat ID
            new_state: New emotional state
            intensity: Emotion intensity (0-1)
        """
        now = time.time()
        
        if chat_id in self.emotion_states:
            metrics = self.emotion_states[chat_id]
            
            # Calculate stability (how often state changes)
            time_since_last = now - metrics.last_update
            if time_since_last < 60:  # Changed within 1 minute
                metrics.stability = max(0.0, metrics.stability - 0.1)
            else:
                metrics.stability = min(1.0, metrics.stability + 0.05)
            
            # Update state
            metrics.current_state = new_state
            metrics.intensity = intensity
            metrics.last_update = now
            metrics.history.append((new_state, now))
            
            # Keep last 20 states
            if len(metrics.history) > 20:
                metrics.history = metrics.history[-20:]
        else:
            # Create new metrics
            self.emotion_states[chat_id] = EmotionMetrics(
                current_state=new_state,
                intensity=intensity,
                stability=0.8,
                last_update=now,
                history=[(new_state, now)]
            )
    
    def detect_atmosphere(self, chat_id: str) -> AtmosphereLevel:
        """Detect conversation atmosphere.
        
        Args:
            chat_id: Chat ID
            
        Returns:
            Detected atmosphere level
        """
        history = self.message_history[chat_id]
        
        if len(history) < 2:
            return AtmosphereLevel.SILENT
        
        now = time.time()
        recent_messages = [
            msg for msg in history
            if now - msg['timestamp'] < 300  # Last 5 minutes
        ]
        
        if not recent_messages:
            return AtmosphereLevel.SILENT
        
        # Calculate messages per minute
        time_span = now - recent_messages[0]['timestamp']
        if time_span > 0:
            msg_per_min = len(recent_messages) / (time_span / 60)
        else:
            msg_per_min = 0
        
        # Determine atmosphere
        if msg_per_min < 0.5:
            return AtmosphereLevel.SILENT
        elif msg_per_min < 2:
            return AtmosphereLevel.CALM
        elif msg_per_min < 5:
            return AtmosphereLevel.ACTIVE
        elif msg_per_min < 10:
            return AtmosphereLevel.HEATED
        else:
            return AtmosphereLevel.CHAOTIC
    
    def should_reply(
        self,
        chat_id: str,
        is_group: bool = False,
        mentioned: bool = False,
        force_consider: bool = False
    ) -> Tuple[bool, str]:
        """Determine if bot should reply.
        
        Args:
            chat_id: Chat ID
            is_group: Whether it's a group chat
            mentioned: Whether bot was mentioned
            force_consider: Force consideration even if normally wouldn't reply
            
        Returns:
            Tuple of (should_reply, reason)
        """
        now = time.time()
        
        # Always reply if mentioned
        if mentioned:
            return True, "被提及"
        
        # Private chat - always reply
        if not is_group:
            return True, "私聊"
        
        # Get atmosphere
        atmosphere = self.detect_atmosphere(chat_id)
        
        # Get last reply time
        last_reply = self.last_reply_time.get(chat_id, 0)
        time_since_last = now - last_reply
        
        # Get reply frequency
        reply_count = self.reply_count.get(chat_id, 0)
        msg_count = self.message_count.get(chat_id, 0)
        
        # Calculate reply ratio
        reply_ratio = reply_count / max(1, msg_count)
        
        # Decision logic based on atmosphere
        if atmosphere == AtmosphereLevel.SILENT:
            # In silent atmosphere, be more proactive
            if time_since_last > 300:  # 5 minutes
                return True, "气氛冷清，主动活跃"
            return False, "气氛冷清，但刚回复过"
        
        elif atmosphere == AtmosphereLevel.CALM:
            # In calm atmosphere, reply moderately
            if reply_ratio > 0.3:
                return False, "回复频率已较高"
            if time_since_last > 60:  # 1 minute
                return True, "气氛平静，适度参与"
            return False, "刚回复过"
        
        elif atmosphere == AtmosphereLevel.ACTIVE:
            # In active atmosphere, be selective
            if reply_ratio > 0.2:
                return False, "回复频率已足够"
            if time_since_last > 30:  # 30 seconds
                # Check if there are many active participants
                active_count = len(self.active_participants.get(chat_id, set()))
                if active_count > 5:
                    return False, "人多，减少插入"
                return True, "气氛活跃，适时参与"
            return False, "刚回复过"
        
        elif atmosphere == AtmosphereLevel.HEATED:
            # In heated atmosphere, be very selective
            if reply_ratio > 0.15:
                return False, "回复已够多"
            if time_since_last > 60:  # 1 minute
                return True, "气氛热烈，偶尔参与"
            return False, "刚回复过，避免打扰"
        
        else:  # CHAOTIC
            # In chaotic atmosphere, mostly stay silent
            if time_since_last > 300:  # 5 minutes
                return True, "长时间未回复，简短参与"
            return False, "气氛混乱，保持沉默"
    
    def record_reply(self, chat_id: str):
        """Record that bot replied.
        
        Args:
            chat_id: Chat ID
        """
        now = time.time()
        self.last_reply_time[chat_id] = now
        self.reply_count[chat_id] += 1
    
    def get_optimal_delay(
        self,
        chat_id: str,
        is_group: bool = False
    ) -> float:
        """Get optimal delay before replying.
        
        Args:
            chat_id: Chat ID
            is_group: Whether it's a group chat
            
        Returns:
            Delay in seconds
        """
        if not is_group:
            return 0.5  # Quick reply in private chat
        
        atmosphere = self.detect_atmosphere(chat_id)
        
        # More delay in calmer atmospheres
        if atmosphere == AtmosphereLevel.SILENT:
            return 2.0
        elif atmosphere == AtmosphereLevel.CALM:
            return 1.5
        elif atmosphere == AtmosphereLevel.ACTIVE:
            return 1.0
        elif atmosphere == AtmosphereLevel.HEATED:
            return 0.5
        else:  # CHAOTIC
            return 0.2
    
    def assess_topic_activity(self, chat_id: str) -> float:
        """Assess how active the current topic is.
        
        Args:
            chat_id: Chat ID
            
        Returns:
            Activity score (0-1)
        """
        history = self.message_history[chat_id]
        
        if len(history) < 5:
            return 0.3
        
        now = time.time()
        recent = [msg for msg in history if now - msg['timestamp'] < 180]  # 3 min
        
        if not recent:
            return 0.1
        
        # Calculate message rate
        time_span = now - recent[0]['timestamp']
        if time_span > 0:
            rate = len(recent) / (time_span / 60)
        else:
            rate = 0
        
        # Normalize to 0-1
        activity = min(1.0, rate / 5.0)  # 5 msg/min = max activity
        
        return activity
    
    def get_flow_metrics(self, chat_id: str) -> Dict[str, Any]:
        """Get flow metrics for a chat.
        
        Args:
            chat_id: Chat ID
            
        Returns:
            Dict with flow metrics
        """
        atmosphere = self.detect_atmosphere(chat_id)
        topic_activity = self.assess_topic_activity(chat_id)
        
        emotion_metrics = self.emotion_states.get(chat_id)
        
        return {
            'atmosphere': atmosphere.value,
            'topic_activity': topic_activity,
            'emotional_state': emotion_metrics.current_state.value if emotion_metrics else 'neutral',
            'emotion_intensity': emotion_metrics.intensity if emotion_metrics else 0.5,
            'emotion_stability': emotion_metrics.stability if emotion_metrics else 0.8,
            'active_participants': len(self.active_participants.get(chat_id, set())),
            'message_count': self.message_count.get(chat_id, 0),
            'reply_count': self.reply_count.get(chat_id, 0),
            'reply_ratio': self.reply_count.get(chat_id, 0) / max(1, self.message_count.get(chat_id, 0))
        }
    
    def reset_chat(self, chat_id: str):
        """Reset all data for a chat.
        
        Args:
            chat_id: Chat ID
        """
        self.message_history.pop(chat_id, None)
        self.emotion_states.pop(chat_id, None)
        self.conversation_metrics.pop(chat_id, None)
        self.last_reply_time.pop(chat_id, None)
        self.reply_count.pop(chat_id, None)
        self.message_count.pop(chat_id, None)
        self.current_topics.pop(chat_id, None)
        self.topic_start_times.pop(chat_id, None)
        self.active_participants.pop(chat_id, None)
        self.participant_last_seen.pop(chat_id, None)
        
        logger.info(f"[HeartFlowEnhanced] 重置聊天 {chat_id} 的所有数据")


# Global instance
_heartflow_enhanced: Optional[HeartFlowEnhanced] = None


def get_heartflow_enhanced() -> HeartFlowEnhanced:
    """Get global HeartFlow Enhanced instance.
    
    Returns:
        HeartFlowEnhanced instance
    """
    global _heartflow_enhanced
    if _heartflow_enhanced is None:
        _heartflow_enhanced = HeartFlowEnhanced()
    return _heartflow_enhanced

