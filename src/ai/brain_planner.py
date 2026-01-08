"""Brain Planner - ReAct-based action planning system.

Inspired by RuaBot's BrainPlanner, this module:
1. Implements ReAct (Reasoning-Acting-Observing) pattern
2. Plans actions based on chat context
3. Supports multiple action types (reply, wait, complete_talk)
4. Provides reasoning for each action
"""

import re
import json
import time
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass
from json_repair import repair_json

from ..core.logger import get_logger
from .llm_client import LLMClient

logger = get_logger(__name__)


@dataclass
class ActionPlan:
    """Represents a planned action."""
    action_type: str  # reply, wait, complete_talk
    reasoning: str  # Why this action
    target_message_id: Optional[str] = None
    target_message: Optional[Dict[str, Any]] = None
    action_data: Optional[Dict[str, Any]] = None  # Additional action data
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'action_type': self.action_type,
            'reasoning': self.reasoning,
            'target_message_id': self.target_message_id,
            'target_message': self.target_message,
            'action_data': self.action_data
        }


class BrainPlanner:
    """ReAct-based action planner."""
    
    def __init__(self):
        """Initialize brain planner."""
        self.last_obs_time = 0.0
        self._plan_history: List[Tuple[float, List[ActionPlan]]] = []
    
    async def plan_actions(
        self,
        chat_context: str,
        messages: List[Dict[str, Any]],
        llm_client: LLMClient,
        bot_name: str = "AI助手",
        time_info: Optional[str] = None,
        actions_history: Optional[str] = None
    ) -> List[ActionPlan]:
        """Plan actions based on current context using ReAct pattern.
        
        Args:
            chat_context: Formatted chat context with message IDs
            messages: List of message dicts with IDs
            llm_client: LLM client
            bot_name: Bot's name
            time_info: Current time information
            actions_history: Previous actions history
            
        Returns:
            List of ActionPlan objects
        """
        try:
            # Build planner prompt
            prompt = self._build_planner_prompt(
                chat_context=chat_context,
                bot_name=bot_name,
                time_info=time_info,
                actions_history=actions_history
            )
            
            logger.info(f"[BrainPlanner] 调用 LLM 规划 (prompt: {len(prompt)} 字符)")
            
            # Call LLM
            response = await llm_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
                max_tokens=1000,
                stream=False
            )
            
            if isinstance(response, dict):
                response_text = response.get("content", "")
            else:
                response_text = str(response)
            
            if not response_text:
                logger.warning("[BrainPlanner] LLM 返回空响应")
                return [self._create_fallback_action()]
            
            # Parse actions from response
            actions = self._parse_actions_response(response_text, messages)
            
            if not actions:
                logger.warning("[BrainPlanner] 未解析到有效动作")
                return [self._create_fallback_action()]
            
            # Record plan
            self._plan_history.append((time.time(), actions))
            # Keep only last 10 plans
            self._plan_history = self._plan_history[-10:]
            
            action_types = [a.action_type for a in actions]
            logger.info(f"[BrainPlanner] 规划成功: {action_types}")
            return actions
            
        except Exception as e:
            logger.error(f"[BrainPlanner] 规划失败: {e}", exc_info=True)
            return [self._create_fallback_action()]
    
    def _build_planner_prompt(
        self,
        chat_context: str,
        bot_name: str,
        time_info: Optional[str],
        actions_history: Optional[str]
    ) -> str:
        """Build planner prompt in ReAct format."""
        time_block = ""
        if time_info:
            time_block = f"**当前时间**\n{time_info}\n\n"
        
        name_block = f"**你的身份**\n你的名字是{bot_name}\n\n"
        
        chat_desc = "你正在qq群里聊天"
        
        actions_block = ""
        if actions_history:
            actions_block = f"**之前的动作**\n{actions_history}\n\n"
        else:
            actions_block = "**之前的动作**\n暂无\n\n"
        
        prompt = f"""{time_block}{name_block}{chat_desc}，以下是具体的聊天内容

**聊天内容**
{chat_context}

{actions_block}**可用的action**

reply
动作描述：
进行回复，你可以自然的顺着正在进行的聊天内容进行回复或自然的提出一个问题
{{
    "action": "reply",
    "target_message_id":"想要回复的消息id (格式: m数字)",
    "reason":"回复的原因"
}}

wait
动作描述：
暂时不再发言，等待指定时间。适用于以下情况：
- 你已经表达清楚一轮，想给对方留出空间
- 你感觉对方的话还没说完，或者自己刚刚发了好几条连续消息
- 你想要等待一定时间来让对方把话说完，或者等待对方反应
- 你想保持安静，专注"听"而不是马上回复
- 群里其他人正在对话，你没必要插嘴
- 消息内容不需要你回复（比如日常闲聊、他人之间的对话等）
请你根据上下文来判断要等待多久，请你灵活判断：
- 如果你们交流间隔时间很短，聊的很频繁，不宜等待太久
- 如果你们交流间隔时间很长，聊的很少，可以等待较长时间
{{
    "action": "wait",
    "target_message_id":"想要作为这次等待依据的消息id（通常是对方的最新消息）",
    "wait_seconds": 等待的秒数（必填，例如：5 表示等待5秒）,
    "reason":"选择等待的原因"
}}

complete_talk
动作描述：
当前聊天暂时结束了，对方离开，没有更多话题了
你可以使用该动作来暂时休息，等待对方有新发言再继续：
- 多次wait之后，对方迟迟不回复消息才用
- 如果对方只是短暂不回复，应该使用wait而不是complete_talk
- 聊天内容显示当前聊天已经结束或者没有新内容时候，选择complete_talk
选择此动作后，将不再继续循环思考，直到收到对方的新消息
{{
    "action": "complete_talk",
    "target_message_id":"触发完成对话的消息id（通常是对方的最新消息）",
    "reason":"选择完成对话的原因"
}}

请选择合适的action，并说明触发action的消息id和选择该action的原因。消息id格式:m+数字

**动作选择要求**
请你根据聊天内容,用户的最新消息和以下标准选择合适的动作:
- 仔细判断是否需要回复：不是每条消息都需要回复！
- 如果消息是针对你的、需要你回答的问题、或需要你参与的话题，才选择reply
- 如果是日常闲聊、其他人之间的对话、或不需要你参与的内容，选择wait或complete_talk
- 如果你刚回复过，应该给对方留出反应时间，选择wait
- 如果需要等待对方回复，使用wait动作
- 如果聊天已经结束，使用complete_talk动作
- 可以选择多个动作，但要合理

请选择所有符合使用要求的action，先输出你的选择思考理由（简短，不要分点），再输出你选择的action。
动作用json格式输出，每个json都要单独用```json包裹:

**示例**
// 理由文本
```json
{{
    "action":"reply",
    "target_message_id":"m5",
    "reason":"用户询问了一个问题，需要回答"
}}
```
```json
{{
    "action":"wait",
    "target_message_id":"m5",
    "wait_seconds": 3,
    "reason":"给对方留出时间思考"
}}
```

现在请输出你的思考和选择：
"""
        return prompt
    
    def _parse_actions_response(
        self,
        response_text: str,
        messages: List[Dict[str, Any]]
    ) -> List[ActionPlan]:
        """Parse actions from LLM response."""
        actions = []
        
        try:
            # Extract reasoning (text before first JSON)
            reasoning_match = re.search(r'^(.*?)```json', response_text, re.DOTALL)
            overall_reasoning = ""
            if reasoning_match:
                overall_reasoning = reasoning_match.group(1).strip()
                # Remove comment markers
                overall_reasoning = re.sub(r'^//\s*', '', overall_reasoning, flags=re.MULTILINE)
                overall_reasoning = overall_reasoning.strip()
                if overall_reasoning:
                    logger.info(f"[BrainPlanner] LLM 思考: {overall_reasoning[:60]}...")
            
            # Extract all JSON blocks
            json_blocks = re.findall(r'```json\s*(\{[\s\S]*?\})\s*```', response_text)
            
            if not json_blocks:
                logger.warning("[BrainPlanner] 响应中未找到 JSON 块")
                return []
            
            # Parse each JSON block
            for json_str in json_blocks:
                try:
                    data = json.loads(json_str)
                except json.JSONDecodeError:
                    try:
                        data = json.loads(repair_json(json_str))
                    except Exception as e:
                        logger.warning(f"Failed to parse JSON block: {e}")
                        continue
                
                # Extract action info
                action_type = data.get('action', 'complete_talk')
                reason = data.get('reason', overall_reasoning)
                target_msg_id = data.get('target_message_id')
                
                # Find target message
                target_msg = None
                if target_msg_id:
                    for msg in messages:
                        if msg.get('message_id') == target_msg_id:
                            target_msg = msg
                            break
                
                # If no target message found, use last message
                if not target_msg and messages:
                    target_msg = messages[-1]
                    logger.debug(f"Target message {target_msg_id} not found, using last message")
                
                # Extract action-specific data
                action_data = {}
                if action_type == 'wait':
                    wait_seconds = data.get('wait_seconds', 5)
                    action_data['wait_seconds'] = wait_seconds
                
                # Create action plan
                action = ActionPlan(
                    action_type=action_type,
                    reasoning=reason,
                    target_message_id=target_msg_id,
                    target_message=target_msg,
                    action_data=action_data
                )
                
                actions.append(action)
            
            return actions
            
        except Exception as e:
            logger.error(f"Failed to parse actions response: {e}", exc_info=True)
            return []
    
    def _create_fallback_action(self) -> ActionPlan:
        """Create fallback action when planning fails."""
        return ActionPlan(
            action_type='complete_talk',
            reasoning='规划失败，暂停思考等待新消息',
            target_message_id=None,
            target_message=None,
            action_data={}
        )
    
    def get_plan_history(self, limit: int = 5) -> List[Tuple[float, List[ActionPlan]]]:
        """Get recent plan history.
        
        Args:
            limit: Maximum number of plans to return
            
        Returns:
            List of (timestamp, actions) tuples
        """
        return self._plan_history[-limit:]
    
    def format_actions_history(self, limit: int = 3) -> str:
        """Format recent actions history for prompt.
        
        Args:
            limit: Number of recent plans to include
            
        Returns:
            Formatted actions history string
        """
        recent_plans = self.get_plan_history(limit)
        
        if not recent_plans:
            return "暂无"
        
        lines = []
        for timestamp, actions in recent_plans:
            time_str = time.strftime('%H:%M:%S', time.localtime(timestamp))
            for action in actions:
                lines.append(f"[{time_str}] {action.action_type}: {action.reasoning}")
        
        return "\n".join(lines)


# Global brain planner instance
_brain_planner_instance: Optional[BrainPlanner] = None


def get_brain_planner() -> BrainPlanner:
    """Get or create global brain planner instance."""
    global _brain_planner_instance
    if _brain_planner_instance is None:
        _brain_planner_instance = BrainPlanner()
    return _brain_planner_instance

