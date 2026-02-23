"""Sticker Selector - selects appropriate stickers based on context and emotion.

This module selects suitable stickers/emojis/images to use in AI responses,
similar to RuaBot's emoji selection system.
"""

import re
import json
import time
import random
from typing import List, Optional, Dict, Any, Tuple

from ..core.logger import get_logger
from .ai_database import get_ai_database
from .llm_client import LLMClient
from json_repair import repair_json

logger = get_logger(__name__)


class StickerSelector:
    """Selects appropriate stickers based on context and emotion."""
    
    def __init__(self):
        """Initialize sticker selector."""
        self.ai_db = get_ai_database()
    
    async def select_stickers(
        self,
        chat_id: str,
        situation: Optional[str] = None,
        emotion: Optional[str] = None,
        chat_context: Optional[str] = None,
        reply_content: Optional[str] = None,
        llm_client: Optional[LLMClient] = None,
        max_count: int = 3
    ) -> List[Dict[str, Any]]:
        """Select appropriate stickers based on context.
        
        Args:
            chat_id: Chat ID
            situation: Situation description (e.g., "表示开心")
            emotion: Emotion keyword (e.g., "开心", "无语")
            chat_context: Current chat context
            reply_content: AI's reply content (to match sticker with)
            llm_client: Optional LLM client for smart selection
            max_count: Maximum number of stickers to return
            
        Returns:
            List of selected sticker dicts
        """
        try:
            # Get available stickers
            stickers = await self.ai_db.get_stickers(
                chat_id=chat_id,
                checked=None,  # Get all non-rejected stickers
                rejected=False,
                limit=100
            )
            
            if not stickers:
                logger.debug(f"No stickers available for chat {chat_id}")
                return []
            
            # Filter by emotion/situation if provided
            filtered_stickers = self._filter_stickers(
                stickers=stickers,
                emotion=emotion,
                situation=situation
            )
            
            if not filtered_stickers:
                logger.debug(f"No stickers match emotion={emotion}, situation={situation}")
                filtered_stickers = stickers  # Fallback to all stickers
            
            # Simple selection (no LLM)
            if not llm_client:
                return await self._select_simple(
                    stickers=filtered_stickers,
                    max_count=max_count
                )
            
            # Advanced selection (with LLM)
            return await self._select_advanced(
                stickers=filtered_stickers,
                chat_context=chat_context,
                reply_content=reply_content,
                emotion=emotion,
                llm_client=llm_client,
                max_count=max_count
            )
            
        except Exception as e:
            logger.error(f"Failed to select stickers: {e}", exc_info=True)
            return []
    
    def _filter_stickers(
        self,
        stickers: List[Any],
        emotion: Optional[str] = None,
        situation: Optional[str] = None
    ) -> List[Any]:
        """Filter stickers by emotion and situation.
        
        Args:
            stickers: List of Sticker objects
            emotion: Target emotion
            situation: Target situation
            
        Returns:
            Filtered list of stickers
        """
        filtered = []
        
        for sticker in stickers:
            # Check emotion match
            if emotion and sticker.emotion:
                if emotion.lower() in sticker.emotion.lower() or \
                   sticker.emotion.lower() in emotion.lower():
                    filtered.append(sticker)
                    continue
            
            # Check situation match
            if situation and sticker.situation:
                # Simple keyword matching
                if any(word in sticker.situation for word in situation.split()) or \
                   any(word in situation for word in sticker.situation.split()):
                    filtered.append(sticker)
                    continue
            
            # If no specific filter, include all
            if not emotion and not situation:
                filtered.append(sticker)
        
        return filtered
    
    async def _select_simple(
        self,
        stickers: List[Any],
        max_count: int
    ) -> List[Dict[str, Any]]:
        """Simple sticker selection based on usage count.
        
        Args:
            stickers: List of Sticker objects
            max_count: Maximum number to select
            
        Returns:
            List of selected sticker dicts
        """
        try:
            if not stickers:
                return []
            
            # Sort by count (descending) and last_active_time (descending)
            sorted_stickers = sorted(
                stickers,
                key=lambda s: (s.count or 0, s.last_active_time or 0),
                reverse=True
            )
            
            # Take top stickers, but add some randomness
            if len(sorted_stickers) > max_count * 2:
                # From top candidates, randomly select
                top_candidates = sorted_stickers[:max_count * 2]
                selected = random.sample(top_candidates, min(max_count, len(top_candidates)))
            else:
                selected = sorted_stickers[:max_count]
            
            # Update usage statistics
            current_time = time.time()
            result = []
            
            for sticker in selected:
                # Update last_active_time
                await self.ai_db.update_sticker(
                    sticker_id=sticker.id,
                    last_active_time=current_time
                )
                
                result.append({
                    'id': sticker.id,
                    'type': sticker.sticker_type,
                    'sticker_id': sticker.sticker_id,
                    'sticker_url': sticker.sticker_url,
                    'sticker_file': sticker.sticker_file,
                    'situation': sticker.situation,
                    'emotion': sticker.emotion,
                    'meaning': sticker.meaning
                })
            
            logger.debug(f"Simple selection: selected {len(result)} stickers")
            return result
            
        except Exception as e:
            logger.error(f"Simple selection failed: {e}", exc_info=True)
            return []
    
    async def _select_advanced(
        self,
        stickers: List[Any],
        chat_context: Optional[str],
        reply_content: Optional[str],
        emotion: Optional[str],
        llm_client: LLMClient,
        max_count: int
    ) -> List[Dict[str, Any]]:
        """Advanced sticker selection using LLM.
        
        Args:
            stickers: List of Sticker objects
            chat_context: Chat context
            reply_content: AI's reply content
            emotion: Target emotion
            llm_client: LLM client
            max_count: Maximum number to select
            
        Returns:
            List of selected sticker dicts
        """
        try:
            if not stickers:
                return []
            
            # Build sticker candidates list
            candidates = []
            for idx, sticker in enumerate(stickers[:20], 1):  # Limit to top 20 for LLM
                emotion_str = sticker.emotion or "未知"
                situation_str = sticker.situation or "表达情感"
                meaning_str = sticker.meaning or ""
                
                desc = f"{idx}. [{sticker.sticker_type}] {situation_str}"
                if emotion_str != "未知":
                    desc += f" (情感: {emotion_str})"
                if meaning_str:
                    desc += f" - {meaning_str}"
                
                candidates.append({
                    'index': idx,
                    'sticker': sticker,
                    'description': desc
                })
            
            if not candidates:
                return await self._select_simple(stickers, max_count)
            
            candidates_str = "\n".join([c['description'] for c in candidates])
            
            # Build prompt
            context_block = ""
            if reply_content:
                context_block = f"你即将发送的回复内容是：{reply_content}\n\n"
            elif chat_context:
                context_block = f"当前聊天上下文：{chat_context}\n\n"
            
            emotion_block = ""
            if emotion:
                emotion_block = f"你想要表达的情感是：{emotion}\n\n"
            
            from .prompts import build_sticker_selection_prompt
            prompt = build_sticker_selection_prompt(
                reply_content=reply_content,
                chat_context=chat_context,
                emotion=emotion,
                candidates_str=candidates_str,
                max_count=max_count
            )
            
            # Call LLM
            response = await llm_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
                max_tokens=200,
                stream=False
            )
            
            if isinstance(response, dict):
                response_text = response.get("content", "")
            else:
                response_text = str(response)
            
            if not response_text:
                logger.warning("LLM returned empty response, falling back to simple selection")
                return await self._select_simple(stickers, max_count)
            
            # Parse response
            result_data = self._parse_selection_response(response_text)
            if not result_data:
                logger.warning("Failed to parse LLM response, falling back to simple selection")
                return await self._select_simple(stickers, max_count)
            
            selected_indices = result_data.get('selected_stickers', [])
            
            # Get selected stickers
            selected_stickers = []
            for idx in selected_indices:
                if isinstance(idx, int) and 1 <= idx <= len(candidates):
                    selected_stickers.append(candidates[idx - 1]['sticker'])
            
            if not selected_stickers:
                logger.warning("No valid stickers selected by LLM, falling back to simple selection")
                return await self._select_simple(stickers, max_count)
            
            # Update usage statistics and build result
            current_time = time.time()
            result = []
            
            for sticker in selected_stickers:
                await self.ai_db.update_sticker(
                    sticker_id=sticker.id,
                    last_active_time=current_time
                )
                
                result.append({
                    'id': sticker.id,
                    'type': sticker.sticker_type,
                    'sticker_id': sticker.sticker_id,
                    'sticker_url': sticker.sticker_url,
                    'sticker_file': sticker.sticker_file,
                    'situation': sticker.situation,
                    'emotion': sticker.emotion,
                    'meaning': sticker.meaning
                })
            
            logger.debug(f"Advanced selection: selected {len(result)} stickers from {len(candidates)} candidates")
            return result
            
        except Exception as e:
            logger.error(f"Advanced selection failed: {e}", exc_info=True)
            return await self._select_simple(stickers, max_count)
    
    def _parse_selection_response(self, response_text: str) -> Optional[Dict[str, Any]]:
        """Parse LLM selection response."""
        try:
            # Extract JSON
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if not json_match:
                return None
            
            json_str = json_match.group(0)
            
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError:
                data = json.loads(repair_json(json_str))
            
            return data
            
        except Exception as e:
            logger.error(f"Failed to parse selection response: {e}")
            return None
    
    def format_sticker_for_message(
        self,
        sticker: Dict[str, Any]
    ) -> Optional[str]:
        """Format a sticker for inclusion in a message.
        
        Args:
            sticker: Sticker dict with type and id/url/file
            
        Returns:
            Formatted CQ code string or None
        """
        try:
            sticker_type = sticker.get('type', 'image')
            
            if sticker_type == 'image':
                # Image sticker
                if sticker.get('sticker_url'):
                    return f"[CQ:image,url={sticker['sticker_url']}]"
                elif sticker.get('sticker_file'):
                    return f"[CQ:image,file={sticker['sticker_file']}]"
            
            elif sticker_type == 'face':
                # Platform face/emoji
                if sticker.get('sticker_id'):
                    return f"[CQ:face,id={sticker['sticker_id']}]"
            
            elif sticker_type == 'sticker':
                # Platform sticker pack
                if sticker.get('sticker_id'):
                    return f"[CQ:sticker,id={sticker['sticker_id']}]"
            
            elif sticker_type == 'emoji':
                # Unicode emoji
                if sticker.get('sticker_id'):
                    return sticker['sticker_id']  # Just the emoji character
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to format sticker: {e}")
            return None
    
    async def detect_emotion_from_text(
        self,
        text: str,
        llm_client: Optional[LLMClient] = None
    ) -> Optional[str]:
        """Detect emotion from text to help select stickers.
        
        Args:
            text: Text to analyze
            llm_client: Optional LLM client
            
        Returns:
            Detected emotion keyword or None
        """
        try:
            if not text:
                return None
            
            # Simple keyword-based detection
            text_lower = text.lower()
            
            emotion_keywords = {
                '开心': ['开心', '哈哈', '笑', '高兴', '快乐', '😊', '😄', '😁'],
                '无语': ['无语', '无奈', '服了', '醉了', '😑', '🙄'],
                '赞同': ['赞', '厉害', '牛', '强', '棒', '👍', '👏'],
                '难过': ['难过', '伤心', '哭', '😢', '😭'],
                '惊讶': ['惊', '震惊', '卧槽', '天啊', '😱', '😲'],
                '愤怒': ['生气', '愤怒', '气死', '😠', '😡'],
                '疑惑': ['疑惑', '不懂', '什么', '？', '❓', '🤔']
            }
            
            for emotion, keywords in emotion_keywords.items():
                if any(keyword in text_lower for keyword in keywords):
                    return emotion
            
            # If LLM available, use it for more accurate detection
            if llm_client:
                try:
                    from .prompts import build_emotion_analysis_prompt
                    prompt = build_emotion_analysis_prompt(text)
                    response = await llm_client.chat_completion(
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.3,
                        max_tokens=10,
                        stream=False
                    )
                    
                    if isinstance(response, dict):
                        emotion = response.get("content", "").strip()
                    else:
                        emotion = str(response).strip()
                    
                    if emotion and len(emotion) <= 10:
                        return emotion
                except Exception as e:
                    logger.error(f"LLM emotion detection failed: {e}")
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to detect emotion: {e}")
            return None


# Global sticker selector instance
_sticker_selector_instance: Optional[StickerSelector] = None


def get_sticker_selector() -> StickerSelector:
    """Get or create global sticker selector instance."""
    global _sticker_selector_instance
    if _sticker_selector_instance is None:
        _sticker_selector_instance = StickerSelector()
    return _sticker_selector_instance

