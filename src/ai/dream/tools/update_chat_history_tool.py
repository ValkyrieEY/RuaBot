"""Update Chat History Tool - Update an existing memory record."""

import json
from typing import Optional
from src.core.logger import get_logger
from ...ai_database import get_ai_database

logger = get_logger(__name__)


def make_update_chat_history(chat_id: str):
    """Factory function to create update_chat_history tool bound to a specific chat_id."""
    
    async def update_chat_history(
        memory_id: int,
        theme: Optional[str] = None,
        summary: Optional[str] = None,
        keywords: Optional[str] = None,
        key_point: Optional[str] = None
    ) -> str:
        """Update fields of an existing chat history memory.
        
        Args:
            memory_id: The ID of the ChatHistory record to update
            theme: New theme (optional)
            summary: New summary (optional)
            keywords: New keywords as JSON string (optional)
            key_point: New key points as JSON string (optional)
            
        Returns:
            Success or error message
        """
        try:
            # First verify the memory exists and belongs to this chat_id
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
                
                # Build update dict
                updates = {}
                
                if theme is not None:
                    updates['theme'] = theme
                
                if summary is not None:
                    updates['summary'] = summary
                
                if keywords is not None:
                    try:
                        keywords_list = json.loads(keywords)
                        if not isinstance(keywords_list, list):
                            return f"关键词格式错误，应为 JSON 数组: {keywords}"
                        updates['keywords'] = json.dumps(keywords_list, ensure_ascii=False)
                    except json.JSONDecodeError:
                        return f"关键词 JSON 解析失败: {keywords}"
                
                if key_point is not None:
                    try:
                        key_point_list = json.loads(key_point)
                        if not isinstance(key_point_list, list):
                            return f"关键信息格式错误，应为 JSON 数组: {key_point}"
                        updates['key_point'] = json.dumps(key_point_list, ensure_ascii=False)
                    except json.JSONDecodeError:
                        return f"关键信息 JSON 解析失败: {key_point}"
                
                if not updates:
                    return "未提供任何更新字段"
                
                # Update
                for key, value in updates.items():
                    setattr(record, key, value)
                
                session.commit()
                
                logger.info(f"[Dream] 更新记忆: ID={memory_id}, 字段={list(updates.keys())}")
                
                return f"成功更新记忆 ID={memory_id}，更新字段: {', '.join(updates.keys())}"
                
            finally:
                session.close()
                
        except Exception as e:
            logger.error(f"更新记忆失败: {e}", exc_info=True)
            return f"更新失败: {str(e)}"
    
    return update_chat_history

