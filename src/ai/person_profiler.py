"""Person Profiler - Analyzes and remembers user characteristics.

This module:
1. Tracks user messages and behaviors
2. Generates user profiles and impressions
3. Stores memory points about users
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


class PersonProfiler:
    """Analyzes and profiles individual users."""
    
    def __init__(self):
        """Initialize person profiler."""
        self.ai_db = get_ai_database()
        self._profiling: Dict[str, bool] = {}  # {person_id: is_profiling}
    
    async def analyze_person(
        self,
        user_id: str,
        chat_id: str,
        llm_client: Optional[LLMClient] = None,
        platform: str = "qq"
    ) -> bool:
        """Analyze a person and create/update their profile.
        
        Args:
            user_id: User ID
            chat_id: Chat ID where user is active
            llm_client: LLM client
            platform: Platform name
            
        Returns:
            True if profile was created/updated
        """
        if not llm_client:
            return False
        
        person_id = f"{platform}:{user_id}"
        
        # Avoid concurrent profiling
        if self._profiling.get(person_id, False):
            return False
        
        try:
            self._profiling[person_id] = True
            
            # Get user's messages
            all_messages = await self.ai_db.get_recent_messages(
                chat_id=chat_id,
                limit=200,
                exclude_bot=False
            )
            
            # Filter to only this user's messages
            user_messages = [msg for msg in all_messages if msg.user_id == user_id and not msg.is_bot_message]
            
            if len(user_messages) < 5:  # Need at least 5 messages
                logger.debug(f"Not enough messages from {user_id} to profile")
                return False
            
            # Check if person already exists
            existing = await self.ai_db.get_person_by_id(person_id)
            
            # Generate profile
            profile_data = await self._generate_profile(user_messages, all_messages, llm_client)
            
            if not profile_data:
                return False
            
            current_time = time.time()
            
            if existing:
                # Update existing profile
                memory_points = existing.memory_points or []
                if isinstance(memory_points, str):
                    try:
                        memory_points = json.loads(memory_points)
                    except:
                        memory_points = []
                
                # Add new memory points
                new_points = profile_data.get('memory_points', [])
                memory_points.extend(new_points)
                # Keep last 20 memory points
                memory_points = memory_points[-20:]
                
                await self.ai_db.update_person(
                    existing.id,
                    person_name=profile_data.get('person_name') or existing.person_name,
                    name_reason=profile_data.get('name_reason') or existing.name_reason,
                    is_known=True,
                    memory_points=memory_points,
                    last_know=current_time
                )
                
                logger.info(f"Updated profile for {person_id}")
            else:
                # Create new profile
                await self.ai_db.create_person(
                    person_id=person_id,
                    platform=platform,
                    user_id=user_id,
                    person_name=profile_data.get('person_name'),
                    name_reason=profile_data.get('name_reason'),
                    nickname=user_messages[0].user_nickname if user_messages else None,
                    is_known=True,
                    memory_points=profile_data.get('memory_points', []),
                    know_times=current_time,
                    know_since=current_time,
                    last_know=current_time
                )
                
                logger.info(f"Created profile for {person_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to analyze person: {e}", exc_info=True)
            return False
        finally:
            self._profiling[person_id] = False
    
    async def _generate_profile(
        self,
        user_messages: List[Any],
        all_messages: List[Any],
        llm_client: LLMClient
    ) -> Optional[Dict[str, Any]]:
        """Generate user profile using LLM.
        
        Args:
            user_messages: Messages from the target user
            all_messages: All messages for context
            llm_client: LLM client
            
        Returns:
            Profile data dict or None
        """
        try:
            # Build context
            user_text = self._build_user_context(user_messages)
            
            # Build prompt
            prompt = self._build_profile_prompt(user_text)
            
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
            logger.error(f"Failed to generate profile: {e}", exc_info=True)
            return None
    
    def _build_user_context(self, messages: List[Any]) -> str:
        """Build context from user's messages."""
        lines = []
        for msg in messages[-30:]:  # Last 30 messages
            timestamp = time.strftime('%H:%M:%S', time.localtime(msg.time))
            content = msg.plain_text or ""
            lines.append(f"[{timestamp}] {content}")
        return "\n".join(lines)
    
    def _build_profile_prompt(self, user_text: str) -> str:
        """Build prompt for user profiling."""
        return f"""请分析以下用户的聊天记录，生成用户画像：

{user_text}

要求：
1. 给这个用户起一个简短的称呼或标签（例如：技术大神、搞笑王、沉默寡言的小伙伴等）
2. 解释为什么给这个称呼
3. 提取3-5个关于这个用户的记忆点（性格特点、兴趣爱好、说话风格等）

请以 JSON 格式输出：
{{
  "person_name": "用户称呼",
  "name_reason": "起这个称呼的原因",
  "memory_points": [
    "记忆点1：喜欢讨论技术话题",
    "记忆点2：说话风格幽默风趣",
    "记忆点3：经常在晚上活跃"
  ]
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
                'person_name': data.get('person_name', '').strip(),
                'name_reason': data.get('name_reason', '').strip(),
                'memory_points': data.get('memory_points', [])
            }
            
        except Exception as e:
            logger.error(f"Failed to parse profile response: {e}", exc_info=True)
            return None


# Global instance
_person_profiler_instance: Optional[PersonProfiler] = None


def get_person_profiler() -> PersonProfiler:
    """Get or create global person profiler instance."""
    global _person_profiler_instance
    if _person_profiler_instance is None:
        _person_profiler_instance = PersonProfiler()
    return _person_profiler_instance

