"""Chat Summarizer - Creates summaries of conversations for long-term memory.

This module:
1. Monitors message accumulation
2. Automatically summarizes chat segments
3. Stores summaries with themes and key points
4. Provides memory retrieval for context
"""

import time
import json
import asyncio
from typing import List, Dict, Optional, Any
from json_repair import repair_json

from ..core.logger import get_logger
from .ai_database import get_ai_database
from .llm_client import LLMClient

logger = get_logger(__name__)


class ChatSummarizer:
    """Summarizes conversations for long-term memory."""
    
    def __init__(self):
        """Initialize chat summarizer."""
        self.ai_db = get_ai_database()
        self._last_summary_time: Dict[str, float] = {}  # {chat_id: timestamp}
        self._summarizing: Dict[str, bool] = {}  # {chat_id: is_summarizing}
    
    async def check_and_summarize(
        self,
        chat_id: str,
        llm_client: Optional[LLMClient] = None,
        force: bool = False
    ) -> bool:
        """Check if chat needs summarization and create summary if needed.
        
        Args:
            chat_id: Chat ID
            llm_client: LLM client for summarization
            force: Force summarization even if not needed
            
        Returns:
            True if summary was created
        """
        if not llm_client:
            return False
        
        # Avoid concurrent summarization
        if self._summarizing.get(chat_id, False):
            return False
        
        try:
            self._summarizing[chat_id] = True
            
            # Check if enough time has passed since last summary
            last_summary = self._last_summary_time.get(chat_id, 0)
            current_time = time.time()
            
            # Summarize every 30 minutes or 100 messages
            if not force and (current_time - last_summary < 1800):  # 30 minutes
                return False
            
            # Get recent messages
            messages = await self.ai_db.get_recent_messages(
                chat_id=chat_id,
                limit=100,
                exclude_bot=False
            )
            
            if len(messages) < 10:  # Need at least 10 messages to summarize
                return False
            
            # Create summary
            summary_data = await self._create_summary(messages, llm_client)
            
            if not summary_data:
                return False
            
            # Save summary to database
            start_time = messages[0].time
            end_time = messages[-1].time
            
            await self.ai_db.save_chat_history(
                chat_id=chat_id,
                start_time=start_time,
                end_time=end_time,
                original_text=self._build_chat_text(messages),
                summary=summary_data['summary'],
                theme=summary_data['theme'],
                participants=summary_data.get('participants', []),
                keywords=summary_data.get('keywords', []),
                key_point=summary_data.get('key_points', [])
            )
            
            self._last_summary_time[chat_id] = current_time
            logger.info(f"Created chat summary for {chat_id}: {summary_data['theme']}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to summarize chat: {e}", exc_info=True)
            return False
        finally:
            self._summarizing[chat_id] = False
    
    def _build_chat_text(self, messages: List[Any]) -> str:
        """Build chat text from messages."""
        lines = []
        for msg in messages[:50]:  # Limit to 50 messages for storage
            user_name = msg.user_nickname or f"User_{msg.user_id}"
            content = msg.plain_text or ""
            timestamp = time.strftime('%H:%M:%S', time.localtime(msg.time))
            lines.append(f"[{timestamp}] {user_name}: {content}")
        return "\n".join(lines)
    
    async def _create_summary(
        self,
        messages: List[Any],
        llm_client: LLMClient
    ) -> Optional[Dict[str, Any]]:
        """Create summary from messages using LLM.
        
        Args:
            messages: List of message records
            llm_client: LLM client
            
        Returns:
            Summary data dict or None
        """
        try:
            # Build chat context
            chat_text = self._build_chat_text(messages)
            
            # Build prompt
            prompt = self._build_summary_prompt(chat_text)
            
            # Call LLM
            response = await llm_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1000,
                stream=False
            )
            
            if isinstance(response, dict):
                response_text = response.get("content", "")
            else:
                response_text = str(response)
            
            # Parse response
            summary_data = self._parse_summary_response(response_text)
            
            return summary_data
            
        except Exception as e:
            logger.error(f"Failed to create summary: {e}", exc_info=True)
            return None
    
    def _build_summary_prompt(self, chat_text: str) -> str:
        """Build prompt for chat summarization."""
        return f"""请总结以下聊天记录：

{chat_text}

要求：
1. 提取对话的主题（10字以内）
2. 写一段简洁的摘要（50-100字）
3. 提取3-5个关键词
4. 列出3-5个重要信息点
5. 列出参与者名单

请以 JSON 格式输出：
{{
  "theme": "对话主题",
  "summary": "对话摘要...",
  "keywords": ["关键词1", "关键词2", "关键词3"],
  "key_points": ["信息点1", "信息点2", "信息点3"],
  "participants": ["用户1", "用户2"]
}}
"""
    
    def _parse_summary_response(self, response_text: str) -> Optional[Dict[str, Any]]:
        """Parse summary response from LLM."""
        try:
            # Extract JSON
            import re
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if not json_match:
                logger.warning("No JSON found in summary response")
                return None
            
            json_str = json_match.group(0)
            
            # Parse JSON
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError:
                logger.warning("Failed to parse JSON, trying json_repair")
                data = json.loads(repair_json(json_str))
            
            # Validate required fields
            if not data.get('theme') or not data.get('summary'):
                logger.warning("Missing required fields in summary")
                return None
            
            return {
                'theme': data.get('theme', '').strip(),
                'summary': data.get('summary', '').strip(),
                'keywords': data.get('keywords', []),
                'key_points': data.get('key_points', []),
                'participants': data.get('participants', [])
            }
            
        except Exception as e:
            logger.error(f"Failed to parse summary response: {e}", exc_info=True)
            return None


# Global instance
_chat_summarizer_instance: Optional[ChatSummarizer] = None


def get_chat_summarizer() -> ChatSummarizer:
    """Get or create global chat summarizer instance."""
    global _chat_summarizer_instance
    if _chat_summarizer_instance is None:
        _chat_summarizer_instance = ChatSummarizer()
    return _chat_summarizer_instance

