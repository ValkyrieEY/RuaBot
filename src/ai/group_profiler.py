"""Group Profiler - Analyzes and remembers group characteristics.

This module:
1. Tracks group messages and dynamics
2. Generates group atmosphere and topic analysis
3. Stores information about group culture
4. Updates profiles over time
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


class GroupProfiler:
    """Analyzes and profiles groups."""
    
    def __init__(self):
        """Initialize group profiler."""
        self.ai_db = get_ai_database()
        self._profiling: Dict[str, bool] = {}  # {group_id: is_profiling}
    
    async def analyze_group(
        self,
        group_id: str,
        chat_id: str,
        llm_client: Optional[LLMClient] = None,
        platform: str = "qq",
        group_name: Optional[str] = None
    ) -> bool:
        """Analyze a group and create/update its profile.
        
        Args:
            group_id: Group ID
            chat_id: Chat ID
            llm_client: LLM client
            platform: Platform name
            group_name: Group name (optional)
            
        Returns:
            True if profile was created/updated
        """
        if not llm_client:
            return False
        
        # Avoid concurrent profiling
        if self._profiling.get(group_id, False):
            return False
        
        try:
            self._profiling[group_id] = True
            
            # Get group messages
            messages = await self.ai_db.get_recent_messages(
                chat_id=chat_id,
                limit=200,
                exclude_bot=False
            )
            
            if len(messages) < 20:  # Need at least 20 messages
                logger.debug(f"Not enough messages in {group_id} to profile")
                return False
            
            # Check if group already exists
            existing = await self.ai_db.get_group_by_id(group_id)
            
            # Generate profile
            profile_data = await self._generate_profile(messages, llm_client, group_name)
            
            if not profile_data:
                return False
            
            current_time = time.time()
            
            # Get member list
            members = list(set([msg.user_id for msg in messages if not msg.is_bot_message]))
            
            if existing:
                # Update existing profile
                await self.ai_db.update_group(
                    existing.id,
                    group_name=group_name or existing.group_name,
                    group_impression=profile_data.get('impression'),
                    topic=profile_data.get('topic'),
                    member_list=members,
                    member_count=len(members),
                    last_active=current_time
                )
                
                logger.info(f"Updated profile for group {group_id}")
            else:
                # Create new profile
                await self.ai_db.create_group(
                    group_id=group_id,
                    platform=platform,
                    group_name=group_name,
                    group_impression=profile_data.get('impression'),
                    topic=profile_data.get('topic'),
                    member_list=members,
                    member_count=len(members),
                    create_time=current_time,
                    last_active=current_time
                )
                
                logger.info(f"Created profile for group {group_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to analyze group: {e}", exc_info=True)
            return False
        finally:
            self._profiling[group_id] = False
    
    async def _generate_profile(
        self,
        messages: List[Any],
        llm_client: LLMClient,
        group_name: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """Generate group profile using LLM.
        
        Args:
            messages: Group messages
            llm_client: LLM client
            group_name: Group name (optional)
            
        Returns:
            Profile data dict or None
        """
        try:
            # Build context
            chat_text = self._build_group_context(messages)
            
            # Build prompt
            prompt = self._build_profile_prompt(chat_text, group_name)
            
            # Call LLM
            response = await llm_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
                max_tokens=800,
                stream=False
            )
            
            if isinstance(response, dict):
                response_text = response.get("content", "")
            else:
                response_text = str(response)
            
            # Parse response
            profile_data = self._parse_profile_response(response_text)
            
            return profile_data
            
        except Exception as e:
            logger.error(f"Failed to generate group profile: {e}", exc_info=True)
            return None
    
    def _build_group_context(self, messages: List[Any]) -> str:
        """Build context from group messages."""
        lines = []
        for msg in messages[-50:]:  # Last 50 messages
            user_name = msg.user_nickname or f"User_{msg.user_id}"
            content = msg.plain_text or ""
            timestamp = time.strftime('%H:%M:%S', time.localtime(msg.time))
            
            # Skip bot messages for analysis
            if msg.is_bot_message:
                continue
            
            lines.append(f"[{timestamp}] {user_name}: {content}")
        return "\n".join(lines)
    
    def _build_profile_prompt(self, chat_text: str, group_name: Optional[str]) -> str:
        """Build prompt for group profiling."""
        name_info = f"群名称：{group_name}\n" if group_name else ""
        
        return f"""{name_info}请分析以下群聊记录，生成群组画像：

{chat_text}

要求：
1. 描述这个群的整体氛围和印象（50-100字）
2. 总结这个群的主要话题和基本信息（30-50字）

请以 JSON 格式输出：
{{
  "impression": "群组氛围描述：这是一个...的群，成员之间...，大家经常讨论...",
  "topic": "主要话题：技术交流、日常闲聊等"
}}
"""
    
    def _parse_profile_response(self, response_text: str) -> Optional[Dict[str, Any]]:
        """Parse profile response from LLM."""
        try:
            import re
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if not json_match:
                return None
            
            json_str = json_match.group(0)
            
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError:
                data = json.loads(repair_json(json_str))
            
            return {
                'impression': data.get('impression', '').strip(),
                'topic': data.get('topic', '').strip()
            }
            
        except Exception as e:
            logger.error(f"Failed to parse group profile response: {e}", exc_info=True)
            return None


# Global instance
_group_profiler_instance: Optional[GroupProfiler] = None


def get_group_profiler() -> GroupProfiler:
    """Get or create global group profiler instance."""
    global _group_profiler_instance
    if _group_profiler_instance is None:
        _group_profiler_instance = GroupProfiler()
    return _group_profiler_instance

