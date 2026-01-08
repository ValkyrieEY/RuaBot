"""Create Chat History Tool - Create a new memory record."""

import json
import time
from typing import Optional
from src.core.logger import get_logger
from ...ai_database import get_ai_database

logger = get_logger(__name__)


def make_create_chat_history(chat_id: str):
    """Factory function to create create_chat_history tool bound to a specific chat_id."""
    
    async def create_chat_history(
        theme: str,
        summary: str,
        keywords: str,
        key_point: str,
        start_time: str,
        end_time: str
    ) -> str:
        """Create a new chat history memory record.
        
        Args:
            theme: Theme/title of the memory
            summary: Summary of the conversation
            keywords: Keywords as JSON string, e.g. ['keyword1', 'keyword2']
            key_point: Key points as JSON string, e.g. ['point1', 'point2']
            start_time: Start timestamp (Unix seconds)
            end_time: End timestamp (Unix seconds)
            
        Returns:
            Success or error message
        """
        try:
            # Parse JSON strings
            try:
                keywords_list = json.loads(keywords) if keywords else []
                if not isinstance(keywords_list, list):
                    return f"关键词格式错误，应为 JSON 数组: {keywords}"
            except json.JSONDecodeError:
                return f"关键词 JSON 解析失败: {keywords}"
            
            try:
                key_point_list = json.loads(key_point) if key_point else []
                if not isinstance(key_point_list, list):
                    return f"关键信息格式错误，应为 JSON 数组: {key_point}"
            except json.JSONDecodeError:
                return f"关键信息 JSON 解析失败: {key_point}"
            
            # Parse timestamps
            try:
                start_ts = int(start_time)
                end_ts = int(end_time)
            except ValueError:
                return f"时间戳格式错误: start_time={start_time}, end_time={end_time}"
            
            # Create record
            ai_db = get_ai_database()
            
            new_record = await ai_db.save_chat_history(
                chat_id=chat_id,
                theme=theme,
                summary=summary,
                keywords=keywords_list,
                key_point=key_point_list,
                start_time=start_ts,
                end_time=end_ts,
                participants=None,  # Will be extracted if needed
                original_text=None  # Summary only, no original text
            )
            
            logger.info(f"[Dream] 创建新记忆: ID={new_record.id}, 主题={theme}")
            
            return f"成功创建新记忆 ID={new_record.id}，主题='{theme}'"
            
        except Exception as e:
            logger.error(f"创建记忆失败: {e}", exc_info=True)
            return f"创建失败: {str(e)}"
    
    return create_chat_history

