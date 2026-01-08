"""Expression Auto Checker - Automatically checks and evaluates learned expressions.

Complete implementation inspired by RuaBot's expression auto check system.
Features:
1. Periodic scanning of unchecked expressions
2. LLM-based quality evaluation
3. Automatic marking (checked/rejected)
4. Batch processing with rate limiting
5. Detailed evaluation reports
6. Statistics tracking
"""

import asyncio
import time
import json
from typing import List, Dict, Optional, Any, Tuple
from json_repair import repair_json

from ..core.logger import get_logger
from .ai_database import get_ai_database
from .llm_client import LLMClient

logger = get_logger(__name__)


class ExpressionAutoChecker:
    """Automatically checks and evaluates learned expressions."""
    
    def __init__(self):
        """Initialize expression auto checker."""
        self.ai_db = get_ai_database()
        
        # Statistics
        self.total_checked = 0
        self.total_accepted = 0
        self.total_rejected = 0
        self.last_check_time: Optional[float] = None
    
    async def check_unchecked_expressions(
        self,
        llm_client: LLMClient,
        chat_id: Optional[str] = None,
        limit: int = 20,
        batch_size: int = 5
    ) -> Dict[str, Any]:
        """Check unchecked expressions using LLM evaluation.
        
        Args:
            llm_client: LLM client
            chat_id: Optional chat_id to filter by
            limit: Maximum number of expressions to check
            batch_size: Number of expressions to evaluate in one batch
            
        Returns:
            Dict with check results
        """
        start_time = time.time()
        logger.info(f"[ExpressionAutoChecker] 开始自动检查表达方式，限制={limit}")
        
        try:
            # Get unchecked expressions
            unchecked = await self.ai_db.get_expressions(
                chat_id=chat_id,
                checked=False,
                rejected=False,
                limit=limit
            )
            
            if not unchecked:
                logger.info("[ExpressionAutoChecker] 没有未检查的表达方式")
                return {
                    'total_found': 0,
                    'total_checked': 0,
                    'accepted': 0,
                    'rejected': 0,
                    'cost_seconds': time.time() - start_time
                }
            
            logger.info(f"[ExpressionAutoChecker] 找到 {len(unchecked)} 个未检查的表达方式")
            
            # Process in batches
            checked_count = 0
            accepted_count = 0
            rejected_count = 0
            
            for i in range(0, len(unchecked), batch_size):
                batch = unchecked[i:i + batch_size]
                
                logger.info(f"[ExpressionAutoChecker] 处理批次 {i // batch_size + 1}, 大小={len(batch)}")
                
                # Evaluate batch
                results = await self._evaluate_batch(batch, llm_client)
                
                # Update database
                for expr, evaluation in zip(batch, results):
                    checked_count += 1
                    
                    if evaluation['accepted']:
                        accepted_count += 1
                        await self.ai_db.update_expression(
                            expr.id,
                            checked=True,
                            rejected=False
                        )
                    else:
                        rejected_count += 1
                        await self.ai_db.update_expression(
                            expr.id,
                            checked=True,
                            rejected=True
                        )
                    
                    logger.debug(
                        f"[ExpressionAutoChecker] 表达方式 ID={expr.id}: "
                        f"{'接受' if evaluation['accepted'] else '拒绝'} - {evaluation['reason']}"
                    )
                
                # Rate limiting between batches
                if i + batch_size < len(unchecked):
                    await asyncio.sleep(2)
            
            # Update statistics
            self.total_checked += checked_count
            self.total_accepted += accepted_count
            self.total_rejected += rejected_count
            self.last_check_time = time.time()
            
            cost = time.time() - start_time
            
            result = {
                'total_found': len(unchecked),
                'total_checked': checked_count,
                'accepted': accepted_count,
                'rejected': rejected_count,
                'cost_seconds': cost
            }
            
            logger.info(
                f"[ExpressionAutoChecker] 检查完成: "
                f"总数={len(unchecked)}, 已检查={checked_count}, "
                f"接受={accepted_count}, 拒绝={rejected_count}, 耗时={cost:.1f}s"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"[ExpressionAutoChecker] 检查失败: {e}", exc_info=True)
            return {
                'total_found': 0,
                'total_checked': 0,
                'accepted': 0,
                'rejected': 0,
                'error': str(e),
                'cost_seconds': time.time() - start_time
            }
    
    async def _evaluate_batch(
        self,
        expressions: List[Any],
        llm_client: LLMClient
    ) -> List[Dict[str, Any]]:
        """Evaluate a batch of expressions using LLM.
        
        Args:
            expressions: List of Expression objects
            llm_client: LLM client
            
        Returns:
            List of evaluation results
        """
        # Build evaluation prompt
        prompt = self._build_evaluation_prompt(expressions)
        
        try:
            # Call LLM
            response = await llm_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2000
            )
            
            if isinstance(response, dict):
                response_text = response.get("content", "")
            else:
                response_text = str(response)
            
            if not response_text:
                logger.warning("[ExpressionAutoChecker] LLM 返回空响应，全部接受")
                return [{'accepted': True, 'reason': 'LLM 无响应，默认接受'} for _ in expressions]
            
            # Parse results
            results = self._parse_evaluation_results(response_text, len(expressions))
            
            # Ensure we have results for all expressions
            while len(results) < len(expressions):
                results.append({'accepted': True, 'reason': '评估结果不足，默认接受'})
            
            return results[:len(expressions)]
            
        except Exception as e:
            logger.error(f"[ExpressionAutoChecker] LLM 评估失败: {e}", exc_info=True)
            return [{'accepted': True, 'reason': f'评估失败: {str(e)}'} for _ in expressions]
    
    def _build_evaluation_prompt(self, expressions: List[Any]) -> str:
        """Build prompt for expression evaluation.
        
        Args:
            expressions: List of Expression objects
            
        Returns:
            Prompt string
        """
        expr_lines = []
        for idx, expr in enumerate(expressions, 1):
            expr_lines.append(
                f"{idx}. 情境：{expr.situation}\n"
                f"   表达方式：{expr.style}\n"
                f"   来源：{expr.chat_id}\n"
                f"   使用次数：{expr.count}"
            )
        
        expressions_text = "\n\n".join(expr_lines)
        
        prompt = f"""你是一个AI表达方式质量评估专家。请评估以下学习的表达方式的质量。

评估标准：
1. **接受条件**：
   - 表达方式自然、流畅
   - 情境描述清晰、具体
   - 没有明显的语法错误或病句
   - 不包含敏感、不当内容
   - 表达方式与情境匹配

2. **拒绝条件**：
   - 表达方式包含明显错误或无意义内容
   - 情境描述过于模糊或不准确
   - 包含占位符（如 [占位符]、<xxx>、{{xxx}}）
   - 包含 SELF、BOT、AI 等自我指代（除非情境明确需要）
   - 包含图片标记（如 [CQ:image...)、[图片]）
   - 包含链接或特殊代码
   - 表达方式与情境严重不匹配

待评估的表达方式：

{expressions_text}

请对每个表达方式进行评估，并以JSON格式输出结果：

{{
    "evaluations": [
        {{"id": 1, "accepted": true, "reason": "表达方式自然，情境清晰"}},
        {{"id": 2, "accepted": false, "reason": "包含占位符"}},
        ...
    ]
}}

只输出JSON，不要其他内容。"""
        
        return prompt
    
    def _parse_evaluation_results(self, response_text: str, expected_count: int) -> List[Dict[str, Any]]:
        """Parse LLM evaluation results.
        
        Args:
            response_text: LLM response
            expected_count: Expected number of results
            
        Returns:
            List of evaluation dicts
        """
        try:
            # Extract JSON
            import re
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if not json_match:
                logger.warning("[ExpressionAutoChecker] 未找到 JSON，尝试修复")
                # Try to repair the whole response
                try:
                    data = json.loads(repair_json(response_text))
                except:
                    return []
            else:
                json_str = json_match.group(0)
                try:
                    data = json.loads(json_str)
                except json.JSONDecodeError:
                    data = json.loads(repair_json(json_str))
            
            evaluations = data.get('evaluations', [])
            
            # Convert to our format
            results = []
            for eval_item in evaluations:
                results.append({
                    'accepted': eval_item.get('accepted', True),
                    'reason': eval_item.get('reason', '无原因')
                })
            
            return results
            
        except Exception as e:
            logger.error(f"[ExpressionAutoChecker] 解析评估结果失败: {e}")
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get checker statistics.
        
        Returns:
            Statistics dict
        """
        acceptance_rate = (self.total_accepted / self.total_checked * 100) if self.total_checked > 0 else 0
        
        return {
            'total_checked': self.total_checked,
            'total_accepted': self.total_accepted,
            'total_rejected': self.total_rejected,
            'acceptance_rate': acceptance_rate,
            'last_check_time': self.last_check_time
        }


# Global instance
_expression_auto_checker: Optional[ExpressionAutoChecker] = None


def get_expression_auto_checker() -> ExpressionAutoChecker:
    """Get global expression auto checker instance.
    
    Returns:
        ExpressionAutoChecker instance
    """
    global _expression_auto_checker
    if _expression_auto_checker is None:
        _expression_auto_checker = ExpressionAutoChecker()
    return _expression_auto_checker


async def start_expression_auto_check_scheduler(
    llm_client: LLMClient,
    interval_minutes: int = 60,
    batch_size: int = 10,
    stop_event: Optional[asyncio.Event] = None
):
    """Start periodic expression auto checking.
    
    Args:
        llm_client: LLM client
        interval_minutes: Check interval in minutes
        batch_size: Batch size for evaluation
        stop_event: Optional stop event
    """
    checker = get_expression_auto_checker()
    
    logger.info(f"[ExpressionAutoChecker] 调度器启动，间隔={interval_minutes}分钟")
    
    try:
        while True:
            if stop_event and stop_event.is_set():
                logger.info("[ExpressionAutoChecker] 收到停止信号")
                break
            
            # Run check
            await checker.check_unchecked_expressions(
                llm_client=llm_client,
                limit=50,
                batch_size=batch_size
            )
            
            # Wait
            try:
                if stop_event:
                    await asyncio.wait_for(
                        stop_event.wait(),
                        timeout=interval_minutes * 60
                    )
                    break
                else:
                    await asyncio.sleep(interval_minutes * 60)
            except asyncio.TimeoutError:
                pass
                
    except asyncio.CancelledError:
        logger.info("[ExpressionAutoChecker] 调度器被取消")
        raise
    except Exception as e:
        logger.error(f"[ExpressionAutoChecker] 调度器异常: {e}", exc_info=True)

