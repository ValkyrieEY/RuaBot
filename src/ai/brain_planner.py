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
        from .prompts import build_planner_prompt
        return build_planner_prompt(chat_context, bot_name, time_info, actions_history)
    
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

