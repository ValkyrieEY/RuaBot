"""Dream Generator - Generates summaries of dream maintenance sessions."""

import time
from typing import List, Dict, Any
from src.core.logger import get_logger

logger = get_logger(__name__)


async def generate_dream_summary(
    chat_id: str,
    conversation: List[Dict[str, Any]],
    iterations: int,
    cost_seconds: float
) -> str:
    """Generate a summary of the dream maintenance session.
    
    Args:
        chat_id: Chat ID that was maintained
        conversation: Full conversation history
        iterations: Number of iterations completed
        cost_seconds: Time cost in seconds
        
    Returns:
        Summary string
    """
    try:
        # Extract tool calls from conversation
        tool_calls_count = 0
        tools_used = []
        
        for msg in conversation:
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    tool_name = tc.get("function", {}).get("name")
                    if tool_name:
                        tools_used.append(tool_name)
                        tool_calls_count += 1
        
        # Count unique operations
        from collections import Counter
        tool_counter = Counter(tools_used)
        
        summary_lines = [
            f"=== Dream 维护总结 ===",
            f"Chat ID: {chat_id}",
            f"轮次: {iterations}",
            f"耗时: {cost_seconds:.1f}s",
            f"工具调用总数: {tool_calls_count}",
            f"",
            f"操作统计:"
        ]
        
        for tool_name, count in tool_counter.most_common():
            summary_lines.append(f"  - {tool_name}: {count} 次")
        
        summary = "\n".join(summary_lines)
        
        logger.info(f"[Dream] 维护总结:\n{summary}")
        
        return summary
        
    except Exception as e:
        logger.error(f"生成 Dream 总结失败: {e}", exc_info=True)
        return f"维护完成，共 {iterations} 轮，耗时 {cost_seconds:.1f}s"

