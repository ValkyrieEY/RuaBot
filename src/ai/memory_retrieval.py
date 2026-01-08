"""Memory Retrieval - retrieves relevant memories from chat history.

Inspired by RuaBot's memory system, this module:
1. Retrieves relevant chat history
2. Searches memories by keywords
3. Provides context-aware memory selection
4. Supports memory summarization
"""

from typing import List, Dict, Optional, Any

from ..core.logger import get_logger
from .ai_database import get_ai_database

logger = get_logger(__name__)


class MemoryRetrieval:
    """Retrieves and manages memories."""
    
    def __init__(self):
        """Initialize memory retrieval."""
        self.ai_db = get_ai_database()
    
    async def search_memories(
        self,
        chat_id: str,
        keywords: Optional[List[str]] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Search chat history memories.
        
        Args:
            chat_id: Chat ID
            keywords: Keywords to search for
            limit: Maximum number of memories to return
            
        Returns:
            List of memory dicts
        """
        try:
            memories = await self.ai_db.search_chat_history(
                chat_id=chat_id,
                keywords=keywords,
                limit=limit
            )
            
            # Convert to dict
            result = []
            for memory in memories:
                result.append({
                    'id': memory.id,
                    'theme': memory.theme,
                    'summary': memory.summary,
                    'original_text': memory.original_text,
                    'start_time': memory.start_time,
                    'end_time': memory.end_time,
                    'participants': memory.participants,
                    'keywords': memory.keywords,
                    'key_point': memory.key_point
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to search memories: {e}", exc_info=True)
            return []
    
    async def format_memories_for_prompt(
        self,
        memories: List[Dict[str, Any]],
        max_count: int = 3
    ) -> str:
        """Format memories for inclusion in prompt.
        
        Args:
            memories: List of memory dicts
            max_count: Maximum number of memories to include
            
        Returns:
            Formatted memory string
        """
        if not memories:
            return ""
        
        lines = ["以下是相关的历史记忆："]
        
        for i, memory in enumerate(memories[:max_count], 1):
            theme = memory.get('theme', '未知主题')
            summary = memory.get('summary', '')
            lines.append(f"{i}. {theme}: {summary}")
        
        return "\n".join(lines)
    
    async def get_person_info(
        self,
        platform: str,
        user_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get person information.
        
        Args:
            platform: Platform name (e.g., 'qq')
            user_id: User ID
            
        Returns:
            Person info dict or None
        """
        try:
            person = await self.ai_db.get_or_create_person_info(
                platform=platform,
                user_id=user_id
            )
            
            if person:
                return {
                    'person_id': person.person_id,
                    'person_name': person.person_name,
                    'is_known': person.is_known,
                    'memory_points': person.memory_points,
                    'nickname': person.nickname
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get person info: {e}", exc_info=True)
            return None
    
    async def get_group_info(
        self,
        platform: str,
        group_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get group information.
        
        Args:
            platform: Platform name (e.g., 'qq')
            group_id: Group ID
            
        Returns:
            Group info dict or None
        """
        try:
            group = await self.ai_db.get_or_create_group_info(
                platform=platform,
                group_id=group_id
            )
            
            if group:
                return {
                    'group_id': group.group_id,
                    'group_name': group.group_name,
                    'group_impression': group.group_impression,
                    'topic': group.topic,
                    'member_count': group.member_count
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get group info: {e}", exc_info=True)
            return None


# Global memory retrieval instance
_memory_retrieval_instance: Optional[MemoryRetrieval] = None


def get_memory_retrieval() -> MemoryRetrieval:
    """Get or create global memory retrieval instance."""
    global _memory_retrieval_instance
    if _memory_retrieval_instance is None:
        _memory_retrieval_instance = MemoryRetrieval()
    return _memory_retrieval_instance

