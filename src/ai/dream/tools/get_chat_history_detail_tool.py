"""Get Chat History Detail Tool - Get detailed information about a memory."""

import time
from src.core.logger import get_logger
from ...ai_database import get_ai_database

logger = get_logger(__name__)


def make_get_chat_history_detail(chat_id: str):
    """Factory function to create get_chat_history_detail tool bound to a specific chat_id."""
    
    async def get_chat_history_detail(memory_id: int) -> str:
        """Get detailed information about a specific chat history memory.
        
        Args:
            memory_id: The ID of the ChatHistory record
            
        Returns:
            Formatted detailed information
        """
        try:
            ai_db = get_ai_database()
            session = ai_db.get_session()
            
            try:
                from ...ai_database_models import ChatHistory
                
                record = session.query(ChatHistory).filter(
                    ChatHistory.id == memory_id,
                    ChatHistory.chat_id == chat_id
                ).first()
                
                if not record:
                    return f"未找到 memory_id={memory_id} 的记录（或不属于当前 chat_id={chat_id}）"
                
                # Format timestamps
                start_time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(record.start_time)) if record.start_time else "未知"
                end_time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(record.end_time)) if record.end_time else "未知"
                
                detail_text = f"""
【记忆详情】
ID: {record.id}
Chat ID: {record.chat_id}
时间范围: {start_time_str} 至 {end_time_str}
主题: {record.theme or '无'}
关键词: {record.keywords or '无'}
参与者: {record.participants or '无'}
概括: {record.summary or '无'}
关键信息: {record.key_point or '无'}
检索次数: {record.count}
创建时间: {record.created_at}
"""
                
                return detail_text.strip()
                
            finally:
                session.close()
                
        except Exception as e:
            logger.error(f"获取记忆详情失败: {e}", exc_info=True)
            return f"获取详情失败: {str(e)}"
    
    return get_chat_history_detail

