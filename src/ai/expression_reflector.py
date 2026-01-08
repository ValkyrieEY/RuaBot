"""Expression Reflector - Reflects on expression usage and effectiveness.

Complete implementation inspired by RuaBot's expression reflector.
Features:
1. Tracks expression usage and context
2. Analyzes usage effectiveness
3. Identifies low-performing expressions
4. Provides usage recommendations
5. Adjusts expression selection strategy
6. Generates reflection reports
"""

import time
import json
from typing import List, Dict, Optional, Any, Tuple
from collections import defaultdict
from json_repair import repair_json

from ..core.logger import get_logger
from .ai_database import get_ai_database
from .llm_client import LLMClient

logger = get_logger(__name__)


class ExpressionUsageTracker:
    """Tracks expression usage for reflection."""
    
    def __init__(self):
        """Initialize usage tracker."""
        # {expression_id: [(timestamp, context, success), ...]}
        self.usage_history: Dict[int, List[Tuple[float, str, bool]]] = defaultdict(list)
        self.max_history_per_expr = 100
    
    def record_usage(
        self,
        expression_id: int,
        context: str,
        success: bool = True
    ):
        """Record expression usage.
        
        Args:
            expression_id: Expression ID
            context: Usage context
            success: Whether usage was successful
        """
        timestamp = time.time()
        self.usage_history[expression_id].append((timestamp, context, success))
        
        # Keep only recent history
        if len(self.usage_history[expression_id]) > self.max_history_per_expr:
            self.usage_history[expression_id] = self.usage_history[expression_id][-self.max_history_per_expr:]
    
    def get_usage_stats(self, expression_id: int) -> Dict[str, Any]:
        """Get usage statistics for an expression.
        
        Args:
            expression_id: Expression ID
            
        Returns:
            Usage statistics dict
        """
        history = self.usage_history.get(expression_id, [])
        
        if not history:
            return {
                'total_uses': 0,
                'success_count': 0,
                'success_rate': 0.0,
                'recent_uses': 0,
                'last_use_time': None
            }
        
        total = len(history)
        success_count = sum(1 for _, _, success in history if success)
        success_rate = success_count / total if total > 0 else 0.0
        
        # Recent uses (last 24 hours)
        now = time.time()
        recent_uses = sum(1 for ts, _, _ in history if now - ts < 86400)
        
        last_use_time = max(ts for ts, _, _ in history)
        
        return {
            'total_uses': total,
            'success_count': success_count,
            'success_rate': success_rate,
            'recent_uses': recent_uses,
            'last_use_time': last_use_time
        }


