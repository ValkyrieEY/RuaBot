"""Search Chat History Tool - Search for chat history memories."""

from typing import Optional, List
from src.core.logger import get_logger
from ...ai_database import get_ai_database

logger = get_logger(__name__)


def make_search_chat_history(chat_id: str):
    """Factory function to create search_chat_history tool bound to a specific chat_id."""
    
    async def search_chat_history(
        keyword: Optional[str] = None,
        participant: Optional[str] = None
    ) -> str:
        """Search chat history memories by keyword or participant.
        
        Args:
            keyword: Keywords to search for (optional, can be multiple separated by space/comma)
            participant: Participant nickname to filter by (optional)
            
        Returns:
            Formatted search results
        """
        try:
            ai_db = get_ai_database()
            
            # Parse keywords
            keywords = None
            if keyword:
                # Split by space, comma, or Chinese comma
                keywords = [k.strip() for k in keyword.replace('，', ',').replace(' ', ',').split(',') if k.strip()]
            
            # Search
            results = await ai_db.search_chat_history(
                chat_id=chat_id,
                keywords=keywords,
                limit=20
            )
            
            if not results:
                return f"未找到相关记忆。搜索条件: 关键词={keywords}, 参与者={participant}"
            
            # Format results
            output_lines = [f"找到 {len(results)} 条相关记忆：\n"]
            
            for idx, record in enumerate(results, 1):
                output_lines.append(
                    f"{idx}. ID={record.id} | 主题: {record.theme or '无'} | "
                    f"关键词: {record.keywords or '无'} | "
                    f"时间: {record.start_time} 至 {record.end_time}"
                )
            
            output_lines.append("\n提示: 使用 get_chat_history_detail(memory_id) 查看详细内容")
            
            return "\n".join(output_lines)
            
        except Exception as e:
            logger.error(f"搜索聊天历史失败: {e}", exc_info=True)
            return f"搜索失败: {str(e)}"
    
    return search_chat_history

