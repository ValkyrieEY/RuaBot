"""Search Jargon Tool - Search for jargon/slang terms."""

from src.core.logger import get_logger
from ...ai_database import get_ai_database

logger = get_logger(__name__)


def make_search_jargon(chat_id: str):
    """Factory function to create search_jargon tool bound to a specific chat_id."""
    
    async def search_jargon(keyword: str) -> str:
        """Search for jargon terms by keyword.
        
        Args:
            keyword: Keyword(s) to search for in content/meaning
            
        Returns:
            Formatted search results
        """
        try:
            ai_db = get_ai_database()
            
            # Parse keywords
            keywords = [k.strip() for k in keyword.replace('，', ',').replace(' ', ',').split(',') if k.strip()]
            
            # Search jargons (only is_jargon=True)
            results = await ai_db.get_jargons(
                chat_id=chat_id,
                is_jargon=True,
                limit=20
            )
            
            # Filter by keywords (simple substring match)
            if keywords:
                filtered = []
                for jargon in results:
                    for kw in keywords:
                        if kw.lower() in (jargon.content or '').lower() or \
                           kw.lower() in (jargon.meaning or '').lower():
                            filtered.append(jargon)
                            break
                results = filtered
            
            if not results:
                return f"未找到相关黑话。搜索关键词: {keywords}"
            
            # Format results
            output_lines = [f"找到 {len(results)} 条黑话：\n"]
            
            for idx, jargon in enumerate(results, 1):
                output_lines.append(
                    f"{idx}. ID={jargon.id} | 黑话: {jargon.content} | "
                    f"含义: {jargon.meaning or '无'} | "
                    f"使用次数: {jargon.count}"
                )
            
            output_lines.append("\n注意: 黑话信息仅供参考，请勿修改")
            
            return "\n".join(output_lines)
            
        except Exception as e:
            logger.error(f"搜索黑话失败: {e}", exc_info=True)
            return f"搜索失败: {str(e)}"
    
    return search_jargon