class ExpressionReflector:
    """Reflects on expression usage and provides recommendations."""
    
    def __init__(self):
        """Initialize expression reflector."""
        self.ai_db = get_ai_database()
        self.usage_tracker = ExpressionUsageTracker()
        
        # Statistics
        self.total_reflections = 0
        self.total_analyzed = 0
        self.total_recommendations = 0
        self.last_reflection_time: Optional[float] = None
    
    async def reflect_on_expressions(
        self,
        llm_client: LLMClient,
        chat_id: Optional[str] = None,
        min_usage_count: int = 5,
        limit: int = 30
    ) -> Dict[str, Any]:
        """Reflect on expression usage and generate recommendations.
        
        Args:
            llm_client: LLM client
            chat_id: Optional chat_id to filter by
            min_usage_count: Minimum usage count to consider
            limit: Maximum number of expressions to analyze
            
        Returns:
            Reflection results dict
        """
        start_time = time.time()
        self.total_reflections += 1
        
        logger.info(f"[ExpressionReflector] 开始反思表达方式使用情况")
        
        try:
            # Get expressions with sufficient usage
            expressions = await self.ai_db.get_expressions(
                chat_id=chat_id,
                checked=True,
                rejected=False,
                limit=limit * 2  # Get more to filter
            )
            
            # Filter by usage count
            expressions = [e for e in expressions if e.count >= min_usage_count]
            expressions = expressions[:limit]
            
            if not expressions:
                logger.info("[ExpressionReflector] 没有满足条件的表达方式")
                return {
                    'total_analyzed': 0,
                    'recommendations': [],
                    'cost_seconds': time.time() - start_time
                }
            
            logger.info(f"[ExpressionReflector] 分析 {len(expressions)} 个表达方式")
            
            # Analyze expressions
            analysis_results = await self._analyze_expressions(expressions, llm_client)
            
            # Generate recommendations
            recommendations = await self._generate_recommendations(
                expressions,
                analysis_results,
                llm_client
            )
            
            # Update statistics
            self.total_analyzed += len(expressions)
            self.total_recommendations += len(recommendations)
            self.last_reflection_time = time.time()
            
            # Apply recommendations (mark low-quality expressions)
            applied_count = await self._apply_recommendations(recommendations)
            
            cost = time.time() - start_time
            
            result = {
                'total_analyzed': len(expressions),
                'recommendations': recommendations,
                'applied_count': applied_count,
                'cost_seconds': cost
            }
            
            logger.info(
                f"[ExpressionReflector] 反思完成: "
                f"分析={len(expressions)}, 建议={len(recommendations)}, "
                f"应用={applied_count}, 耗时={cost:.1f}s"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"[ExpressionReflector] 反思失败: {e}", exc_info=True)
            return {
                'total_analyzed': 0,
                'recommendations': [],
                'error': str(e),
                'cost_seconds': time.time() - start_time
            }
    
    async def _analyze_expressions(
        self,
        expressions: List[Any],
        llm_client: LLMClient
    ) -> List[Dict[str, Any]]:
        """Analyze expressions using LLM.
        
        Args:
            expressions: List of Expression objects
            llm_client: LLM client
            
        Returns:
            List of analysis results
        """
        prompt = self._build_analysis_prompt(expressions)
        
        try:
            response = await llm_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
                max_tokens=3000
            )
            
            if isinstance(response, dict):
                response_text = response.get("content", "")
            else:
                response_text = str(response)
            
            if not response_text:
                logger.warning("[ExpressionReflector] LLM 返回空响应")
                return []
            
            # Parse results
            results = self._parse_analysis_results(response_text, len(expressions))
            return results
            
        except Exception as e:
            logger.error(f"[ExpressionReflector] LLM 分析失败: {e}", exc_info=True)
            return []
    
    def _build_analysis_prompt(self, expressions: List[Any]) -> str:
        """Build prompt for expression analysis.
        
        Args:
            expressions: List of Expression objects
            
        Returns:
            Prompt string
        """
        expr_lines = []
        for idx, expr in enumerate(expressions, 1):
            usage_stats = self.usage_tracker.get_usage_stats(expr.id)
            
            expr_lines.append(
                f"{idx}. 情境：{expr.situation}\n"
                f"   表达方式：{expr.style}\n"
                f"   使用次数：{expr.count}\n"
                f"   追踪成功率：{usage_stats['success_rate']:.0%}\n"
                f"   最近使用：{usage_stats['recent_uses']} 次（24h内）"
            )
        
        expressions_text = "\n\n".join(expr_lines)
        
        prompt = f"""你是一个AI表达方式使用效果分析专家。请分析以下表达方式的使用情况，并评估其效果。

分析维度：
1. **使用频率**：使用次数是否合理
2. **适用性**：表达方式是否适合其情境
3. **多样性**：是否与其他表达方式重复
4. **时效性**：是否仍然适用于当前语境
5. **质量**：整体表达质量

评估结果：
- excellent: 非常好，应该继续使用
- good: 良好，保持使用
- fair: 一般，可以改进
- poor: 较差，考虑减少使用
- remove: 应该删除或停用

表达方式列表：

{expressions_text}

请对每个表达方式进行分析，并以JSON格式输出结果：

{{
    "analyses": [
        {{
            "id": 1,
            "rating": "excellent",
            "reason": "使用频率合理，表达自然，适合情境",
            "recommendations": ["继续保持使用"]
        }},
        {{
            "id": 2,
            "rating": "poor",
            "reason": "使用频率过低，可能不够自然",
            "recommendations": ["考虑重写", "减少优先级"]
        }},
        ...
    ]
}}

只输出JSON，不要其他内容。"""
        
        return prompt
    
    def _parse_analysis_results(self, response_text: str, expected_count: int) -> List[Dict[str, Any]]:
        """Parse LLM analysis results.
        
        Args:
            response_text: LLM response
            expected_count: Expected number of results
            
        Returns:
            List of analysis dicts
        """
        try:
            import re
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if not json_match:
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
            
            analyses = data.get('analyses', [])
            return analyses
            
        except Exception as e:
            logger.error(f"[ExpressionReflector] 解析分析结果失败: {e}")
            return []
    
    async def _generate_recommendations(
        self,
        expressions: List[Any],
        analysis_results: List[Dict[str, Any]],
        llm_client: LLMClient
    ) -> List[Dict[str, Any]]:
        """Generate recommendations based on analysis.
        
        Args:
            expressions: List of Expression objects
            analysis_results: Analysis results from LLM
            llm_client: LLM client
            
        Returns:
            List of recommendations
        """
        recommendations = []
        
        for i, (expr, analysis) in enumerate(zip(expressions, analysis_results)):
            rating = analysis.get('rating', 'good')
            reason = analysis.get('reason', '')
            recs = analysis.get('recommendations', [])
            
            # Generate recommendation
            recommendation = {
                'expression_id': expr.id,
                'situation': expr.situation,
                'style': expr.style,
                'rating': rating,
                'reason': reason,
                'recommendations': recs,
                'action': None
            }
            
            # Determine action
            if rating == 'remove':
                recommendation['action'] = 'mark_rejected'
            elif rating == 'poor':
                recommendation['action'] = 'decrease_priority'
            elif rating == 'excellent':
                recommendation['action'] = 'increase_priority'
            
            recommendations.append(recommendation)
        
        return recommendations
    
    async def _apply_recommendations(self, recommendations: List[Dict[str, Any]]) -> int:
        """Apply recommendations to expressions.
        
        Args:
            recommendations: List of recommendations
            
        Returns:
            Number of applied recommendations
        """
        applied = 0
        
        for rec in recommendations:
            action = rec.get('action')
            expr_id = rec.get('expression_id')
            
            if not action or not expr_id:
                continue
            
            try:
                if action == 'mark_rejected':
                    await self.ai_db.update_expression(expr_id, rejected=True)
                    applied += 1
                    logger.info(f"[ExpressionReflector] 标记表达方式 {expr_id} 为拒绝")
                
                # Note: priority adjustment would require additional fields in database
                # For now, we just log the recommendation
                elif action in ['increase_priority', 'decrease_priority']:
                    logger.info(f"[ExpressionReflector] 建议 {action} 表达方式 {expr_id}")
                    applied += 1
                    
            except Exception as e:
                logger.error(f"[ExpressionReflector] 应用建议失败: {e}")
        
        return applied
    
    def record_usage(self, expression_id: int, context: str, success: bool = True):
        """Record expression usage for future reflection.
        
        Args:
            expression_id: Expression ID
            context: Usage context
            success: Whether usage was successful
        """
        self.usage_tracker.record_usage(expression_id, context, success)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get reflector statistics.
        
        Returns:
            Statistics dict
        """
        return {
            'total_reflections': self.total_reflections,
            'total_analyzed': self.total_analyzed,
            'total_recommendations': self.total_recommendations,
            'last_reflection_time': self.last_reflection_time,
            'tracked_expressions': len(self.usage_tracker.usage_history)
        }


# Global instance
_expression_reflector: Optional[ExpressionReflector] = None


def get_expression_reflector() -> ExpressionReflector:
    """Get global expression reflector instance.
    
    Returns:
        ExpressionReflector instance
    """
    global _expression_reflector
    if _expression_reflector is None:
        _expression_reflector = ExpressionReflector()
    return _expression_reflector

