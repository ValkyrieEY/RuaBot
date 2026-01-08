"""Sticker Learner - learns sticker usage patterns from chat messages.

This module learns when and how users use stickers/emojis/images in conversations,
similar to RuaBot's expression learning but focused on visual elements.
"""

import re
import time
import asyncio
from typing import List, Optional, Dict, Any, Tuple

from ..core.logger import get_logger
from .ai_database import get_ai_database
from .llm_client import LLMClient

logger = get_logger(__name__)


class StickerLearner:
    """Learns sticker usage patterns from chat messages."""
    
    def __init__(self):
        """Initialize sticker learner."""
        self.ai_db = get_ai_database()
        self._learning_lock = asyncio.Lock()
    
    async def learn_from_messages(
        self,
        chat_id: str,
        messages: List[Any],
        llm_client: Optional[LLMClient] = None
    ) -> List[Dict[str, Any]]:
        """Learn sticker usage from messages.
        
        Args:
            chat_id: Chat ID
            messages: List of message objects with sticker information
            llm_client: Optional LLM client for analyzing stickers
            
        Returns:
            List of learned sticker records
        """
        async with self._learning_lock:
            try:
                learned_stickers = []
                
                for msg in messages:
                    # Skip bot's own messages
                    if self._is_bot_message(msg):
                        continue
                    
                    # Extract stickers from message
                    stickers = self._extract_stickers_from_message(msg)
                    
                    if not stickers:
                        continue
                    
                    # Get context around the sticker usage
                    context = self._build_context(messages, msg)
                    
                    # Process each sticker
                    for sticker_info in stickers:
                        try:
                            # Infer situation/emotion from context
                            situation, emotion = await self._infer_sticker_usage(
                                sticker_info=sticker_info,
                                context=context,
                                llm_client=llm_client
                            )
                            
                            if not situation:
                                situation = "表达情感"  # Default situation
                            
                            # Save or update sticker record
                            sticker = await self.ai_db.save_sticker(
                                sticker_type=sticker_info['type'],
                                situation=situation,
                                chat_id=chat_id,
                                sticker_id=sticker_info.get('id'),
                                sticker_url=sticker_info.get('url'),
                                sticker_file=sticker_info.get('file'),
                                emotion=emotion,
                                context=context
                            )
                            
                            learned_stickers.append({
                                'sticker_id': sticker.id,
                                'type': sticker.sticker_type,
                                'situation': situation,
                                'emotion': emotion
                            })
                            
                            logger.info(
                                f"Learned sticker usage: {sticker_info['type']} - "
                                f"{situation} ({emotion})"
                            )
                            
                        except Exception as e:
                            logger.error(f"Failed to process sticker: {e}", exc_info=True)
                            continue
                
                if learned_stickers:
                    logger.info(f"Learned {len(learned_stickers)} sticker usages from {len(messages)} messages")
                
                return learned_stickers
                
            except Exception as e:
                logger.error(f"Failed to learn from messages: {e}", exc_info=True)
                return []
    
    def _extract_stickers_from_message(self, message: Any) -> List[Dict[str, Any]]:
        """Extract sticker information from a message.
        
        Supports various sticker types:
        - image: Regular images
        - face: Platform-specific emoji/face (e.g., QQ face)
        - emoji: Unicode emoji
        - sticker: Platform sticker packs
        
        Args:
            message: Message object
            
        Returns:
            List of sticker info dicts
        """
        stickers = []
        
        try:
            # Check if message has content to parse
            message_content = getattr(message, 'display_message', None) or \
                            getattr(message, 'content', None) or \
                            getattr(message, 'text', '')
            
            if not message_content:
                return stickers
            
            # Extract images (CQ code format: [CQ:image,file=xxx,url=xxx])
            image_pattern = r'\[CQ:image,(?:file=([^,\]]+),?)?(?:url=([^\]]+))?\]'
            for match in re.finditer(image_pattern, message_content):
                file_name = match.group(1)
                url = match.group(2)
                stickers.append({
                    'type': 'image',
                    'file': file_name,
                    'url': url,
                    'id': file_name or url
                })
            
            # Extract face/emoji (CQ code format: [CQ:face,id=xxx])
            face_pattern = r'\[CQ:face,id=(\d+)\]'
            for match in re.finditer(face_pattern, message_content):
                face_id = match.group(1)
                stickers.append({
                    'type': 'face',
                    'id': face_id,
                    'file': None,
                    'url': None
                })
            
            # Extract platform stickers (e.g., [CQ:sticker,id=xxx])
            sticker_pattern = r'\[CQ:sticker,id=([^\]]+)\]'
            for match in re.finditer(sticker_pattern, message_content):
                sticker_id = match.group(1)
                stickers.append({
                    'type': 'sticker',
                    'id': sticker_id,
                    'file': None,
                    'url': None
                })
            
            # Detect Unicode emoji
            emoji_pattern = r'[\U0001F300-\U0001F9FF]+'
            for match in re.finditer(emoji_pattern, message_content):
                emoji_text = match.group(0)
                stickers.append({
                    'type': 'emoji',
                    'id': emoji_text,
                    'file': None,
                    'url': None
                })
            
        except Exception as e:
            logger.error(f"Failed to extract stickers from message: {e}")
        
        return stickers
    
    def _build_context(
        self,
        messages: List[Any],
        target_message: Any,
        context_window: int = 5
    ) -> str:
        """Build context around a message.
        
        Args:
            messages: All messages
            target_message: The message containing sticker
            context_window: Number of messages before/after to include
            
        Returns:
            Context string
        """
        try:
            # Find target message index
            target_time = getattr(target_message, 'time', None) or \
                         getattr(target_message, 'timestamp', time.time())
            
            # Get messages sorted by time
            sorted_messages = sorted(
                messages,
                key=lambda m: getattr(m, 'time', None) or getattr(m, 'timestamp', 0)
            )
            
            target_idx = None
            for idx, msg in enumerate(sorted_messages):
                msg_time = getattr(msg, 'time', None) or getattr(msg, 'timestamp', 0)
                if abs(msg_time - target_time) < 0.1:  # Same message
                    target_idx = idx
                    break
            
            if target_idx is None:
                return self._get_message_text(target_message)
            
            # Get context messages
            start_idx = max(0, target_idx - context_window)
            end_idx = min(len(sorted_messages), target_idx + context_window + 1)
            context_messages = sorted_messages[start_idx:end_idx]
            
            # Build context string
            context_parts = []
            for msg in context_messages:
                text = self._get_message_text(msg)
                if text:
                    sender = getattr(msg, 'user_nickname', None) or \
                            getattr(msg, 'sender_name', '用户')
                    context_parts.append(f"{sender}: {text}")
            
            return "\n".join(context_parts)
            
        except Exception as e:
            logger.error(f"Failed to build context: {e}")
            return ""
    
    def _get_message_text(self, message: Any) -> str:
        """Get plain text from message, removing CQ codes."""
        try:
            text = getattr(message, 'plain_text', None) or \
                  getattr(message, 'processed_plain_text', None) or \
                  getattr(message, 'text', '')
            
            if not text:
                # Try to get from display_message and remove CQ codes
                text = getattr(message, 'display_message', '') or \
                      getattr(message, 'content', '')
                # Remove CQ codes
                text = re.sub(r'\[CQ:[^\]]+\]', '[表情]', text)
            
            return text.strip()
            
        except Exception:
            return ""
    
    def _is_bot_message(self, message: Any) -> bool:
        """Check if message is from bot."""
        is_bot = getattr(message, 'is_bot_message', False) or \
                getattr(message, 'is_bot', False) or \
                getattr(message, 'from_bot', False)
        return bool(is_bot)
    
    async def _infer_sticker_usage(
        self,
        sticker_info: Dict[str, Any],
        context: str,
        llm_client: Optional[LLMClient] = None
    ) -> Tuple[str, Optional[str]]:
        """Infer when/why the sticker was used.
        
        Args:
            sticker_info: Sticker information
            context: Context messages
            llm_client: Optional LLM client for inference
            
        Returns:
            Tuple of (situation, emotion)
        """
        try:
            # If no LLM client, use simple heuristics
            if not llm_client:
                return self._infer_simple(sticker_info, context)
            
            # Use LLM to infer usage
            return await self._infer_with_llm(sticker_info, context, llm_client)
            
        except Exception as e:
            logger.error(f"Failed to infer sticker usage: {e}")
            return "表达情感", None
    
    def _infer_simple(
        self,
        sticker_info: Dict[str, Any],
        context: str
    ) -> Tuple[str, Optional[str]]:
        """Simple heuristic-based inference."""
        # Default values
        situation = "表达情感"
        emotion = None
        
        # Simple keyword-based detection
        context_lower = context.lower()
        
        if any(word in context_lower for word in ['哈哈', '笑', '好笑', '有趣']):
            situation = "表示好笑"
            emotion = "开心"
        elif any(word in context_lower for word in ['无语', '无奈', '服了']):
            situation = "表示无语"
            emotion = "无奈"
        elif any(word in context_lower for word in ['赞', '厉害', '牛', '强']):
            situation = "表示赞同"
            emotion = "赞同"
        elif any(word in context_lower for word in ['哭', '难过', '伤心']):
            situation = "表示难过"
            emotion = "难过"
        elif any(word in context_lower for word in ['惊', '震惊', '吓']):
            situation = "表示惊讶"
            emotion = "惊讶"
        
        return situation, emotion
    
    async def _infer_with_llm(
        self,
        sticker_info: Dict[str, Any],
        context: str,
        llm_client: LLMClient
    ) -> Tuple[str, Optional[str]]:
        """Use LLM to infer sticker usage."""
        try:
            prompt = f"""以下是聊天对话，其中使用了一个{sticker_info['type']}类型的表情：

{context}

请分析在这个对话中，发送表情的人想要表达什么情境和情感。

输出格式（JSON）：
{{
    "situation": "简短描述使用该表情的情境，不超过20字",
    "emotion": "一个词描述情感，如：开心、无语、赞同、惊讶等"
}}

请只输出JSON，不要其他内容：
"""
            
            response = await llm_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=150,
                stream=False
            )
            
            if isinstance(response, dict):
                response_text = response.get("content", "")
            else:
                response_text = str(response)
            
            if not response_text:
                return self._infer_simple(sticker_info, context)
            
            # Parse response
            import json
            from json_repair import repair_json
            
            try:
                # Extract JSON
                json_match = re.search(r'\{[\s\S]*\}', response_text)
                if json_match:
                    json_str = json_match.group(0)
                    try:
                        result = json.loads(json_str)
                    except json.JSONDecodeError:
                        result = json.loads(repair_json(json_str))
                    
                    situation = result.get('situation', '表达情感')
                    emotion = result.get('emotion')
                    
                    return situation, emotion
            except Exception as e:
                logger.error(f"Failed to parse LLM response: {e}")
            
            return self._infer_simple(sticker_info, context)
            
        except Exception as e:
            logger.error(f"LLM inference failed: {e}")
            return self._infer_simple(sticker_info, context)


# Global sticker learner instance
_sticker_learner_instance: Optional[StickerLearner] = None


def get_sticker_learner() -> StickerLearner:
    """Get or create global sticker learner instance."""
    global _sticker_learner_instance
    if _sticker_learner_instance is None:
        _sticker_learner_instance = StickerLearner()
    return _sticker_learner_instance

