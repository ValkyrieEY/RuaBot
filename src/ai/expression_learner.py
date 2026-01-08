"""Expression Learner - learns speaking styles and patterns from users.

Inspired by RuaBot's expression learning system, this module:
1. Extracts speaking patterns from chat messages
2. Stores them in a structured format (situation -> style)
3. Selects appropriate expressions based on context
4. Makes AI responses more natural and group-specific
"""

import re
import json
import time
import asyncio
from typing import List, Dict, Optional, Tuple, Any
from json_repair import repair_json

from ..core.logger import get_logger
from .ai_database import get_ai_database
from .llm_client import LLMClient

logger = get_logger(__name__)


class ExpressionLearner:
    """Learns and manages speaking styles/patterns from users."""
    
    def __init__(self):
        """Initialize expression learner."""
        self.ai_db = get_ai_database()
        self._learning_lock = asyncio.Lock()
    
    async def learn_from_messages(
        self,
        chat_id: str,
        messages: List[Dict[str, Any]],
        llm_client: Optional[LLMClient] = None,
        bot_name: str = "AI助手"
    ) -> List[Tuple[str, str]]:
        """Learn expressions from a list of messages.
        
        Args:
            chat_id: Chat ID (format: "group:群号" or "user:QQ号")
            messages: List of message dicts with keys: user_name, content, time, etc.
            llm_client: LLM client for calling AI (if None, skip learning)
            bot_name: Bot's name (to exclude bot's own messages)
            
        Returns:
            List of learned expressions as (situation, style) tuples
        """
        if not messages or not llm_client:
            return []
        
        async with self._learning_lock:
            try:
                # Build chat context string with line numbers
                chat_str = self._build_chat_string(messages, bot_name, show_ids=True)
                
                # Build learning prompt
                prompt = self._build_learning_prompt(chat_str, bot_name)
                
                # Call LLM to extract expressions
                try:
                    response = await llm_client.chat_completion(
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.3,
                        max_tokens=2000,
                        stream=False
                    )
                    
                    if isinstance(response, dict):
                        response_text = response.get("content", "")
                    else:
                        response_text = str(response)
                except Exception as e:
                    logger.error(f"Failed to call LLM for expression learning: {e}", exc_info=True)
                    return []
                
                # Parse response
                expressions = self._parse_expression_response(response_text)
                
                if not expressions:
                    logger.info("No expressions learned from response")
                    return []
                
                # Filter and validate expressions
                validated_expressions = self._filter_expressions(expressions, messages, bot_name)
                
                if not validated_expressions:
                    logger.info("No valid expressions after filtering")
                    return []
                
                # Store expressions in database
                current_time = time.time()
                stored_count = 0
                
                for situation, style in validated_expressions:
                    try:
                        # Check if similar expression exists
                        existing = await self.ai_db.find_similar_expression(
                            chat_id=chat_id,
                            situation=situation,
                            style=style
                        )
                        
                        if existing:
                            # Update existing expression
                            await self.ai_db.update_expression(
                                existing.id,
                                count=existing.count + 1,
                                last_active_time=current_time
                            )
                            logger.debug(f"Updated existing expression: {situation} -> {style}")
                        else:
                            # Create new expression (auto-approved by AI)
                            await self.ai_db.create_expression(
                                situation=situation,
                                style=style,
                                chat_id=chat_id,
                                count=1,
                                last_active_time=current_time,
                                create_date=current_time,
                                checked=True,  # Auto-approve: AI has already reviewed it
                                modified_by='ai'  # Mark as AI-approved
                            )
                            logger.debug(f"Created new expression (auto-approved): {situation} -> {style}")
                        
                        stored_count += 1
                    except Exception as e:
                        logger.error(f"Failed to store expression: {e}", exc_info=True)
                
                logger.info(f"Learned and stored {stored_count}/{len(validated_expressions)} expressions for {chat_id}")
                return validated_expressions
                
            except Exception as e:
                logger.error(f"Failed to learn expressions: {e}", exc_info=True)
                return []
    
    def _build_chat_string(
        self,
        messages: List[Dict[str, Any]],
        bot_name: str,
        show_ids: bool = False
    ) -> str:
        """Build chat context string from messages.
        
        Args:
            messages: List of message dicts
            bot_name: Bot's name
            show_ids: Whether to show message IDs
            
        Returns:
            Formatted chat string
        """
        lines = []
        for idx, msg in enumerate(messages):
            user_name = msg.get('user_name', msg.get('user_nickname', 'User'))
            content = msg.get('content', '')
            
            # Skip empty messages
            if not content.strip():
                continue
            
            # Replace bot's name with SELF for learning
            if user_name == bot_name:
                user_name = "SELF"
            
            if show_ids:
                lines.append(f"[{idx}] {user_name}: {content}")
            else:
                lines.append(f"{user_name}: {content}")
        
        return "\n".join(lines)
    
    def _build_learning_prompt(self, chat_str: str, bot_name: str) -> str:
        """Build prompt for learning expressions.
        
        Args:
            chat_str: Formatted chat string
            bot_name: Bot's name
            
        Returns:
            Learning prompt
        """
        return f"""{chat_str}

你的名字是{bot_name},现在请你完成一个提取任务:

请从上面这段群聊中提取用户的语言风格和说话方式

要求:
1. 只考虑文字,不要考虑表情包和图片
2. 不要总结SELF的发言,因为这是你自己的发言
3. 不要涉及具体的人名,也不要涉及具体名词
4. 思考有没有特殊的梗,一并总结成语言风格
5. 总结成如下格式的规律,总结的内容要详细,但具有概括性

格式要求:
- 每个表达方式格式为: "当[情境]时,[表达方式]"
- 情境描述不超过20个字,表达方式不超过20个字
- 提取3-10个表达方式
- 每个表达方式需要标注来源行编号 (上方聊天记录中方括号里的数字)

示例:
[
  {{"situation": "对某件事表示十分惊叹", "style": "使用 我嘞个xxxx", "source_id": "3"}},
  {{"situation": "表示讽刺的赞同,不讲道理", "style": "对对对", "source_id": "7"}},
  {{"situation": "涉及游戏相关时,夸赞,略带戏谑意味", "style": "使用 这么强!", "source_id": "12"}}
]

其中:
- situation: 表示"在什么情境下"的简短概括(不超过20个字)
- style: 表示对应的语言风格或常用表达(不超过20个字)
- source_id: 该表达方式对应的"来源行编号",即上方聊天记录中方括号里的数字,请只输出数字本身

现在请输出 JSON 数组:
"""
    
    def _parse_expression_response(self, response_text: str) -> List[Tuple[str, str, str]]:
        """Parse LLM response to extract expressions.
        
        Args:
            response_text: LLM response text
            
        Returns:
            List of (situation, style, source_id) tuples
        """
        try:
            # Extract JSON from response
            json_match = re.search(r'\[[\s\S]*\]', response_text)
            if not json_match:
                logger.warning("No JSON array found in response")
                return []
            
            json_str = json_match.group(0)
            
            # Try to parse JSON, use json_repair if failed
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError:
                logger.warning("Failed to parse JSON, trying json_repair")
                data = json.loads(repair_json(json_str))
            
            if not isinstance(data, list):
                logger.warning("Parsed data is not a list")
                return []
            
            expressions = []
            for item in data:
                if not isinstance(item, dict):
                    continue
                
                situation = item.get('situation', '').strip()
                style = item.get('style', '').strip()
                source_id = str(item.get('source_id', '')).strip()
                
                if situation and style:
                    expressions.append((situation, style, source_id))
            
            return expressions
            
        except Exception as e:
            logger.error(f"Failed to parse expression response: {e}", exc_info=True)
            return []
    
    def _filter_expressions(
        self,
        expressions: List[Tuple[str, str, str]],
        messages: List[Dict[str, Any]],
        bot_name: str
    ) -> List[Tuple[str, str]]:
        """Filter and validate expressions.
        
        Args:
            expressions: List of (situation, style, source_id) tuples
            messages: Original messages
            bot_name: Bot's name
            
        Returns:
            List of validated (situation, style) tuples
        """
        validated = []
        
        for situation, style, source_id in expressions:
            # Basic validation
            if len(situation) > 30 or len(style) > 30:
                logger.debug(f"Skipped too long expression: {situation} -> {style}")
                continue
            
            # Check source_id if provided
            if source_id:
                try:
                    idx = int(source_id)
                    if 0 <= idx < len(messages):
                        msg = messages[idx]
                        # Skip if from bot's own message
                        user_name = msg.get('user_name', msg.get('user_nickname', ''))
                        if user_name == bot_name:
                            logger.debug(f"Skipped bot's own expression: {situation} -> {style}")
                            continue
                except (ValueError, IndexError):
                    pass
            
            validated.append((situation, style))
        
        return validated
    
    async def select_expressions(
        self,
        chat_id: str,
        context: str,
        reply_reason: Optional[str] = None,
        llm_client: Optional[LLMClient] = None,
        max_count: int = 8
    ) -> List[Dict[str, str]]:
        """Select appropriate expressions based on context.
        
        Args:
            chat_id: Chat ID
            context: Current chat context
            reply_reason: Planner's reasoning for reply
            llm_client: LLM client (if None, return all recent expressions)
            max_count: Maximum number of expressions to return
            
        Returns:
            List of selected expressions as dicts with 'situation' and 'style' keys
        """
        try:
            # Get available expressions (not rejected, prioritize checked ones)
            expressions = await self.ai_db.get_expressions(
                chat_id=chat_id,
                rejected=False,
                limit=50  # Get more for selection
            )
            
            if not expressions:
                return []
            
            # If no LLM client, return most used expressions
            if not llm_client:
                selected = sorted(expressions, key=lambda e: e.count, reverse=True)[:max_count]
                return [{"situation": e.situation, "style": e.style} for e in selected]
            
            # Use LLM to select appropriate expressions
            # Build selection prompt
            expressions_str = "\n".join([
                f"{i+1}. 当{e.situation}时: {e.style}"
                for i, e in enumerate(expressions)
            ])
            
            prompt = f"""根据以下聊天内容和回复理由,选择最合适的表达方式(最多{max_count}个):

聊天内容:
{context}

{"回复理由: " + reply_reason if reply_reason else ""}

可用的表达方式:
{expressions_str}

请选择最合适的表达方式编号(用逗号分隔,例如: 1,3,5):
"""
            
            try:
                response = await llm_client.chat_completion(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=200,
                    stream=False
                )
                
                if isinstance(response, dict):
                    response_text = response.get("content", "")
                else:
                    response_text = str(response)
                
                # Parse selection
                selected_indices = []
                for match in re.finditer(r'\d+', response_text):
                    idx = int(match.group()) - 1
                    if 0 <= idx < len(expressions):
                        selected_indices.append(idx)
                
                if selected_indices:
                    selected = [expressions[i] for i in selected_indices[:max_count]]
                    return [{"situation": e.situation, "style": e.style} for e in selected]
                
            except Exception as e:
                logger.error(f"Failed to select expressions with LLM: {e}", exc_info=True)
            
            # Fallback: return most used expressions
            selected = sorted(expressions, key=lambda e: e.count, reverse=True)[:max_count]
            return [{"situation": e.situation, "style": e.style} for e in selected]
            
        except Exception as e:
            logger.error(f"Failed to select expressions: {e}", exc_info=True)
            return []
    
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


# Global expression learner instance
_expression_learner_instance: Optional[ExpressionLearner] = None


def get_expression_learner() -> ExpressionLearner:
    """Get or create global expression learner instance.
    
    Returns:
        ExpressionLearner instance
    """
    global _expression_learner_instance
    if _expression_learner_instance is None:
        _expression_learner_instance = ExpressionLearner()
    return _expression_learner_instance

