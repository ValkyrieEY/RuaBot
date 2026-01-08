"""Expression Selector - selects appropriate expressions based on context.

Inspired by RuaBot's expression selection system, this module:
1. Selects expressions from database based on current context
2. Uses LLM to intelligently choose appropriate expressions
3. Considers reply reason and chat context
4. Updates expression usage statistics
"""

import re
import json
import time
import random
from typing import List, Dict, Optional, Any, Tuple
from json_repair import repair_json

from ..core.logger import get_logger
from .ai_database import get_ai_database
from .llm_client import LLMClient

logger = get_logger(__name__)


class ExpressionSelector:
    """Selects appropriate expressions based on context."""
    
    def __init__(self):
        """Initialize expression selector."""
        self.ai_db = get_ai_database()
    
    async def select_expressions(
        self,
        chat_id: str,
        chat_context: str,
        reply_reason: Optional[str] = None,
        target_message: Optional[str] = None,
        llm_client: Optional[LLMClient] = None,
        max_count: int = 8,
        think_level: int = 1
    ) -> List[Dict[str, str]]:
        """Select appropriate expressions based on context.
        
        Args:
            chat_id: Chat ID
            chat_context: Current chat context
            reply_reason: Planner's reasoning for reply
            target_message: Target message to reply to
            llm_client: LLM client (if None, use simple selection)
            max_count: Maximum number of expressions to return
            think_level: Thinking level (0=simple, 1=advanced)
            
        Returns:
            List of selected expressions as dicts with 'situation' and 'style' keys
        """
        try:
            # Get available expressions
            expressions = await self.ai_db.get_expressions(
                chat_id=chat_id,
                rejected=False,
                limit=100
            )
            
            if not expressions:
                logger.debug(f"No expressions found for {chat_id}")
                return []
            
            # Simple selection (think_level=0): random selection of high-count expressions
            if think_level == 0 or not llm_client:
                return await self._select_expressions_simple(
                    expressions, 
                    max_count,
                    chat_id=chat_id,
                    reply_reason=reply_reason
                )
            
            # Advanced selection (think_level=1): LLM-based selection
            return await self._select_expressions_advanced(
                expressions=expressions,
                chat_context=chat_context,
                reply_reason=reply_reason,
                target_message=target_message,
                llm_client=llm_client,
                max_count=max_count
            )
            
        except Exception as e:
            logger.error(f"Failed to select expressions: {e}", exc_info=True)
            return []
    
    async def _select_expressions_simple(
        self,
        expressions: List[Any],
        max_count: int,
        chat_id: str = "",
        reply_reason: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """Simple expression selection: random selection of high-count expressions.
        
        Args:
            expressions: List of Expression objects
            max_count: Maximum number to select
            chat_id: Chat ID for usage tracking
            reply_reason: Reply reason for usage tracking
            
        Returns:
            List of selected expressions
        """
        try:
            # Filter high-count expressions (count > 1)
            high_count_exprs = [e for e in expressions if e.count > 1]
            
            if len(high_count_exprs) < 8:
                logger.debug(f"Not enough high-count expressions ({len(high_count_exprs)}), using all expressions")
                high_count_exprs = expressions
            
            if not high_count_exprs:
                return []
            
            # Random selection
            select_count = min(5, len(high_count_exprs))
            selected = random.sample(high_count_exprs, select_count)
            
            # Update last_active_time and record usage
            current_time = time.time()
            context_str = f"chat_id={chat_id}, reason={reply_reason[:50] if reply_reason else 'none'}"
            
            # Record usage for reflection
            try:
                from .expression_reflector import get_expression_reflector
                reflector = get_expression_reflector()
                for expr in selected:
                    await self.ai_db.update_expression(
                        expr.id,
                        last_active_time=current_time
                    )
                    # Record usage for reflection
                    reflector.usage_tracker.record_usage(
                        expression_id=expr.id,
                        context=context_str,
                        success=True
                    )
            except Exception as e:
                logger.warning(f"Failed to record expression usage: {e}")
                # Still update last_active_time even if usage tracking fails
                for expr in selected:
                    await self.ai_db.update_expression(
                        expr.id,
                        last_active_time=current_time
                    )
            
            result = [
                {"situation": e.situation, "style": e.style}
                for e in selected
            ]
            
            logger.debug(f"Simple selection: selected {len(result)} expressions")
            return result
            
        except Exception as e:
            logger.error(f"Simple selection failed: {e}", exc_info=True)
            return []
    
    async def _select_expressions_advanced(
        self,
        expressions: List[Any],
        chat_context: str,
        reply_reason: Optional[str],
        target_message: Optional[str],
        llm_client: LLMClient,
        max_count: int
    ) -> List[Dict[str, str]]:
        """Advanced expression selection using LLM.
        
        Args:
            expressions: List of Expression objects
            chat_context: Chat context
            reply_reason: Reply reasoning
            target_message: Target message
            llm_client: LLM client
            max_count: Maximum number to select
            
        Returns:
            List of selected expressions
        """
        try:
            # Separate high-count and low-count expressions
            high_count_exprs = [e for e in expressions if e.count > 1]
            all_exprs = expressions
            
            # Build candidate pool
            candidates = []
            
            # Add high-count expressions (up to 5)
            if len(high_count_exprs) >= 10:
                # Weighted sampling
                selected_high = self._weighted_sample(high_count_exprs, min(5, len(high_count_exprs)))
                candidates.extend(selected_high)
            
            # Add random expressions (up to 5)
            selected_random = self._weighted_sample(all_exprs, min(5, len(all_exprs)))
            
            # Merge candidates (deduplicate)
            candidate_ids = {e.id for e in candidates}
            for expr in selected_random:
                if expr.id not in candidate_ids:
                    candidates.append(expr)
                    candidate_ids.add(expr.id)
            
            # Shuffle to avoid bias
            random.shuffle(candidates)
            
            if len(candidates) < 10:
                logger.info(f"Not enough candidates ({len(candidates)}), using simple selection")
                return await self._select_expressions_simple(expressions, max_count)
            
            # Build situation list for LLM
            situation_lines = []
            for idx, expr in enumerate(candidates, 1):
                situation_lines.append(f"{idx}. 当{expr.situation}时: {expr.style}")
            
            situations_str = "\n".join(situation_lines)
            
            # Build prompt
            context_block = ""
            if reply_reason:
                context_block = f"你的回复理由是：{reply_reason}\n"
            else:
                context_block = f"以下是正在进行的聊天内容：{chat_context}\n"
            
            target_block = ""
            target_extra = ""
            if target_message:
                target_block = f'，现在你想要对这条消息进行回复："{target_message}"'
                target_extra = "4. 考虑你要回复的目标消息\n"
            
            prompt = f"""{context_block}{target_block}

以下是可选的表达情境：
{situations_str}

请你分析聊天内容的语境、情绪、话题类型，从上述情境中选择最适合当前聊天情境的，最多{max_count}个情境。

考虑因素包括：
1. 聊天的情绪氛围（轻松、严肃、幽默等）
2. 话题类型（日常、技术、游戏、情感等）
3. 情境与当前语境的匹配度
{target_extra}
请以JSON格式输出，只需要输出选中的情境编号：
例如：
{{
    "selected_situations": [2, 3, 5, 7]
}}

请严格按照JSON格式输出：
"""
            
            # Call LLM
            response = await llm_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
                max_tokens=300,
                stream=False
            )
            
            if isinstance(response, dict):
                response_text = response.get("content", "")
            else:
                response_text = str(response)
            
            if not response_text:
                logger.warning("LLM returned empty response")
                return await self._select_expressions_simple(expressions, max_count)
            
            # Parse response
            result_data = self._parse_selection_response(response_text)
            if not result_data:
                logger.warning("Failed to parse LLM response")
                return await self._select_expressions_simple(expressions, max_count)
            
            selected_indices = result_data.get('selected_situations', [])
            
            # Get selected expressions
            selected_exprs = []
            for idx in selected_indices:
                if isinstance(idx, int) and 1 <= idx <= len(candidates):
                    selected_exprs.append(candidates[idx - 1])
            
            if not selected_exprs:
                logger.warning("No valid expressions selected by LLM")
                return await self._select_expressions_simple(expressions, max_count)
            
            # Update last_active_time and record usage
            current_time = time.time()
            context_str = f"chat_id={chat_id}, reason={reply_reason[:50] if reply_reason else 'none'}"
            
            # Record usage for reflection
            try:
                from .expression_reflector import get_expression_reflector
                reflector = get_expression_reflector()
                for expr in selected_exprs:
                    await self.ai_db.update_expression(
                        expr.id,
                        last_active_time=current_time
                    )
                    # Record usage for reflection
                    reflector.usage_tracker.record_usage(
                        expression_id=expr.id,
                        context=context_str,
                        success=True  # Will be updated after reply generation if needed
                    )
            except Exception as e:
                logger.warning(f"Failed to record expression usage: {e}")
                # Still update last_active_time even if usage tracking fails
                for expr in selected_exprs:
                    await self.ai_db.update_expression(
                        expr.id,
                        last_active_time=current_time
                    )
            
            result = [
                {"situation": e.situation, "style": e.style}
                for e in selected_exprs
            ]
            
            logger.debug(f"Advanced selection: selected {len(result)} expressions from {len(candidates)} candidates")
            return result
            
        except Exception as e:
            logger.error(f"Advanced selection failed: {e}", exc_info=True)
            return await self._select_expressions_simple(expressions, max_count)
    
    def _weighted_sample(self, items: List[Any], k: int) -> List[Any]:
        """Weighted random sampling based on count.
        
        Args:
            items: List of Expression objects
            k: Number of items to sample
            
        Returns:
            List of sampled items
        """
        if not items:
            return []
        
        k = min(k, len(items))
        
        # Calculate weights based on count
        weights = [max(1, getattr(item, 'count', 1)) for item in items]
        
        # Weighted random sampling
        try:
            import numpy as np
            probabilities = np.array(weights, dtype=float)
            probabilities /= probabilities.sum()
            indices = np.random.choice(len(items), size=k, replace=False, p=probabilities)
            return [items[i] for i in indices]
        except ImportError:
            # Fallback: simple random sampling
            return random.sample(items, k)
    
    def _parse_selection_response(self, response_text: str) -> Optional[Dict[str, Any]]:
        """Parse LLM selection response."""
        try:
            # Extract JSON
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if not json_match:
                return None
            
            json_str = json_match.group(0)
            
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError:
                data = json.loads(repair_json(json_str))
            
            return data
            
        except Exception as e:
            logger.error(f"Failed to parse selection response: {e}")
            return None
    
    async def format_expressions_for_prompt(
        self,
        expressions: List[Dict[str, str]]
    ) -> str:
        """Format selected expressions for inclusion in AI prompt.
        
        Args:
            expressions: List of expression dicts
            
        Returns:
            Formatted string for prompt
        """
        if not expressions:
            return ""
        
        lines = ["在回复时,你可以参考以下的语言习惯,不要生硬使用:"]
        for expr in expressions:
            lines.append(f"当{expr['situation']}时: {expr['style']}")
        
        return "\n".join(lines)


# Global expression selector instance
_expression_selector_instance: Optional[ExpressionSelector] = None


def get_expression_selector() -> ExpressionSelector:
    """Get or create global expression selector instance."""
    global _expression_selector_instance
    if _expression_selector_instance is None:
        _expression_selector_instance = ExpressionSelector()
    return _expression_selector_instance

