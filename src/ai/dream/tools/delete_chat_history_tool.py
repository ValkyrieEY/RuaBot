"""Delete Chat History Tool - Delete a memory record."""

from src.core.logger import get_logger
from ...ai_database import get_ai_database

logger = get_logger(__name__)


def make_delete_chat_history(chat_id: str):
    """Factory function to create delete_chat_history tool bound to a specific chat_id."""
    
    async def delete_chat_history(memory_id: int) -> str:
        """Delete a chat history memory record.
        
        Args:
            memory_id: The ID of the ChatHistory record to delete
            
        Returns:
            Success or error message
        """
        try:
            ai_db = get_ai_database()
            session = ai_db.get_session()
            
            try:
                from ...ai_database_models import ChatHistory
                
                # First verify the memory exists and belongs to this chat_id
                record = session.query(ChatHistory).filter(
                    ChatHistory.id == memory_id,
                    ChatHistory.chat_id == chat_id
                ).first()
                
                if not record:
                    return f"未找到 memory_id={memory_id} 的记录（或不属于当前 chat_id={chat_id}）"
                
                theme = record.theme
                
                # Delete
                session.delete(record)
                session.commit()
                
                logger.info(f"[Dream] 删除记忆: ID={memory_id}, 主题={theme}")
                
                return f"成功删除记忆 ID={memory_id}，主题='{theme}'"
                
            finally:
                session.close()
                
        except Exception as e:
            logger.error(f"删除记忆失败: {e}", exc_info=True)
            return f"删除失败: {str(e)}"
    
    return delete_chat_history

