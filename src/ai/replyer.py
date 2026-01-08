"""Replyer - reply generation with multi-layer context integration.

Inspired by RuaBot's Replyer system, this module:
1. Builds comprehensive prompts with multiple information layers
2. Integrates expressions, jargons, memory, and knowledge
3. Generates natural and context-aware replies
4. Supports dynamic prompt construction
"""

import asyncio
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime

from ..core.logger import get_logger
from .llm_client import LLMClient
from .expression_learner import get_expression_learner
from .expression_selector import get_expression_selector
from .jargon_miner import get_jargon_miner
from .ai_database import get_ai_database
from .sticker_manager import get_sticker_manager
from .knowledge import get_kg_manager
from .heartflow_enhanced import get_heartflow_enhanced
from .learning_config import get_learning_config
from .person_profiler import get_person_profiler

logger = get_logger(__name__)


class Replyer:
    """Reply generator with multi-layer context integration."""
    
    def __init__(self):
        """Initialize replyer."""
        self.ai_db = get_ai_database()
        self.expression_learner = get_expression_learner()
        self.expression_selector = get_expression_selector()
        self.jargon_miner = get_jargon_miner()
        self.sticker_manager = get_sticker_manager()
        self.kg_manager = get_kg_manager()
        self.heartflow = get_heartflow_enhanced()
        self.learning_config = get_learning_config()
        self.person_profiler = get_person_profiler()
    
    async def generate_reply(
        self,
        chat_id: str,
        chat_context: str,
        messages: List[Dict[str, Any]],
        llm_client: LLMClient,
        target_message: Optional[Dict[str, Any]] = None,
        reply_reason: Optional[str] = None,
        bot_name: str = "AI助手",
        system_prompt: Optional[str] = None,
        think_level: int = 1,
        enable_expression: bool = True,
        enable_jargon: bool = True,
        enable_learning: bool = True,
        tools: Optional[List[Dict[str, Any]]] = None,
        stream: bool = False,
        image_urls: Optional[List[str]] = None,
        supports_vision: bool = False
    ) -> Tuple[str, Dict[str, Any]]:
        """Generate reply with comprehensive context.
        
        Args:
            chat_id: Chat ID
            chat_context: Formatted chat context
            messages: List of message dicts
            llm_client: LLM client
            target_message: Target message to reply to
            reply_reason: Planner's reasoning
            bot_name: Bot's name
            system_prompt: System prompt
            think_level: Thinking level (0=simple, 1=advanced)
            enable_expression: Enable expression learning/selection
            enable_jargon: Enable jargon explanation
            enable_learning: Enable learning from messages
            tools: Optional list of tools for LLM to use
            stream: Enable streaming response
            
        Returns:
            Tuple of (reply_text, metadata_dict)
        """
        try:
            logger.info(f"[Replyer] 生成回复 (think_level={think_level}, tools={len(tools) if tools else 0})")
            
            # Step 1: Learn from messages (if enabled)
            if enable_learning and messages:
                # Trigger learning asynchronously (don't wait for it)
                asyncio.create_task(self._learn_from_messages(
                    chat_id=chat_id,
                    messages=messages,
                    llm_client=llm_client,
                    bot_name=bot_name
                ))
            
            # Step 2: Build prompt layers in parallel
            prompt_layers = await self._build_prompt_layers(
                chat_id=chat_id,
                chat_context=chat_context,
                messages=messages,
                target_message=target_message,
                reply_reason=reply_reason,
                bot_name=bot_name,
                llm_client=llm_client,
                think_level=think_level,
                enable_expression=enable_expression,
                enable_jargon=enable_jargon
            )
            
            # Step 3: Construct final prompt
            final_prompt = self._construct_final_prompt(
                prompt_layers=prompt_layers,
                chat_context=chat_context,
                target_message=target_message,
                reply_reason=reply_reason,
                bot_name=bot_name,
                system_prompt=system_prompt
            )
            logger.info(f"[Replyer] 调用 LLM (prompt: {len(final_prompt)} 字符)")
            
            # Initialize metadata dict first
            metadata = {
                'think_level': think_level,
                'expression_used': prompt_layers.get('expression_habits', '') != '',
                'jargon_used': prompt_layers.get('jargon_explanation', '') != '',
                'reply_reason': reply_reason,
                'target_message_id': target_message.get('message_id') if target_message else None,
                'stream': stream
            }
            
            # Step 4: Generate reply
            # Build system prompt with tool instructions if tools are available
            sys_prompt = system_prompt or f"你是{bot_name}，一个友好、自然的AI助手。"
            if tools:
                sys_prompt += (
                    "\n\n[重要] 工具使用规则："
                    "\n1. 正常对话回复时，直接返回文本内容即可，不要使用 send_group_message 或 send_private_message 工具。"
                    "\n2. 只有在需要@用户、回复特定消息、或跨群发送时，才使用消息发送工具。"
                    "\n3. 不要在回复文本中包含工具调用的XML格式（如 <arg_key>、<arg_value> 等），这些是系统内部格式。"
                    "\n4. 如果需要使用工具，使用标准的 tool_calls 格式，不要在文本中描述工具调用。"
                )
            
            # Build user message with images if vision model
            user_message_content = []
            if image_urls and supports_vision:
                # Add images first
                for img_url in image_urls:
                    user_message_content.append({
                        'type': 'image_url',
                        'image_url': {'url': img_url}
                    })
                # Then add text
                user_message_content.append({
                    'type': 'text',
                    'text': final_prompt
                })
            else:
                # Text only
                user_message_content = final_prompt
            
            response = await llm_client.chat_completion(
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_message_content}
                ],
                temperature=0.9,
                max_tokens=800,
                tools=tools,  # Pass tools to LLM
                stream=stream  # Support streaming
            )
            
            # Handle response based on stream mode
            if stream:
                # For streaming mode, return generator
                reply_text = response  # This is an async generator
            else:
                # Non-streaming mode
                if isinstance(response, dict):
                    reply_text = response.get("content", "")
                    # Check for tool calls
                    tool_calls = response.get("tool_calls")
                    if tool_calls:
                        logger.info(f"[Replyer] 检测到 {len(tool_calls)} 个工具调用")
                        metadata['tool_calls'] = tool_calls
                else:
                    reply_text = str(response)
                
                # Clean up any tool call XML that might have leaked into the text
                if reply_text and isinstance(reply_text, str):
                    reply_text = self._clean_tool_call_xml(reply_text)
                
                if not reply_text:
                    logger.warning("[Replyer] LLM 返回空回复")
                    reply_text = "..."
                else:
                    logger.info(f"[Replyer] 回复生成: {reply_text[:60]}...")
            
            # Step 5: Save message record
            if enable_learning:
                asyncio.create_task(self._save_bot_message(
                    chat_id=chat_id,
                    message_text=reply_text if isinstance(reply_text, str) else "[streaming]",
                    bot_name=bot_name
                ))
            
            return reply_text, metadata
            
        except Exception as e:
            logger.error(f"[Replyer] 生成回复失败: {e}", exc_info=True)
            return "抱歉，我遇到了一些问题...", {'error': str(e)}
    
    def _clean_tool_call_xml(self, text: str) -> str:
        """Remove any tool call XML that leaked into the response text."""
        import re
        
        # Pattern to match tool call XML like:
        # send_group_message\n<arg_key>...</arg_key>\n<arg_value>...</arg_value>
        # or just the tool name followed by XML tags
        
        # Remove tool call function names followed by XML
        text = re.sub(r'\n?(send_group_message|send_private_message|text_to_speech|set_group_ban|[a-z_]+_[a-z_]+)\s*\n?<arg_', '\n', text, flags=re.IGNORECASE)
        
        # Remove all <arg_key> and <arg_value> tags and their content
        text = re.sub(r'<arg_key>.*?</arg_key>', '', text, flags=re.DOTALL)
        text = re.sub(r'<arg_value>.*?</arg_value>', '', text, flags=re.DOTALL)
        
        # Remove any remaining XML-like tags that might be tool-related
        text = re.sub(r'</?arg[^>]*>', '', text)
        
        # Clean up multiple newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text.strip()
    
    async def _build_prompt_layers(
        self,
        chat_id: str,
        chat_context: str,
        messages: List[Dict[str, Any]],
        target_message: Optional[Dict[str, Any]],
        reply_reason: Optional[str],
        bot_name: str,
        llm_client: LLMClient,
        think_level: int,
        enable_expression: bool,
        enable_jargon: bool
    ) -> Dict[str, str]:
        """Build prompt layers in parallel.
        
        Returns:
            Dictionary with different prompt layers
        """
        # Build all layers in parallel
        tasks = []
        layer_names = []
        
        # Layer 1: Expression habits
        if enable_expression:
            tasks.append(self._build_expression_layer(
                chat_id=chat_id,
                chat_context=chat_context,
                reply_reason=reply_reason,
                target_message=target_message,
                llm_client=llm_client,
                think_level=think_level
            ))
            layer_names.append('expression_habits')
        
        # Layer 2: Jargon explanation
        if enable_jargon and target_message:
            target_text = target_message.get('content', '')
            tasks.append(self.jargon_miner.get_jargon_explanations(
                chat_id=chat_id,
                current_message=target_text
            ))
            layer_names.append('jargon_explanation')
        
        # Execute all tasks in parallel
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Build layers dict
            layers = {}
            for name, result in zip(layer_names, results):
                if isinstance(result, Exception):
                    logger.error(f"Failed to build layer {name}: {result}")
                    layers[name] = ""
                else:
                    layers[name] = result or ""
            
            return layers
        
        return {}
    
    async def _build_expression_layer(
        self,
        chat_id: str,
        chat_context: str,
        reply_reason: Optional[str],
        target_message: Optional[Dict[str, Any]],
        llm_client: LLMClient,
        think_level: int
    ) -> str:
        """Build expression habits layer."""
        try:
            # Select appropriate expressions
            target_text = target_message.get('content', '') if target_message else None
            
            expressions = await self.expression_selector.select_expressions(
                chat_id=chat_id,
                chat_context=chat_context,
                reply_reason=reply_reason,
                target_message=target_text,
                llm_client=llm_client,
                max_count=8,
                think_level=think_level
            )
            
            if not expressions:
                return ""
            
            # Format for prompt
            return await self.expression_selector.format_expressions_for_prompt(expressions)
            
        except Exception as e:
            logger.error(f"Failed to build expression layer: {e}", exc_info=True)
            return ""
    
    def _construct_final_prompt(
        self,
        prompt_layers: Dict[str, str],
        chat_context: str,
        target_message: Optional[Dict[str, Any]],
        reply_reason: Optional[str],
        bot_name: str,
        system_prompt: Optional[str]
    ) -> str:
        """Construct final prompt from all layers."""
        sections = []
        
        # Layer 1: Jargon explanation (if available)
        if jargon_layer := prompt_layers.get('jargon_explanation', ''):
            sections.append(jargon_layer)
            sections.append("")
        
        # Layer 2: Expression habits (if available)
        if expr_layer := prompt_layers.get('expression_habits', ''):
            sections.append(expr_layer)
            sections.append("")
        
        # Layer 3: Chat context
        sections.append("你正在qq群里聊天，下面是群里正在聊的内容：")
        sections.append(chat_context)
        sections.append("")
        
        # Layer 4: Target message and reasoning
        if target_message:
            target_text = target_message.get('content', '')
            sender = target_message.get('user_name', target_message.get('user_nickname', '用户'))
            sections.append(f"现在{sender}说的：{target_text}，引起了你的注意")
        
        if reply_reason:
            sections.append(f"你的想法是：{reply_reason}")
        
        sections.append("")
        sections.append("现在，你说：")
        
        return "\n".join(sections)
    
    async def _learn_from_messages(
        self,
        chat_id: str,
        messages: List[Dict[str, Any]],
        llm_client: LLMClient,
        bot_name: str
    ):
        """Learn from messages asynchronously - Complete integration of all learning features."""
        try:
            # Get learning configuration
            # Determine config_type and target_id from chat_id
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
            
            # 1. Learn expressions (if enabled)
            if self.learning_config.is_feature_enabled('expression_learning', learning_config):
                await self.expression_learner.learn_from_messages(
                    chat_id=chat_id,
                    messages=messages,
                    llm_client=llm_client,
                    bot_name=bot_name
                )
            
            # 2. Extract jargons (if enabled)
            if self.learning_config.is_feature_enabled('jargon_learning', learning_config):
                await self.jargon_miner.extract_jargons_from_messages(
                    chat_id=chat_id,
                    messages=messages,
                    llm_client=llm_client,
                    bot_name=bot_name
                )
            
            # 3. Learn stickers from messages (if enabled and images present)
            if self.learning_config.is_feature_enabled('sticker_learning', learning_config):
                await self.sticker_manager.process_messages_for_learning(
                    chat_id=chat_id,
                    messages=messages,
                    llm_client=llm_client
                )
            
            # 4. Extract knowledge from messages (if enabled)
            if self.learning_config.is_feature_enabled('knowledge_graph', learning_config):
                kg_config = self.learning_config.get_feature_config('knowledge_graph', learning_config)
                max_triples = kg_config.get('max_triples_per_message', 5)
                
                for msg in messages:
                    if msg.get('is_bot_message', False):
                        continue  # Skip bot messages for knowledge extraction
                    
                    content = msg.get('content', '')
                    if content and len(content.strip()) > 10:  # Only process meaningful messages
                        user_id = msg.get('user_id', 'unknown')
                        await self.kg_manager.process_message(
                            text=content,
                            chat_id=chat_id,
                            llm_client=llm_client,
                            user_id=user_id
                        )
            
            # 5. User profiling (if enabled) - analyze users from messages
            if self.learning_config.is_feature_enabled('person_profiling', learning_config):
                # Extract unique user IDs from messages
                user_ids = set()
                for msg in messages:
                    if not msg.get('is_bot_message', False):
                        user_id = msg.get('user_id')
                        if user_id:
                            user_ids.add(user_id)
                
                # Analyze each user (in background, don't wait)
                for user_id in user_ids:
                    asyncio.create_task(self.person_profiler.analyze_person(
                        user_id=user_id,
                        chat_id=chat_id,
                        llm_client=llm_client,
                        platform="qq"  # Default platform, can be extracted from chat_id if needed
                    ))
            
            logger.info(f"[Replyer] 学习完成: {chat_id} (根据配置启用相应功能)")
            
        except Exception as e:
            logger.error(f"Failed to learn from messages: {e}", exc_info=True)
    
    async def _save_bot_message(
        self,
        chat_id: str,
        message_text: str,
        bot_name: str
    ):
        """Save bot's message to database."""
        try:
            import time
            await self.ai_db.save_message_record(
                chat_id=chat_id,
                user_id="bot",
                plain_text=message_text,
                user_nickname=bot_name,
                time=time.time(),
                is_bot_message=True
            )
        except Exception as e:
            logger.error(f"Failed to save bot message: {e}", exc_info=True)


# Global replyer instance
_replyer_instance: Optional[Replyer] = None


def get_replyer() -> Replyer:
    """Get or create global replyer instance."""
    global _replyer_instance
    if _replyer_instance is None:
        _replyer_instance = Replyer()
    return _replyer_instance

