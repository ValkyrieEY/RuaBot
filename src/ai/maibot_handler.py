"""RuaBot-style AI Handler - Complete integration of RuaBot features.

This module integrates all RuaBot-style features:
1. Expression learning and selection
2. Jargon mining and explanation
3. Brain planning (ReAct pattern)
4. Reply generation with multi-layer context
5. Message recording and memory retrieval
"""

import asyncio
import time
from typing import Optional, Dict, Any, List, Tuple

from ..core.logger import get_logger
from .llm_client import LLMClient
from .brain_planner import get_brain_planner, ActionPlan
from .replyer import get_replyer
from .message_recorder import get_message_recorder
from .memory_retrieval import get_memory_retrieval
from .expression_learner import get_expression_learner
from .jargon_miner import get_jargon_miner
from .chat_summarizer import get_chat_summarizer
from .person_profiler import get_person_profiler
from .group_profiler import get_group_profiler
from .heartflow_enhanced import get_heartflow_enhanced
from .learning_config import get_learning_config

logger = get_logger(__name__)


class RuaBotHandler:
    """RuaBot-style AI handler with complete feature integration."""
    
    def __init__(self):
        """Initialize RuaBot handler."""
        self.brain_planner = get_brain_planner()
        self.replyer = get_replyer()
        self.message_recorder = get_message_recorder()
        self.memory_retrieval = get_memory_retrieval()
        self.expression_learner = get_expression_learner()
        self.jargon_miner = get_jargon_miner()
        self.chat_summarizer = get_chat_summarizer()
        self.person_profiler = get_person_profiler()
        self.group_profiler = get_group_profiler()
        self.heartflow = get_heartflow_enhanced()
        self.learning_config = get_learning_config()
        
        # Thinking loop state
        self._thinking_loops: Dict[str, bool] = {}  # {chat_id: is_thinking}
        self._loop_tasks: Dict[str, asyncio.Task] = {}  # {chat_id: task}
        
        # Frequency control for group chats
        self._last_reply_time: Dict[str, float] = {}  # {chat_id: timestamp}
        self._reply_count: Dict[str, int] = {}  # {chat_id: count}
        self._message_count: Dict[str, int] = {}  # {chat_id: count}
    
    async def handle_message(
        self,
        chat_id: str,
        message: Dict[str, Any],
        llm_client: LLMClient,
        bot_name: str = "AI助手",
        system_prompt: Optional[str] = None,
        enable_brain_mode: bool = True,
        enable_learning: bool = True,
        think_level: int = 1,
        tools: Optional[List[Dict[str, Any]]] = None,
        stream: bool = False,
        supports_vision: bool = False
    ) -> Optional[Any]:
        """Handle incoming message with RuaBot-style processing.
        
        Args:
            chat_id: Chat ID (format: "group:群号" or "user:QQ号")
            message: Message dict with keys: message_id, user_id, user_name, content, time
            llm_client: LLM client
            bot_name: Bot's name
            system_prompt: System prompt
            enable_brain_mode: Enable brain planning mode (ReAct)
            enable_learning: Enable learning from messages
            think_level: Thinking level (0=simple, 1=advanced)
            tools: Optional list of tools for LLM
            stream: Enable streaming response
            
        Returns:
            Reply text or streaming generator or None
        """
        try:
            logger.info(f"[RuaBot] 开始处理 {chat_id} 的消息: {message.get('content', '')[:30]}...")
            
            # Step 1: Record incoming message
            await self._record_message(chat_id, message, bot_name)
            
            # Step 2: Get recent messages for context
            messages = await self.message_recorder.get_recent_messages(
                chat_id=chat_id,
                limit=30,
                exclude_bot=False
            )
            
            if not messages:
                logger.warning(f"[RuaBot] 未找到历史消息")
                return None
            
            logger.info(f"[RuaBot] 获取到 {len(messages)} 条历史消息")
            
            # Step 3: Build chat context
            chat_context = self._build_chat_context(messages)
            
            # Step 4: Frequency control for group chats
            # Count incoming messages
            self._message_count[chat_id] = self._message_count.get(chat_id, 0) + 1
            
            # Calculate reply frequency (percentage of messages we replied to)
            reply_count = self._reply_count.get(chat_id, 0)
            message_count = self._message_count.get(chat_id, 1)
            reply_frequency = reply_count / message_count if message_count > 0 else 0
            
            logger.info(f"[RuaBot] 频率检查: {reply_count}/{message_count} ({reply_frequency:.1%})")
            
            # Check if we replied too frequently (more than 30% of messages)
            if reply_frequency > 0.3 and reply_count > 2:
                logger.info(f"[RuaBot] 回复频率过高 ({reply_frequency:.1%})，跳过")
                return None
            
            # Check if we replied too recently (within 10 seconds for group chats)
            if chat_id.startswith("group:"):
                last_reply = self._last_reply_time.get(chat_id, 0)
                time_since_last = time.time() - last_reply
                if time_since_last < 10:
                    logger.info(f"[RuaBot] 回复间隔过短 ({time_since_last:.1f}s)，跳过")
                    return None
            
            # Step 5: Brain planning (if enabled)
            if enable_brain_mode:
                logger.info("[RuaBot] 调用 Brain Planner 规划动作...")
                
                actions = await self.brain_planner.plan_actions(
                    chat_context=chat_context,
                    messages=messages,
                    llm_client=llm_client,
                    bot_name=bot_name,
                    time_info=self._get_time_info(),
                    actions_history=self.brain_planner.format_actions_history()
                )
                
                if actions:
                    action_summary = ", ".join([f"{a.action_type}({a.reasoning[:20]}...)" for a in actions])
                    logger.info(f"[RuaBot] 规划完成: {len(actions)} 个动作 - {action_summary}")
                
                # Process actions
                reply_text = await self._process_actions(
                    actions=actions,
                    chat_id=chat_id,
                    chat_context=chat_context,
                    messages=messages,
                    message=message,
                    llm_client=llm_client,
                    bot_name=bot_name,
                    system_prompt=system_prompt,
                    think_level=think_level,
                    enable_learning=enable_learning,
                    tools=tools,
                    stream=stream,
                    supports_vision=supports_vision
                )
                
                # Update reply tracking
                if reply_text:
                    self._last_reply_time[chat_id] = time.time()
                    self._reply_count[chat_id] = self._reply_count.get(chat_id, 0) + 1
                    new_frequency = self._reply_count[chat_id]/self._message_count[chat_id]
                    logger.info(f"[RuaBot] 已回复，新频率: {self._reply_count[chat_id]}/{self._message_count[chat_id]} ({new_frequency:.1%})")
                    
                    # Record reply to HeartFlow
                    self.heartflow.record_reply(chat_id)
                else:
                    logger.info("[RuaBot] 选择不回复")
                
                return reply_text
            else:
                # Direct reply mode (no planning)
                logger.info("[RuaBot] 直接回复模式（无规划器）")
                
                # Extract image URLs from message if available
                image_urls = message.get('image_urls') if message else None
                
                reply_text, _ = await self.replyer.generate_reply(
                    chat_id=chat_id,
                    chat_context=chat_context,
                    messages=messages,
                    llm_client=llm_client,
                    target_message=messages[-1] if messages else None,
                    bot_name=bot_name,
                    system_prompt=system_prompt,
                    think_level=think_level,
                    enable_learning=enable_learning,
                    tools=tools,
                    stream=stream,
                    image_urls=image_urls,
                    supports_vision=supports_vision
                )
                
                # Update reply tracking
                if reply_text:
                    self._last_reply_time[chat_id] = time.time()
                    self._reply_count[chat_id] = self._reply_count.get(chat_id, 0) + 1
                    logger.info(f"[RuaBot] 回复已生成: {str(reply_text)[:50]}...")
                    
                    # Record reply to HeartFlow
                    self.heartflow.record_reply(chat_id)
                
                # Trigger background analysis tasks (don't wait for them)
                if enable_learning and reply_text:
                    asyncio.create_task(self._run_background_analysis(
                        chat_id=chat_id,
                        message=message,
                        llm_client=llm_client
                    ))
                
                return reply_text
            
        except Exception as e:
            logger.error(f"[RuaBot] 处理失败: {e}", exc_info=True)
            return None
    
    async def _run_background_analysis(
        self,
        chat_id: str,
        message: Dict[str, Any],
        llm_client: LLMClient
    ):
        """Run background analysis tasks (summarization, profiling, etc.)."""
        try:
            # Chat summarization (every 30 minutes or 100 messages)
            await self.chat_summarizer.check_and_summarize(
                chat_id=chat_id,
                llm_client=llm_client
            )
            
            # Person profiling (for group chats)
            if chat_id.startswith("group:"):
                user_id = message.get('user_id')
                if user_id:
                    await self.person_profiler.analyze_person(
                        user_id=user_id,
                        chat_id=chat_id,
                        llm_client=llm_client
                    )
                
                # Group profiling
                group_id = chat_id.split(":", 1)[1]
                await self.group_profiler.analyze_group(
                    group_id=group_id,
                    chat_id=chat_id,
                    llm_client=llm_client
                )
        
        except Exception as e:
            logger.error(f"Background analysis failed: {e}", exc_info=True)
    
    async def _record_message(
        self,
        chat_id: str,
        message: Dict[str, Any],
        bot_name: str
    ):
        """Record message to database and update HeartFlow."""
        try:
            # Extract group_id if chat_id is group format
            group_id = None
            is_group = chat_id.startswith("group:")
            if is_group:
                group_id = chat_id.split(":", 1)[1]
            
            user_id = message.get('user_id', 'unknown')
            content = message.get('content', '')
            is_bot = message.get('user_name') == bot_name
            
            # Record to database
            await self.message_recorder.record_message(
                message_id=message.get('message_id'),
                chat_id=chat_id,
                user_id=user_id,
                plain_text=content,
                user_nickname=message.get('user_name'),
                group_id=group_id,
                is_bot_message=is_bot,
                timestamp=message.get('time', time.time())
            )
            
            # Update HeartFlow (if enabled) - check asynchronously
            asyncio.create_task(self._update_heartflow(chat_id, str(user_id), content, is_bot))
            
        except Exception as e:
            logger.error(f"Failed to record message: {e}", exc_info=True)
    
    def _build_chat_context(self, messages: List[Dict[str, Any]]) -> str:
        """Build formatted chat context with message IDs."""
        lines = []
        for i, msg in enumerate(messages):
            msg_id = f"m{i+1}"
            user_name = msg.get('user_name', 'User')
            content = msg.get('content', '')
            time_str = self._format_time(msg.get('time', time.time()))
            
            lines.append(f"[{msg_id}] [{time_str}] {user_name}: {content}")
            
            # Add message_id to message dict for later reference
            msg['message_id'] = msg_id
        
        return "\n".join(lines)
    
    def _format_time(self, timestamp: float) -> str:
        """Format timestamp to HH:MM:SS."""
        return time.strftime('%H:%M:%S', time.localtime(timestamp))
    
    def _get_time_info(self) -> str:
        """Get current time information."""
        now = time.time()
        return time.strftime('%Y年%m月%d日 %H:%M:%S', time.localtime(now))
    
    async def _process_actions(
        self,
        actions: List[ActionPlan],
        chat_id: str,
        chat_context: str,
        messages: List[Dict[str, Any]],
        message: Dict[str, Any],
        llm_client: LLMClient,
        bot_name: str,
        system_prompt: Optional[str],
        think_level: int,
        enable_learning: bool,
        tools: Optional[List[Dict[str, Any]]] = None,
        stream: bool = False,
        supports_vision: bool = False
    ) -> Optional[str]:
        """Process planned actions.
        
        Returns:
            Reply text if reply action was executed, None otherwise
        """
        reply_text = None
        
        for action in actions:
            action_type = action.action_type
            
            if action_type == 'reply':
                logger.info(f"[RuaBot] 执行 reply: {action.reasoning[:40]}...")
                
                # Extract image URLs from message if available
                image_urls = message.get('image_urls') if message else None
                
                # Generate reply
                reply_text, metadata = await self.replyer.generate_reply(
                    chat_id=chat_id,
                    chat_context=chat_context,
                    messages=messages,
                    llm_client=llm_client,
                    target_message=action.target_message,
                    reply_reason=action.reasoning,
                    bot_name=bot_name,
                    system_prompt=system_prompt,
                    think_level=think_level,
                    enable_learning=enable_learning,
                    tools=tools,
                    stream=stream,
                    image_urls=image_urls,
                    supports_vision=supports_vision
                )
                
                # Store tool calls if any
                if 'tool_calls' in metadata:
                    action.action_data['tool_calls'] = metadata['tool_calls']
                    logger.info(f"[RuaBot] 使用了 {len(metadata['tool_calls'])} 个工具")
                
                if reply_text and not stream:
                    logger.info(f"[RuaBot] 回复生成: {str(reply_text)[:60]}...")
            
            elif action_type == 'wait':
                wait_seconds = action.action_data.get('wait_seconds', 5)
                logger.info(f"[RuaBot] 执行 wait: 等待 {wait_seconds}s - {action.reasoning[:40]}...")
            
            elif action_type == 'complete_talk':
                logger.info(f"[RuaBot] 执行 complete_talk: {action.reasoning[:40]}...")
                break
            
            else:
                logger.warning(f"[RuaBot] 未知动作: {action_type}")
        
        return reply_text
    
    async def start_thinking_loop(
        self,
        chat_id: str,
        llm_client: LLMClient,
        bot_name: str = "AI助手",
        system_prompt: Optional[str] = None,
        think_level: int = 1,
        enable_learning: bool = True
    ):
        """Start continuous thinking loop for a chat (like RuaBot's BrainChatting).
        
        Args:
            chat_id: Chat ID
            llm_client: LLM client
            bot_name: Bot's name
            system_prompt: System prompt
            think_level: Thinking level
            enable_learning: Enable learning
        """
        if chat_id in self._thinking_loops and self._thinking_loops[chat_id]:
            logger.warning(f"Thinking loop already running for {chat_id}")
            return
        
        self._thinking_loops[chat_id] = True
        
        async def thinking_loop():
            """Continuous thinking loop."""
            logger.info(f"Starting thinking loop for {chat_id}")
            
            while self._thinking_loops.get(chat_id, False):
                try:
                    # Get recent messages
                    messages = await self.message_recorder.get_recent_messages(
                        chat_id=chat_id,
                        limit=30,
                        exclude_bot=False
                    )
                    
                    if not messages:
                        await asyncio.sleep(5)
                        continue
                    
                    # Build context
                    chat_context = self._build_chat_context(messages)
                    
                    # Plan actions
                    actions = await self.brain_planner.plan_actions(
                        chat_context=chat_context,
                        messages=messages,
                        llm_client=llm_client,
                        bot_name=bot_name,
                        time_info=self._get_time_info(),
                        actions_history=self.brain_planner.format_actions_history()
                    )
                    
                    # Check for complete_talk action
                    should_stop = False
                    for action in actions:
                        if action.action_type == 'complete_talk':
                            should_stop = True
                            logger.info(f"Thinking loop stopped by complete_talk: {action.reasoning}")
                            break
                    
                    if should_stop:
                        break
                    
                    # Process actions
                    await self._process_actions(
                        actions=actions,
                        chat_id=chat_id,
                        chat_context=chat_context,
                        messages=messages,
                        llm_client=llm_client,
                        bot_name=bot_name,
                        system_prompt=system_prompt,
                        think_level=think_level,
                        enable_learning=enable_learning
                    )
                    
                    # Wait before next iteration
                    await asyncio.sleep(3)
                    
                except Exception as e:
                    logger.error(f"Error in thinking loop: {e}", exc_info=True)
                    await asyncio.sleep(5)
            
            logger.info(f"Thinking loop stopped for {chat_id}")
            self._thinking_loops[chat_id] = False
        
        # Start loop as background task
        task = asyncio.create_task(thinking_loop())
        self._loop_tasks[chat_id] = task
    
    async def _update_heartflow(
        self,
        chat_id: str,
        user_id: str,
        content: str,
        is_bot: bool
    ):
        """Update HeartFlow if enabled."""
        try:
            # Get config to check if heartflow is enabled
            if chat_id.startswith("group:"):
                config_type = 'group'
                target_id = chat_id.split(":", 1)[1]
            elif chat_id.startswith("user:"):
                config_type = 'user'
                target_id = chat_id.split(":", 1)[1]
            else:
                config_type = 'global'
                target_id = None
            
            learning_config = await self.learning_config.get_config(config_type, target_id)
            if self.learning_config.is_feature_enabled('heartflow', learning_config):
                self.heartflow.record_message(
                    chat_id=chat_id,
                    user_id=user_id,
                    content=content,
                    is_bot=is_bot
                )
        except Exception as e:
            logger.error(f"Failed to update heartflow: {e}")
    
    async def stop_thinking_loop(self, chat_id: str):
        """Stop thinking loop for a chat.
        
        Args:
            chat_id: Chat ID
        """
        if chat_id in self._thinking_loops:
            self._thinking_loops[chat_id] = False
            
            # Wait for task to complete
            if chat_id in self._loop_tasks:
                task = self._loop_tasks[chat_id]
                try:
                    await asyncio.wait_for(task, timeout=10.0)
                except asyncio.TimeoutError:
                    logger.warning(f"Thinking loop task timeout for {chat_id}, cancelling")
                    task.cancel()
                
                del self._loop_tasks[chat_id]
            
            logger.info(f"Thinking loop stopped for {chat_id}")


# Global RuaBot handler instance
_RuaBot_handler_instance: Optional[RuaBotHandler] = None


def get_RuaBot_handler() -> RuaBotHandler:
    """Get or create global RuaBot handler instance."""
    global _RuaBot_handler_instance
    if _RuaBot_handler_instance is None:
        _RuaBot_handler_instance = RuaBotHandler()
    return _RuaBot_handler_instance

