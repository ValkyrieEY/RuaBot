"""AI message handler for processing messages and generating AI responses."""

import asyncio
import json
import time
import random
import re
from typing import Optional, Dict, Any, List
from datetime import datetime
from ..core.event_bus import get_event_bus
from ..core.logger import get_logger
from ..core.database import get_database_manager
from ..core.app import get_app
from .ai_manager import AIManager
from .model_manager import ModelManager
from .llm_client import LLMClient
from .tools import AITools
from .mcp_manager import MCPManager
from .frequency_control import frequency_control_manager
from .thread_pool import get_thread_pool_manager
from .RuaBot_handler import get_RuaBot_handler
from .init_ai_database import ensure_ai_database_initialized

logger = get_logger(__name__)


class StreamSplitter:
    """Stream splitter for processing streaming responses."""
    
    def __init__(self):
        self.full_content = ""
        self.last_split_time = time.time()
        self.forward_msg_num = 500
        self.enable_forward_msg_num = False
        self.check_forward_msg = False
        self.split_str = "\n\n\n\n"
        self.chunks = 0
        self.buffer = ""
    
    def split_stream(self, response_stream, type='openai'):
        """Split streaming response into chunks."""
        try:
            buffer_threshold = 200 if type == 'openai' else 50
            
            for chunk in response_stream:
                if type == 'openai':
                    if hasattr(chunk, 'choices') and len(chunk.choices) > 0:
                        delta = chunk.choices[0].delta
                        chunk_text = delta.content if hasattr(delta, 'content') else None
                    else:
                        chunk_text = None
                else:
                    chunk_text = chunk.text if hasattr(chunk, 'text') else None
                
                if chunk_text is None:
                    continue
                
                self.full_content += chunk_text
                self.buffer += chunk_text
                self.chunks += 1
                
                if type == 'openai':
                    if len(self.buffer) < buffer_threshold:
                        continue
                
                if time.time() - self.last_split_time >= 1.5:
                    self.last_split_time = time.time()
                    for r in self.check_and_split():
                        if r != "":
                            yield r, self.enable_forward_msg_num
            
            for r in self.check_and_split(True):
                yield r, self.enable_forward_msg_num
            
            logger.debug(f"FULL_CONTENT: {repr(self.full_content)}")
        except Exception as e:
            logger.error(f"Error in stream splitter: {e}", exc_info=True)
            raise
    
    def check_and_split(self, last_response=False):
        """Check buffer and split if needed."""
        if not self.check_forward_msg:
            if len(self.buffer) > self.forward_msg_num:
                self.enable_forward_msg_num = True
            self.check_forward_msg = True
        
        messages = []
        if self.split_str == "\n\n\n\n":
            for sep in (self.split_str[:i] for i in range(4, -1, -1)):
                if sep in self.buffer:
                    self.split_str = sep
                    break
        
        if self.split_str == "":
            self.split_str = "\n\n\n\n"
            message = self.buffer
        else:
            messages = self.buffer.split(self.split_str)
            
            if not last_response:
                message = messages[0]
            else:
                for m in messages:
                    yield m
                    time.sleep(random.uniform(0.5, 2.0))
                return
            
            if len(messages) == 1:
                self.buffer = messages[0].replace(self.buffer, "")
            else:
                self.buffer = "\n".join(
                    msg + "\n" if self._needs_trailing_newline(msg) else msg
                    for msg in messages[1:-1]
                ) + messages[-1]
        
        if not self.is_balanced(message):
            self.buffer = message + self.buffer
            return
        
        if last_response or self.split_str != "\n\n\n\n":
            yield message
    
    def is_balanced(self, text):
        """Check if text has balanced brackets."""
        brackets = {"(": ")", "[": "]", "{": "}", "「": "」"}
        stack = []
        for char in text:
            if char in brackets:
                stack.append(brackets[char])
            elif stack and char == stack[-1]:
                stack.pop()
        return len(stack) == 0 and not (text.endswith(("\n   -", "（", ":", "：")) or text.startswith((":", "：")))
    
    def _needs_trailing_newline(self, text: str) -> bool:
        """Check if text needs trailing newline."""
        return any([
            text.startswith((' - ', '• ', '* ')),
            text.endswith(('：', ":")),
            re.search(r'\n\s*[-\*•]', text)
        ])


class AIMessageHandler:
    """Handles AI message processing and response generation."""
    
    def __init__(self):
        self.event_bus = get_event_bus()
        self.ai_manager: Optional[AIManager] = None
        self.model_manager: Optional[ModelManager] = None
        self.mcp_manager: Optional[MCPManager] = None
        self._initialized = False
        
        # MaxToken mode state management (per chat stream)
        # Format: {chat_id: {'consecutive_no_reply_count': int, 'last_read_time': float}}
        self._maxtoken_state: Dict[str, Dict[str, Any]] = {}
        
        # Thread pool for blocking operations
        self.thread_pool = None
        
        # RuaBot handler for advanced AI features
        self.RuaBot_handler = None
        self._RuaBot_enabled = False
    
    async def _execute_tool_call(self, tool_name: str, tool_args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a tool call (helper method).
        
        Args:
            tool_name: Name of the tool to call
            tool_args: Arguments for the tool
            context: Optional context information (group_id, user_id, message_type, etc.)
        """
        # Fill in missing required parameters from context
        if context:
            # For send_group_message, fill group_id if missing
            if tool_name == "send_group_message":
                if not tool_args.get("group_id") and context.get("group_id"):
                    tool_args["group_id"] = str(context["group_id"])
                    logger.info(f"Auto-filled group_id from context: {context['group_id']}")
            
            # For send_private_message, fill user_id if missing
            elif tool_name == "send_private_message":
                if not tool_args.get("user_id") and context.get("user_id"):
                    tool_args["user_id"] = str(context["user_id"])
                    logger.info(f"Auto-filled user_id from context: {context['user_id']}")
            
            # For text_to_speech, fill message_type and target_id if missing
            elif tool_name == "text_to_speech":
                if not tool_args.get("message_type") and context.get("message_type"):
                    tool_args["message_type"] = context["message_type"]
                    logger.info(f"Auto-filled message_type from context: {context['message_type']}")
                if not tool_args.get("target_id"):
                    if context.get("message_type") == "group" and context.get("group_id"):
                        tool_args["target_id"] = str(context["group_id"])
                        logger.info(f"Auto-filled target_id (group) from context: {context['group_id']}")
                    elif context.get("message_type") == "private" and context.get("user_id"):
                        tool_args["target_id"] = str(context["user_id"])
                        logger.info(f"Auto-filled target_id (user) from context: {context['user_id']}")
        
        # Check if this is an MCP tool (format: mcp_{server_uuid}_{tool_name})
        if tool_name.startswith('mcp_'):
            # Parse MCP tool name: mcp_{server_uuid}_{tool_name}
            parts = tool_name.split('_', 2)
            if len(parts) >= 3:
                server_uuid = parts[1]
                mcp_tool_name = parts[2]
                
                # Call MCP tool
                try:
                    if self.mcp_manager:
                        mcp_result = await self.mcp_manager.call_tool(
                            server_uuid, mcp_tool_name, tool_args
                        )
                        
                        # Format MCP result for LLM
                        if isinstance(mcp_result, dict):
                            if mcp_result.get('isError'):
                                return {
                                    "success": False,
                                    "error": str(mcp_result.get('content', 'Unknown error'))
                                }
                            else:
                                content = mcp_result.get('content', [])
                                if isinstance(content, list):
                                    content_str = '\n'.join(str(item) for item in content)
                                else:
                                    content_str = str(content)
                                
                                return {
                                    "success": True,
                                    "result": mcp_result,
                                    "message": content_str
                                }
                        else:
                            return {
                                "success": True,
                                "result": mcp_result,
                                "message": str(mcp_result)
                            }
                    else:
                        return {
                            "success": False,
                            "error": "MCP manager not available"
                        }
                except Exception as e:
                    logger.error(f"Error calling MCP tool {mcp_tool_name}: {e}", exc_info=True)
                    return {
                        "success": False,
                        "error": str(e)
                    }
            else:
                return {
                    "success": False,
                    "error": f"Invalid MCP tool name format: {tool_name}"
                }
        else:
            # Call built-in tool with permission checking
            # Extract user info from context for permission check
            user_qq = str(context.get('user_id', '')) if context and context.get('user_id') else None
            chat_type = context.get('message_type', 'unknown') if context else 'unknown'
            chat_id = None
            if context:
                if chat_type == 'group' and context.get('group_id'):
                    chat_id = str(context['group_id'])
                elif chat_type == 'private' and context.get('user_id'):
                    chat_id = str(context['user_id'])
            user_nickname = context.get('user_nickname') if context else None
            
            # Get LLM client for AI approval (try to get from context or create one)
            llm_client = None
            if context and context.get('model_uuid'):
                try:
                    model = await self.model_manager.get_model_with_secret(context['model_uuid'])
                    if model:
                        from .llm_client import LLMClient
                        llm_client = LLMClient(
                            base_url=model.get('base_url', 'https://api.openai.com/v1'),
                            api_key=model.get('api_key', ''),
                            model=model.get('model_name', 'gpt-3.5-turbo')
                        )
                except Exception as e:
                    logger.debug(f"Failed to get LLM client for AI approval: {e}")
            
            return await AITools.call_tool(
                tool_name=tool_name,
                arguments=tool_args,
                user_qq=user_qq,
                chat_type=chat_type,
                chat_id=chat_id,
                user_nickname=user_nickname,
                llm_client=llm_client
            )
    
    async def initialize(self):
        """Initialize the message handler."""
        if self._initialized:
            return
        
        # Initialize AI learning database first
        logger.info("Initializing AI learning database...")
        db_init_success = ensure_ai_database_initialized()
        if db_init_success:
            logger.info("[RuaBot] AI learning database initialized successfully")
            # Initialize RuaBot handler
            try:
                self.RuaBot_handler = get_RuaBot_handler()
                self._RuaBot_enabled = True
                logger.info("[RuaBot] RuaBot handler initialized - Advanced AI features enabled!")
            except Exception as e:
                logger.error(f"Failed to initialize RuaBot handler: {e}", exc_info=True)
                self._RuaBot_enabled = False
        else:
            logger.warning("AI learning database initialization failed - RuaBot features disabled")
            self._RuaBot_enabled = False
        
        from . import ModelManager, AIManager, MCPManager
        self.model_manager = ModelManager()
        self.ai_manager = AIManager(model_manager=self.model_manager)
        self.mcp_manager = MCPManager()
        await self.mcp_manager.initialize()
        
        await self.model_manager.initialize()
        await self.ai_manager.initialize()
        
        # Initialize thread pool for blocking operations
        # Get max_workers from config (default: 5)
        from ..core.config import get_config
        config = get_config()
        max_workers = getattr(config, 'ai_thread_pool_workers', 5)
        self.thread_pool = get_thread_pool_manager(max_workers=max_workers)
        logger.info(f"Thread pool initialized with {max_workers} workers for AI processing")
        
        # Subscribe to message events (subscribe is not async)
        self.event_bus.subscribe("onebot.message", self.handle_message)
        
        self._initialized = True
        logger.info("AIMessageHandler initialized")
    
    def _split_response(self, text: str, max_length: int = 500) -> list[str]:
        """
        Split response text into multiple parts for simulated streaming.
        
        Args:
            text: Full response text
            max_length: Maximum length for each part
            
        Returns:
            List of text parts
        """
        if len(text) <= max_length:
            return [text]
        
        parts = []
        current_part = ""
        
        # Split by paragraphs first (double newline or more)
        paragraphs = re.split(r'\n\n+', text)
        
        for para in paragraphs:
            # If adding this paragraph would exceed max_length, save current part
            if current_part and len(current_part) + len(para) + 2 > max_length:
                parts.append(current_part.strip())
                current_part = para
            else:
                if current_part:
                    current_part += "\n\n" + para
                else:
                    current_part = para
            
            # If current paragraph itself is too long, split by sentences
            if len(current_part) > max_length:
                # Split by sentence endings
                sentences = re.split(r'([。！？\.\!\?]+)', current_part)
                temp_part = ""
                
                for i in range(0, len(sentences), 2):
                    sentence = sentences[i]
                    punctuation = sentences[i+1] if i+1 < len(sentences) else ""
                    full_sentence = sentence + punctuation
                    
                    if temp_part and len(temp_part) + len(full_sentence) > max_length:
                        parts.append(temp_part.strip())
                        temp_part = full_sentence
                    else:
                        temp_part += full_sentence
                
                current_part = temp_part
        
        # Add remaining part
        if current_part.strip():
            parts.append(current_part.strip())
        
        return parts if parts else [text]
    
    async def handle_message(self, event):
        """Handle incoming message event.
        
        Args:
            event: Event object with payload containing OneBot message data
        """
        try:
            # Extract payload from event
            # EventBus passes Event objects with .payload attribute
            if hasattr(event, 'payload'):
                data = event.payload
            elif isinstance(event, dict):
                data = event
            else:
                logger.warning(f"Unexpected event type: {type(event)}")
                return
            
            # Parse message data
            message_type = data.get('message_type')  # 'private' or 'group'
            raw_message = data.get('raw_message', '')
            message = data.get('message', [])  # Message segments array
            user_id = data.get('user_id')
            group_id = data.get('group_id')
            
            # Check if message contains image
            has_image = False
            if isinstance(message, list):
                for seg in message:
                    if isinstance(seg, dict) and seg.get('type') == 'image':
                        has_image = True
                        break
            
            # Also check raw_message for CQ code image format
            if not has_image and raw_message:
                if '[CQ:image' in raw_message:
                    has_image = True
            
            if not raw_message and not has_image:
                return
            
            # Determine target type and ID
            if message_type == 'group':
                config_type = 'group'
                target_id = str(group_id) if group_id else None
            elif message_type == 'private':
                config_type = 'user'
                target_id = str(user_id) if user_id else None
            else:
                return
            
            if not target_id:
                return
            
            # Check if AI is enabled for this target
            is_enabled = await self.ai_manager.is_enabled(config_type, target_id)
            if not is_enabled:
                logger.debug(f"AI disabled for {config_type}:{target_id}")
                return
            
            # Get configuration
            config = await self.ai_manager.get_config(config_type, target_id)
            
            # Check trigger command
            # Get trigger mode and command
            trigger_mode = config.get('config', {}).get('trigger_mode', 'command')  # 'command' or 'maxtoken'
            trigger_command = config.get('config', {}).get('trigger_command', '') or ''
            # Ensure it's a string, not None
            if trigger_command is None:
                trigger_command = ''
            
            logger.debug(f"Trigger mode check: {config_type}:{target_id}, trigger_mode='{trigger_mode}', trigger_command='{trigger_command}', raw_message='{raw_message[:50]}', has_image={has_image}")
            
            # MaxToken mode: all messages are sent to AI, AI decides whether to reply
            if trigger_mode == 'maxtoken':
                # In MaxToken mode, apply RuaBot-style humanization logic
                chat_id = f"{config_type}:{target_id}"
                
                # Check if RuaBot features are enabled
                use_RuaBot = self._RuaBot_enabled and config.get('config', {}).get('enable_RuaBot', True)
                
                if use_RuaBot:
                    logger.info(f"[RuaBot] Using RuaBot handler for {chat_id}")
                    try:
                        # Use RuaBot handler for advanced AI processing
                        # Get LLM model configuration
                        model_uuid = config.get('model_uuid')
                        if not model_uuid:
                            logger.warning("No model configured for RuaBot, skipping")
                            return
                        
                        # Get model with API key (use get_model_with_secret for internal use)
                        model = await self.model_manager.get_model_with_secret(model_uuid)
                        if not model:
                            logger.warning(f"Model {model_uuid} not found")
                            return
                        
                        # Create LLM client
                        llm_client = LLMClient(
                            api_key=model.get('api_key'),
                            base_url=model.get('base_url'),
                            model_name=model.get('model_name')
                        )
                        
                        # Get bot name from config or default
                        bot_name = config.get('config', {}).get('bot_name', 'AI助手')
                        
                        # Extract images from message for vision models
                        image_urls = []
                        if isinstance(message, list):
                            for seg in message:
                                if isinstance(seg, dict) and seg.get('type') == 'image':
                                    img_url = seg.get('data', {}).get('url') or seg.get('data', {}).get('file')
                                    if img_url and (img_url.startswith('http://') or img_url.startswith('https://')):
                                        image_urls.append(img_url)
                        
                        # Also check raw_message for CQ code format
                        if not image_urls and raw_message:
                            import re
                            cq_images = re.findall(r'\[CQ:image,file=([^,\]]+)(?:,url=([^,\]]+))?', raw_message)
                            for file_ref, url_ref in cq_images:
                                if url_ref and (url_ref.startswith('http://') or url_ref.startswith('https://')):
                                    image_urls.append(url_ref)
                        
                        # Prepare message dict for RuaBot
                        RuaBot_message = {
                            'message_id': data.get('message_id', str(time.time())),
                            'user_id': str(user_id),
                            'user_name': data.get('sender', {}).get('card') or data.get('sender', {}).get('nickname', 'User'),
                            'content': raw_message,
                            'time': data.get('time', time.time()),
                            'image_urls': image_urls if image_urls else None,  # Add image URLs
                            'has_image': bool(image_urls)
                        }
                        
                        # Get system prompt from preset
                        system_prompt = None
                        preset_uuid = config.get('preset_uuid')
                        if preset_uuid:
                            db_manager = get_database_manager()
                            preset = await db_manager.get_ai_preset(preset_uuid)
                            if preset:
                                system_prompt = preset.system_prompt
                        
                        # Get tools configuration
                        enabled_tools = config.get('config', {}).get('enabled_tools', {})
                        tools_enabled = config.get('config', {}).get('tools_enabled', False)
                        tools = None
                        if tools_enabled:
                            tools = AITools.get_tools(enabled_tools)
                            if tools:
                                logger.info(f"RuaBot: {len(tools)} tools enabled")
                        
                        # Check if streaming is enabled
                        stream_enabled = config.get('config', {}).get('stream_enabled', False)
                        
                        # Check if TTS is enabled
                        tts_mode_enabled = config.get('config', {}).get('tts_mode_enabled', False)
                        tts_mode_type = config.get('config', {}).get('tts_mode_type', 'auto')
                        
                        # Check if model supports vision
                        supports_vision = model.get('supports_vision', False)
                        
                        # Use RuaBot handler
                        reply = await self.RuaBot_handler.handle_message(
                            chat_id=chat_id,
                            message=RuaBot_message,
                            llm_client=llm_client,
                            bot_name=bot_name,
                            system_prompt=system_prompt,
                            enable_brain_mode=True,   # Enable ReAct planning
                            enable_learning=True,      # Enable learning
                            think_level=1,             # Advanced mode
                            tools=tools,               # Pass tools
                            stream=False,              # RuaBot uses non-streaming for now (can enhance later)
                            supports_vision=supports_vision  # Vision support
                        )
                        
                        # Handle reply (string or None)
                        if reply and isinstance(reply, str) and reply.strip():
                            reply_text = reply.strip()
                            logger.info(f"RuaBot generated reply: {reply_text[:100]}...")
                            
                            # Check if TTS mode is enabled
                            if tts_mode_enabled and reply_text:
                                try:
                                    logger.info(f"TTS mode enabled (type: {tts_mode_type}), converting text to speech")
                                    # Call TTS tool directly (skip permission check for internal TTS calls)
                                    tts_result = await AITools.call_tool(
                                        tool_name="text_to_speech",
                                        arguments={
                                            "text": reply_text,
                                            "message_type": message_type,
                                            "target_id": str(group_id) if message_type == 'group' and group_id else str(user_id) if message_type == 'private' and user_id else None,
                                            "voice_type": 601005,
                                            "codec": "wav",
                                            "sample_rate": 16000,
                                            "speed": 0,
                                            "volume": 0
                                        },
                                        skip_permission_check=True  # Skip permission for internal TTS
                                    )
                                    
                                    if tts_result and tts_result.get("success"):
                                        logger.info("[RuaBot] TTS conversion successful")
                                        # TTS tool already sends the audio, so we're done
                                        if tts_mode_type == "only":
                                            # Only send audio, no text
                                            logger.info("TTS-only mode: skipping text message")
                                            return
                                        # If mode is "auto", continue to send text as well
                                    else:
                                        error_msg = tts_result.get("error", "Unknown error") if tts_result else "No result"
                                        logger.warning(f"TTS conversion failed: {error_msg}")
                                except Exception as e:
                                    logger.error(f"TTS conversion error: {e}", exc_info=True)
                            
                            # Send text message (if TTS didn't handle it)
                            app = get_app()
                            if app and hasattr(app, 'onebot_adapter'):
                                onebot = app.onebot_adapter
                                if message_type == 'group' and group_id:
                                    await onebot.send_message(str(group_id), reply_text, "group")
                                elif message_type == 'private' and user_id:
                                    await onebot.send_message(str(user_id), reply_text, "private")
                                logger.info("[RuaBot] Reply sent successfully")
                            else:
                                logger.error("[RuaBot] Failed to send: OneBot adapter not available")
                        else:
                            logger.info("RuaBot chose not to reply (returned empty/None)")
                        
                        # Skip the regular maxtoken processing
                        return
                        
                    except Exception as e:
                        logger.error(f"RuaBot handler failed, falling back to regular mode: {e}", exc_info=True)
                        # Fall through to regular maxtoken processing
                
                # Regular maxtoken mode (fallback or if RuaBot disabled)
                # Get or create state for this chat
                if chat_id not in self._maxtoken_state:
                    self._maxtoken_state[chat_id] = {
                        'consecutive_no_reply_count': 0,
                        'last_read_time': 0.0
                    }
                
                state = self._maxtoken_state[chat_id]
                
                # Dynamic threshold based on consecutive no_reply count
                consecutive_no_reply = state['consecutive_no_reply_count']
                if consecutive_no_reply >= 5:
                    threshold = 2  # Need at least 2 messages
                elif consecutive_no_reply >= 3:
                    # 50% probability: 1 or 2 messages
                    threshold = 2 if random.random() < 0.5 else 1
                else:
                    threshold = 1  # Default: 1 message triggers
                
                # Get talk_value from config (default 1.0)
                config_obj = config.get('config', {})
                talk_value = config_obj.get('talk_value', 1.0)
                if talk_value <= 0:
                    talk_value = 0.0000001  # Prevent zero
                
                # Get frequency adjustment
                frequency_control = frequency_control_manager.get_or_create_frequency_control(chat_id)
                frequency_adjust = frequency_control.get_talk_frequency_adjust()
                
                # Check if message mentions bot (simplified check)
                is_mentioned = False
                if group_id:
                    # Check for @ mentions in raw_message
                    bot_qq = config.get('bot_qq', '')
                    if bot_qq and (f"@{bot_qq}" in raw_message or f"@全体成员" in raw_message):
                        is_mentioned = True
                
                # Probability check (unless mentioned)
                if is_mentioned:
                    # Mentioned: always process
                    logger.info(f"MaxToken mode: mentioned, processing message (threshold={threshold}, consecutive_no_reply={consecutive_no_reply})")
                    message_content = raw_message
                elif random.random() < talk_value * frequency_adjust:
                    # Probability check passed: process
                    logger.info(f"MaxToken mode: probability check passed ({talk_value * frequency_adjust:.2%}), processing message (threshold={threshold}, consecutive_no_reply={consecutive_no_reply})")
                    message_content = raw_message
                else:
                    # Probability check failed: skip
                    logger.debug(f"MaxToken mode: probability check failed ({talk_value * frequency_adjust:.2%}), skipping message (threshold={threshold}, consecutive_no_reply={consecutive_no_reply})")
                    return  # Skip processing
            # Command mode: only messages with trigger command are processed
            elif trigger_mode == 'command':
                # Handle image messages: require trigger prefix if set, or skip if no prefix
                if has_image:
                    if trigger_command:
                        # Image message requires trigger prefix
                        if not raw_message.startswith(trigger_command):
                            logger.debug(f"Image message does not start with trigger command '{trigger_command}'")
                            return
                        # Remove trigger command from message
                        message_content = raw_message[len(trigger_command):].strip()
                    else:
                        # No trigger command set, skip image messages
                        # (since model might not support images, or user wants prefix for images)
                        logger.debug("Image message received but no trigger command set, skipping")
                        return
                elif trigger_command:
                    # Text message with trigger command requirement
                    if not raw_message.startswith(trigger_command):
                        logger.debug(f"Message does not start with trigger command '{trigger_command}'")
                        return
                    # Remove trigger command from message
                    message_content = raw_message[len(trigger_command):].strip()
                else:
                    # No trigger command set in command mode, skip message
                    logger.debug("Command mode but no trigger command set, skipping message")
                    return
            else:
                # Unknown trigger mode, default to command mode behavior
                logger.warning(f"Unknown trigger_mode '{trigger_mode}', defaulting to command mode")
                if trigger_command and not raw_message.startswith(trigger_command):
                    logger.debug(f"Message does not start with trigger command '{trigger_command}'")
                    return
                message_content = raw_message[len(trigger_command):].strip() if trigger_command else raw_message
            
            # For image messages, allow empty text content (image only)
            if not message_content and not has_image:
                logger.debug("Message content is empty after removing trigger command")
                return
            
            logger.info(f"Processing AI message: {config_type}:{target_id}, content: {message_content[:50] if message_content else '(image only)'}, has_image={has_image}")
            
            # Process message asynchronously (don't block event processing)
            asyncio.create_task(self._process_ai_message(
                config_type, target_id, message_content, user_id, group_id, message_type, data
            ))
            
        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)
    
    async def _process_ai_message(
        self,
        config_type: str,
        target_id: str,
        message_content: str,
        user_id: int,
        group_id: Optional[int],
        message_type: str,
        event_data: Optional[Dict[str, Any]] = None
    ):
        """Process AI message and generate response.
        
        Args:
            config_type: 'group' or 'user'
            target_id: Group ID or user ID
            message_content: Message content (without trigger command)
            user_id: User ID who sent the message
            group_id: Group ID (if group message)
            message_type: 'group' or 'private'
        """
        try:
            # Initialize user/group info variables
            user_name = ''
            user_nickname = ''
            group_name = ''
            
            # Extract user/group info from event_data if available
            if event_data:
                sender = event_data.get('sender', {})
                if isinstance(sender, dict):
                    # user_name: 优先使用群名片(card)，如果没有则使用昵称(nickname)
                    user_name = sender.get('card') or sender.get('nickname', '')
                    user_nickname = sender.get('nickname', '')
            
            # Get configuration
            config = await self.ai_manager.get_config(config_type, target_id)
            
            # Get model
            model_uuid = config.get('model_uuid')
            if not model_uuid:
                # Try to get default model
                db_manager = get_database_manager()
                default_model = await db_manager.get_default_llm_model()
                if not default_model:
                    logger.warning(f"No model configured for {config_type}:{target_id}")
                    return
                model_uuid = default_model.uuid
            
            # Get preset
            preset_uuid = config.get('preset_uuid')
            preset_data = None
            if preset_uuid:
                db_manager = get_database_manager()
                preset = await db_manager.get_ai_preset(preset_uuid)
                if preset:
                    preset_data = preset.to_dict()
            
            # Get memory
            memory = await self.ai_manager.get_memory(config_type, target_id, preset_uuid)
            memory_messages = memory.get('messages', [])
            
            # Get model details
            model_data = await self.model_manager.get_model_with_secret(model_uuid)
            if not model_data:
                error_msg = "未找到配置的模型，请检查AI配置中的模型设置"
                logger.error(f"Model not found: {model_uuid}")
                # Send error message to user
                try:
                    app = get_app()
                    if app and hasattr(app, 'onebot_adapter'):
                        onebot = app.onebot_adapter
                        if message_type == 'group' and group_id:
                            await onebot.send_message(str(group_id), error_msg, "group")
                        elif message_type == 'private' and user_id:
                            await onebot.send_message(str(user_id), error_msg, "private")
                except Exception as e:
                    logger.error(f"Failed to send error message: {e}", exc_info=True)
                return
            
            # Try to get group name from API if group_id exists
            if group_id:
                try:
                    app = get_app()
                    if app and hasattr(app, 'onebot_adapter'):
                        onebot = app.onebot_adapter
                        group_info = await onebot.call_api('get_group_info', {'group_id': int(group_id)})
                        if group_info and isinstance(group_info, dict):
                            group_name = group_info.get('group_name', '')
                except Exception as e:
                    logger.debug(f"Failed to get group name: {e}")
            
            # Prepare messages for LLM
            messages: List[Dict[str, Any]] = []
            
            # Add system prompt if preset exists (without variable replacements)
            if preset_data and preset_data.get('system_prompt'):
                system_prompt = preset_data['system_prompt']
                messages.append({
                    'role': 'system',
                    'content': system_prompt
                })
            
            # Add context information as a system message (always add, not in preset)
            context_info = []
            now = datetime.now()
            context_info.append(f"当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
            context_info.append(f"用户QQ号: {user_id}")
            if user_name:
                context_info.append(f"用户名称: {user_name}")
            if user_nickname and user_nickname != user_name:
                context_info.append(f"用户昵称: {user_nickname}")
            if group_id:
                context_info.append(f"群号: {group_id}")
            if group_name:
                context_info.append(f"群名称: {group_name}")
            
            # Add information about recent messages from memory (including message_ids)
            if memory_messages:
                recent_messages_info = []
                recent_count = min(5, len(memory_messages))  # Last 5 messages
                recent_msgs = memory_messages[-recent_count:]
                for msg in recent_msgs:
                    role = msg.get('role', '')
                    content_preview = str(msg.get('content', ''))[:50] + ('...' if len(str(msg.get('content', ''))) > 50 else '')
                    msg_id = msg.get('message_id', '')
                    if role == 'user':
                        recent_messages_info.append(f"  - 用户消息 (ID: {msg_id}): {content_preview}")
                    elif role == 'assistant':
                        recent_messages_info.append(f"  - AI回复 (ID: {msg_id}): {content_preview}")
                
                if recent_messages_info:
                    context_info.append("\n最近的消息历史（包含消息ID，可用于回复或撤回）:")
                    context_info.extend(recent_messages_info)
                    context_info.append("\n注意：你可以使用reply_to_message_id参数来回复某条消息，使用message_id参数来撤回某条消息。")
            
            # Add instruction about choosing not to reply
            trigger_mode = config.get('config', {}).get('trigger_mode', 'command')
            if trigger_mode == 'maxtoken':
                # MaxToken mode: AI should actively decide whether to reply
                chat_id = f"{config_type}:{target_id}"
                state = self._maxtoken_state.get(chat_id, {})
                consecutive_no_reply = state.get('consecutive_no_reply_count', 0)
                
                context_info.append("\n【重要提示 - MaxToken模式（拟人化）】")
                context_info.append("当前处于MaxToken模式，所有消息都会发送给你，你需要像正常群友一样，谨慎判断是否需要回复。")
                context_info.append("")
                context_info.append("【当前状态】")
                context_info.append(f"- 连续不回复次数: {consecutive_no_reply}")
                if consecutive_no_reply >= 3:
                    context_info.append(f"- 提示：你已经连续{consecutive_no_reply}次选择不回复，现在应该更加谨慎，只在真正需要时才回复")
                context_info.append("")
                context_info.append("【回复原则 - 像正常群友一样】")
                context_info.append("你应该表现得像一个正常的群成员，而不是一个总是回复的机器人。")
                context_info.append("")
                context_info.append("【以下情况必须跳过回复（返回空内容）】")
                context_info.append("1. 用户明确表示不需要你回复，包括但不限于：")
                context_info.append("   - '没问你'、'你别说话了'、'不要回复'、'不回复'、'无需回复'")
                context_info.append("   - '不用你管'、'不用回复'、'别回复'、'别说话'")
                context_info.append("   - 任何明确表示不需要你参与的消息")
                context_info.append("2. 普通闲聊、无关话题、或群友之间的日常对话 - 不需要你参与")
                context_info.append("3. 消息没有明确指向你、没有@你、或不是对你的提问 - 不要主动插话")
                context_info.append("4. 群友在讨论与你无关的话题 - 不要打断别人的对话")
                context_info.append("5. 消息只是表情、图片、或简单的互动（如'哈哈'、'666'等）- 不需要回复")
                context_info.append("6. 消息已经得到其他群友的回复，且不需要你的补充 - 避免重复回复")
                context_info.append("7. 消息内容不完整、不清晰、或无法理解 - 不要猜测回复")
                context_info.append("8. 用户只是在自言自语、发牢骚、或表达情绪，没有提问或需要帮助")
                context_info.append("")
                context_info.append("【以下情况才应该回复】")
                context_info.append("1. 消息明确@了你，或直接向你提问")
                context_info.append("2. 消息需要你执行操作（如使用工具、搜索、发送消息等）")
                context_info.append("3. 消息需要你提供帮助、解答问题、或分享信息")
                context_info.append("4. 消息是紧急情况、需要立即处理的内容")
                context_info.append("5. 群友在讨论你擅长的话题，且你的回复能提供有价值的信息")
                context_info.append("")
                context_info.append("【关键规则】")
                context_info.append("- 如果用户说'没问你'、'你别说话了'等，你必须立即停止回复，返回空内容")
                context_info.append("- 要跳过回复，只需返回空内容（不返回任何文本），不要返回'好的'、'明白了'、'抱歉'等任何确认性回复")
                context_info.append("- 宁可少回复，也不要过度回复。保持沉默比频繁回复更自然")
                context_info.append("- 记住：你是一个群成员，不是客服机器人，不需要对每条消息都回复")
                context_info.append("- 当用户明确表示不需要你回复时，不要解释、不要道歉、不要回复任何内容，直接返回空内容")
                context_info.append("- 如果你已经连续多次选择不回复，说明你可能过于活跃了，应该继续保持沉默，只在真正需要时才回复")
            else:
                # Command mode: normal behavior
                context_info.append("\n重要提示：")
                context_info.append("1. 如果用户明确要求'不要回复'、'不回复'、'无需回复'等，你必须返回空内容（不返回任何文本），系统将不会发送回复。")
                context_info.append("2. 如果你认为不需要回复这条消息（例如：消息不重要、已经在工具调用中完成操作、或只是普通聊天无需回应），你可以返回空内容，系统将不会发送回复消息。")
                context_info.append("3. 要跳过回复，只需不返回任何文本内容即可，不要返回'好的'、'明白了'等确认性回复。")
            
            if context_info:
                messages.append({
                    'role': 'system',
                    'content': '\n'.join(context_info)
                })
            
            # Add conversation history (include message_id info in content if available)
            for msg in memory_messages:
                role = msg.get('role', 'user')
                content = msg.get('content', '')
                message_id = msg.get('message_id', '')
                
                if role in ['user', 'assistant', 'system'] and content:
                    # Handle multimodal content (images)
                    if isinstance(content, list):
                        msg_dict = {'role': role, 'content': content}
                    else:
                        # Add message_id as metadata comment for AI awareness
                        if message_id:
                            # Append message_id info to content for AI reference
                            enhanced_content = content
                            if role == 'assistant':
                                enhanced_content = f"{content}\n[消息ID: {message_id}]"
                            msg_dict = {'role': role, 'content': enhanced_content}
                        else:
                            msg_dict = {'role': role, 'content': content}
                    messages.append(msg_dict)
            
            # Initialize skip reply flag
            should_skip_reply = False
            
            # Check if user explicitly requested no reply (before processing)
            # Expanded keyword list based on RuaBot's approach
            skip_request_keywords = [
                "不要回复", "不回复", "无需回复", "别回复", "不用回复", "不需要回复", "拒绝回复",
                "没问你", "你别说话了", "你别说了", "别说话", "不要说话", "不用你管",
                "不用你", "不需要你", "别理我", "别回", "不用回", "不要回", "别回我", "不用回我",
                "你别回", "你别回复", "不用你回复", "不需要你回复"
            ]
            # Check both current message and recent messages
            message_content_lower = message_content.lower()
            if any(keyword in message_content_lower for keyword in skip_request_keywords):
                should_skip_reply = True
                logger.info(f"User explicitly requested no reply, skipping response")
                # Still save user message to memory but don't generate response
                user_message = {
                    'role': 'user',
                    'content': message_content,
                    'timestamp': datetime.utcnow().isoformat()
                }
                if event_data and event_data.get('message_id'):
                    user_message['message_id'] = str(event_data.get('message_id'))
                await self.ai_manager.create_or_update_memory(
                    config_type, target_id, [user_message], preset_uuid
                )
                return  # Exit early without processing
            
            # Prepare current user message with images if available
            user_message_content: List[Dict[str, Any]] = []
            
            # Check if message contains images
            image_urls = []
            
            # First, try to get images from message array format
            if event_data and isinstance(event_data.get('message'), list):
                for seg in event_data['message']:
                    if isinstance(seg, dict) and seg.get('type') == 'image':
                        image_url = seg.get('data', {}).get('url') or seg.get('data', {}).get('file')
                        if image_url:
                            image_urls.append(image_url)
            
            # Also check raw_message for CQ code format: [CQ:image,file=xxx.jpg]
            if not image_urls and event_data:
                raw_msg = event_data.get('raw_message', '')
                if raw_msg:
                    # Parse CQ codes: [CQ:image,file=xxx.jpg] or [CQ:image,file=xxx.jpg,url=xxx]
                    # Match the entire CQ code including all parameters
                    cq_image_pattern = r'\[CQ:image,([^\]]+)\]'
                    matches = re.findall(cq_image_pattern, raw_msg)
                    for match in matches:
                        # Parse parameters from CQ code
                        # Format: summary=&#91;动画表情&#93;,file=xxx.jpg,sub_type=1,url=https://...,file_size=140552
                        # Note: Need to handle HTML entities and URL parameters carefully
                        params = {}
                        
                        # First decode HTML entities in the entire match string
                        import html
                        try:
                            decoded_match = html.unescape(match)
                        except:
                            decoded_match = match
                        
                        # Parse key=value pairs
                        # Strategy: Split by comma, but be careful with URL values
                        # Since URL comes after 'url=', we can identify it and handle it specially
                        parts = decoded_match.split(',')
                        i = 0
                        while i < len(parts):
                            part = parts[i].strip()
                            if '=' in part:
                                key, value = part.split('=', 1)
                                key = key.strip()
                                value = value.strip()
                                
                                # If this is a URL parameter and value starts with http, 
                                # it might continue in next parts until we find another key=value
                                if key == 'url' and (value.startswith('http://') or value.startswith('https://')):
                                    # Collect remaining parts until we find another key=value pair
                                    url_parts = [value]
                                    i += 1
                                    while i < len(parts):
                                        next_part = parts[i].strip()
                                        # Check if next part is a new key=value pair
                                        if '=' in next_part and not next_part.startswith('http'):
                                            # This is a new parameter, stop collecting URL
                                            break
                                        url_parts.append(next_part)
                                        i += 1
                                    # Join URL parts (they might have been split at commas)
                                    full_url = ','.join(url_parts)
                                    params[key] = full_url
                                    continue
                                else:
                                    params[key] = value
                            i += 1
                        
                        image_file = params.get('file', '')
                        image_url = params.get('url', '')
                        
                        logger.debug(f"Parsed CQ image: file={image_file}, url={image_url[:50] if image_url else 'None'}...")
                        
                        if image_file:
                            if image_url and (image_url.startswith('http://') or image_url.startswith('https://')):
                                # Use URL if provided and valid
                                image_urls.append(image_url)
                            else:
                                # Use file name, will try to get URL from API
                                image_urls.append(image_file)
            
            # Convert image files to URLs if needed
            processed_image_urls = []
            for img_ref in image_urls:
                # If it's already a full URL, use it directly
                if img_ref.startswith('http://') or img_ref.startswith('https://'):
                    processed_image_urls.append(img_ref)
                else:
                    # Try to get full URL from OneBot API
                    try:
                        app = get_app()
                        if app and hasattr(app, 'onebot_adapter'):
                            onebot = app.onebot_adapter
                            # Try to get image URL
                            image_info = await onebot.call_api('get_image', {'file': img_ref})
                            if image_info and isinstance(image_info, dict):
                                full_url = image_info.get('url', '')
                                if full_url:
                                    processed_image_urls.append(full_url)
                                else:
                                    # If no URL returned, try to construct one
                                    # Some OneBot implementations return file path directly
                                    logger.debug(f"Image info returned: {image_info}, using file reference: {img_ref}")
                                    # For now, skip if we can't get a URL
                                    # Some models might accept file:// URLs, but most need http/https
                                    logger.warning(f"Could not get full URL for image: {img_ref}")
                            else:
                                logger.debug(f"get_image API returned non-dict: {image_info}")
                    except Exception as e:
                        logger.debug(f"Failed to get image URL for {img_ref}: {e}")
            
            image_urls = processed_image_urls
            
            # Add images to message content if model supports vision
            supports_vision = model_data.get('supports_vision', False)
            if image_urls and supports_vision:
                for img_url in image_urls:
                    user_message_content.append({
                        'type': 'image_url',
                        'image_url': {'url': img_url}
                    })
            
            # Add text content if available
            if message_content:
                if user_message_content:
                    user_message_content.append({
                        'type': 'text',
                        'text': message_content
                    })
                else:
                    user_message_content = message_content
            
            # If no content at all, use empty string
            if not user_message_content:
                user_message_content = ""
            
            messages.append({
                'role': 'user',
                'content': user_message_content
            })
            
            # Get preset parameters or use defaults
            temperature = preset_data.get('temperature', 1.0) if preset_data else 1.0
            max_tokens = preset_data.get('max_tokens', 2000) if preset_data else 2000
            top_p = preset_data.get('top_p') if preset_data else None
            top_k = preset_data.get('top_k') if preset_data else None
            
            # Create LLM client and generate response
            api_key = model_data.get('api_key', '')
            base_url = model_data.get('base_url') or 'https://api.openai.com/v1'
            model_name = model_data.get('model_name', '')
            provider = model_data.get('provider', 'openai')
            
            # Normalize base_url - remove /chat/completions if present, ensure it ends with /v1
            base_url = base_url.rstrip('/')
            if base_url.endswith('/chat/completions'):
                base_url = base_url[:-15].rstrip('/')
            # For DeepSeek and OpenAI-compatible APIs, ensure /v1 suffix if not present
            if provider == 'deepseek':
                if not base_url.endswith('/v1'):
                    base_url = base_url.rstrip('/') + '/v1'
            elif 'api.openai.com' in base_url or 'deepseek.com' in base_url:
                if not base_url.endswith('/v1'):
                    base_url = base_url.rstrip('/') + '/v1'
            
            if not api_key or not model_name:
                error_msg = "模型配置不完整，请检查模型的API密钥和模型名称是否已正确设置"
                logger.error(f"Model missing API key or model name: {model_uuid}")
                # Send error message to user
                try:
                    app = get_app()
                    if app and hasattr(app, 'onebot_adapter'):
                        onebot = app.onebot_adapter
                        if message_type == 'group' and group_id:
                            await onebot.send_message(str(group_id), error_msg, "group")
                        elif message_type == 'private' and user_id:
                            await onebot.send_message(str(user_id), error_msg, "private")
                except Exception as e:
                    logger.error(f"Failed to send error message: {e}", exc_info=True)
                return
            
            logger.info(f"Calling LLM: {provider}/{model_name} for {config_type}:{target_id}")
            
            llm_client = LLMClient(api_key, base_url, model_name, provider)
            try:
                # Get enabled tools from config
                enabled_tools = config.get('config', {}).get('enabled_tools', {})
                
                # Check if tools are enabled at all
                tools_enabled = config.get('config', {}).get('tools_enabled', False)
                
                # Get available tools only if tools are enabled
                tools = None
                if tools_enabled:
                    # If no config, enable all tools by default
                    if not enabled_tools:
                        enabled_tools = {name: True for name in AITools.ALL_TOOLS.keys()}
                    
                    # Get available tools (filtered by enabled_tools)
                    tools = AITools.get_tools(enabled_tools)
                    
                    # Get MCP tools and add to tools list
                    if self.mcp_manager:
                        try:
                            mcp_tools = await self.mcp_manager.convert_mcp_tools_to_openai_format()
                            tools.extend(mcp_tools)
                            logger.debug(f"Added {len(mcp_tools)} MCP tools to available tools")
                        except Exception as e:
                            logger.warning(f"Failed to get MCP tools: {e}", exc_info=True)
                    
                    logger.info(f"Tools enabled with {len(tools) if tools else 0} available tools")
                    
                    # Add instruction about using tools (if tools are available)
                    tool_names = [tool.get("function", {}).get("name", "") for tool in tools]
                    if tool_names:
                        tool_instruction = (
                            "\n重要工具使用规则："
                            "\n1. 当用户要求执行操作（如搜索、TTS、群管理等）时，你必须使用工具调用（tool_calls）来执行，而不是在文本中描述你要做什么。"
                            "\n2. 你应该主动使用工具来提升交互体验，例如："
                            "   - 当需要查询信息时，主动使用搜索工具"
                            "   - 当对话需要语音时，主动使用text_to_speech工具"
                            "   - 当需要执行群管理操作时，使用相应的群管理工具"
                            "\n3. 工具调用后，如果工具已经完成了操作，你不需要再发送确认消息。工具已经完成了任务，直接结束对话即可。"
                            "\n4. 只有在工具调用失败或需要补充说明时，才需要发送文本回复。"
                            f"\n可用工具：{', '.join(tool_names[:10])}{'...' if len(tool_names) > 10 else ''}"
                            "\n\n[重要] 关于消息发送工具的特殊说明："
                            "\n1. send_group_message 和 send_private_message 是特殊用途工具，仅用于："
                            "   - 需要@（艾特）用户时（使用send_group_message的at_user_ids参数）"
                            "   - 需要引用/回复某条消息时（使用reply_to_message_id参数）"
                            "   - 给其他群或用户发送消息时（跨群/跨用户发送）"
                            "\n2. [重要] 正常对话回复不要使用这些工具！直接返回文本内容即可，系统会自动将你的文本回复发送到当前群或私聊。"
                            "\n3. 如果你只是要回复用户的问题或进行正常对话，直接返回文本，不要调用send_group_message或send_private_message工具。"
                            "\n4. 使用send_group_message工具时，不要在message参数中包含@符号，系统会根据at_user_ids参数自动添加@。"
                            "\n5. 在正常文本回复中，不要包含@符号或@用户，因为系统会自动处理@功能。"
                            "\n6. 如果工具已经发送了消息，不要再次发送文本消息，避免重复。"
                        )
                        messages.append({
                            'role': 'system',
                            'content': tool_instruction
                        })
                else:
                    logger.info("Tools are disabled in config")
                
                # Check if streaming is enabled in config
                config_obj = config.get('config', {})
                enable_streaming = config_obj.get('enable_streaming', True)  # Default to True
                
                # Initialize skip reply flag (before try block so it's accessible after)
                should_skip_reply = False
                
                # Track if any tool has already sent a message (to avoid duplicate messages)
                tool_sent_message = False
                
                # Call LLM with tools support (with multi-round tool calling)
                response_text = ""
                response = None  # Initialize response variable
                max_tool_rounds = 10  # Maximum number of tool calling rounds to prevent infinite loops
                current_round = 0
                
                # Multi-round tool calling loop
                while current_round < max_tool_rounds:
                    current_round += 1
                    
                    # On the last round, add a system message to force final response
                    if current_round == max_tool_rounds:
                        messages.append({
                            'role': 'system',
                            'content': '请根据以上工具调用结果，总结并回复用户。不要再调用工具，直接给出最终回复。'
                        })
                    
                    # Call LLM
                    tools_to_use = tools if current_round < max_tool_rounds else None
                    if tools_to_use:
                        logger.debug(f"[Round {current_round}] Sending {len(tools_to_use)} tools to LLM")
                    
                    # Call LLM with thread pool support for blocking operations
                    response = await llm_client.chat_completion(
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        top_p=top_p,
                        top_k=top_k,
                        tools=tools_to_use,  # Disable tools on last round
                        stream=False,
                        thread_pool=self.thread_pool  # Pass thread pool for blocking operations
                    )
                    
                    # Log response type for debugging
                    logger.debug(f"[Round {current_round}] LLM response type: {response.get('type') if isinstance(response, dict) else type(response)}")
                    
                    # Handle tool calls (for non-streaming)
                    if isinstance(response, dict) and response.get("type") == "tool_calls":
                        # Model wants to call tools
                        tool_calls = response.get("tool_calls", [])
                        logger.info(f"[Round {current_round}] Model requested {len(tool_calls)} tool calls")
                        
                        # Execute tool calls
                        tool_results = []
                        for tool_call in tool_calls:
                            tool_id = tool_call.get("id")
                            function = tool_call.get("function", {})
                            tool_name = function.get("name")
                            tool_args = json.loads(function.get("arguments", "{}"))
                            
                            logger.info(f"Calling tool: {tool_name} with args: {tool_args}")
                            
                            # Prepare context for tool call (to fill missing parameters)
                            tool_context = {
                                "group_id": group_id,
                                "user_id": user_id,
                                "message_type": message_type,
                                "config_type": config_type,
                                "target_id": target_id
                            }
                            
                            # Call tool with context
                            tool_result = await self._execute_tool_call(tool_name, tool_args, tool_context)
                            
                            # Check if this tool sent a message (to avoid duplicate messages)
                            if tool_name in ["send_group_message", "send_private_message"]:
                                if tool_result.get("success"):
                                    tool_sent_message = True
                                    logger.info(f"Tool {tool_name} successfully sent a message, will skip text reply")
                            
                            tool_results.append({
                                "tool_call_id": tool_id,
                                "role": "tool",
                                "name": tool_name,
                                "content": json.dumps(tool_result, ensure_ascii=False)
                            })
                        
                        # Add tool calls and results to messages
                        messages.append({
                            "role": "assistant",
                            "content": response.get("content", ""),
                            "tool_calls": tool_calls
                        })
                        messages.extend(tool_results)
                        
                        # If tool already sent a message, skip further rounds to avoid duplicate messages
                        if tool_sent_message:
                            logger.info("Tool already sent a message, skipping further rounds to avoid duplicate")
                            should_skip_reply = True
                            response_text = ""
                            break
                        
                        # Continue to next round to let model process tool results
                        continue
                    
                    elif isinstance(response, dict):
                        # Regular text response - exit loop
                        response_text = response.get("content", "")
                        
                        # Clean up @ mentions from text response to avoid duplicate @
                        # (Tool calls already handle @ mentions via MessageSegment)
                        # Remove @符号 and @用户格式的文本
                        # Pattern: @数字 或 @用户名
                        response_text = re.sub(r'@\d+', '', response_text)  # Remove @数字
                        response_text = re.sub(r'@[^\s@]+', '', response_text)  # Remove @用户名
                        # Clean up extra spaces
                        response_text = re.sub(r'\s+', ' ', response_text).strip()
                        
                        break
                    else:
                        # Fallback for string response (backward compatibility)
                        response_text = str(response)
                        # Clean up @ mentions from text response
                        response_text = re.sub(r'@\d+', '', response_text)
                        response_text = re.sub(r'@[^\s@]+', '', response_text)
                        response_text = re.sub(r'\s+', ' ', response_text).strip()
                        break
                
                # Check if AI chose to skip reply
                skip_reply_keywords = ["SKIP_REPLY", "不回复", "无需回复", "skip_reply", "no_reply"]
                
                if response_text:
                    response_text_upper = response_text.strip().upper()
                    # Check if response contains skip keywords
                    if any(keyword in response_text_upper for keyword in skip_reply_keywords):
                        should_skip_reply = True
                        logger.info("AI chose to skip reply based on response content")
                        response_text = ""  # Clear response text to skip sending
                elif not response_text:
                    # Empty response - AI chose not to reply
                    should_skip_reply = True
                    logger.info("AI returned empty response, skipping reply")
                
                # Update MaxToken mode state based on reply decision
                trigger_mode = config.get('config', {}).get('trigger_mode', 'command')
                if trigger_mode == 'maxtoken':
                    chat_id = f"{config_type}:{target_id}"
                    if chat_id in self._maxtoken_state:
                        state = self._maxtoken_state[chat_id]
                        if should_skip_reply or not response_text:
                            # AI chose not to reply: increment counter
                            state['consecutive_no_reply_count'] += 1
                            logger.debug(f"MaxToken: consecutive_no_reply_count = {state['consecutive_no_reply_count']}")
                        else:
                            # AI replied: reset counter
                            state['consecutive_no_reply_count'] = 0
                            logger.debug(f"MaxToken: reset consecutive_no_reply_count (AI replied)")
                        state['last_read_time'] = time.time()
                
                # Update memory with new messages (user message + assistant response if any)
                new_messages = memory_messages.copy()
                
                # Always save user message
                user_message = {
                    'role': 'user',
                    'content': message_content,
                    'timestamp': datetime.utcnow().isoformat()
                }
                if event_data and event_data.get('message_id'):
                    user_message['message_id'] = str(event_data.get('message_id'))
                new_messages.append(user_message)
                
                # Only save assistant response if there's actual content (not skipped)
                if not should_skip_reply and response_text:
                    assistant_message = {
                        'role': 'assistant',
                        'content': response_text,
                        'timestamp': datetime.utcnow().isoformat()
                    }
                    new_messages.append(assistant_message)
                    
                    logger.info(f"Generated AI response: {response_text[:100]}...")
                else:
                    logger.info("AI chose not to reply, skipping message sending")
                
                # Limit memory size (keep last 50 messages)
                if len(new_messages) > 50:
                    new_messages = new_messages[-50:]
                
                await self.ai_manager.create_or_update_memory(
                    config_type, target_id, new_messages, preset_uuid
                )
                
                # Only increment message count if AI actually replied
                if not should_skip_reply and response_text:
                    await self.ai_manager.increment_message_count(config_type, target_id)
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Failed to generate LLM response: {e}", exc_info=True)
                
                # Provide user-friendly error messages
                if "402" in error_msg or "Insufficient Balance" in error_msg:
                    response_text = "抱歉，API账户余额不足，请检查账户余额后重试"
                elif "401" in error_msg or "Unauthorized" in error_msg:
                    response_text = "抱歉，API密钥无效或已过期，请检查API密钥配置"
                elif "404" in error_msg:
                    response_text = "抱歉，API地址配置错误，请检查模型配置中的API地址"
                elif "429" in error_msg or "Rate limit" in error_msg:
                    response_text = "抱歉，API请求频率过高，请稍后再试"
                else:
                    response_text = f"抱歉，生成回复时出错了: {error_msg[:100]}"
                
                # Even if response generation failed, save user message to memory
                # This ensures user messages are not lost
                try:
                    new_messages = memory_messages.copy()
                    new_messages.append({
                        'role': 'user',
                        'content': message_content,
                        'timestamp': datetime.utcnow().isoformat()
                    })
                    # Don't save error response to memory, but save user message
                    # Limit memory size (keep last 50 messages)
                    if len(new_messages) > 50:
                        new_messages = new_messages[-50:]
                    
                    await self.ai_manager.create_or_update_memory(
                        config_type, target_id, new_messages, preset_uuid
                    )
                    logger.info(f"Saved user message to memory even though response generation failed")
                except Exception as save_error:
                    logger.error(f"Failed to save user message to memory: {save_error}", exc_info=True)
            finally:
                await llm_client.close()
            
            # Send response back via OneBot API (only if AI didn't skip reply)
            if should_skip_reply or not response_text:
                logger.info(f"AI chose to skip reply, not sending message to {'group ' + str(group_id) if message_type == 'group' else 'user ' + str(user_id)}")
                return  # Exit early without sending message
            
            # Check TTS mode configuration
            tts_mode_enabled = config.get('config', {}).get('tts_mode_enabled', False)
            tts_mode_type = config.get('config', {}).get('tts_mode_type', 'voice_only')  # 'voice_only' or 'text_and_voice'
            
            try:
                app = get_app()
                if app and hasattr(app, 'onebot_adapter'):
                    onebot = app.onebot_adapter
                    
                    # If TTS mode is enabled, automatically convert text to speech
                    tts_success = False
                    if tts_mode_enabled and response_text:
                        try:
                            logger.info(f"TTS mode enabled (type: {tts_mode_type}), converting text to speech")
                            # Call TTS tool directly (skip permission check for internal TTS calls)
                            tts_result = await AITools.call_tool(
                                tool_name="text_to_speech",
                                arguments={
                                    "text": response_text,
                                    "message_type": message_type,
                                    "target_id": str(group_id) if message_type == 'group' and group_id else str(user_id) if message_type == 'private' and user_id else None,
                                    "voice_type": 601005,  # Fixed voice type as per user requirement
                                    "codec": "wav",
                                    "sample_rate": 16000,
                                    "speed": 0,
                                    "volume": 0
                                },
                                skip_permission_check=True  # Skip permission for internal TTS
                            )
                            
                            if tts_result.get("success"):
                                tts_success = True
                                logger.info("TTS conversion successful")
                                # If voice_only mode, skip text sending
                                if tts_mode_type == 'voice_only':
                                    logger.info("Voice-only mode: skipping text message")
                                    # Text is already sent via TTS, so we're done
                                    return
                                # If text_and_voice mode, continue to send text below
                                logger.info("Text+Voice mode: will send text message after voice")
                            else:
                                logger.warning(f"TTS conversion failed: {tts_result.get('error', 'Unknown error')}")
                                # If TTS fails in voice_only mode, send text as fallback
                                if tts_mode_type == 'voice_only':
                                    logger.warning("TTS failed in voice-only mode, sending text as fallback")
                        except Exception as tts_error:
                            logger.error(f"Error in TTS mode: {tts_error}", exc_info=True)
                            # If TTS fails in voice_only mode, send text as fallback
                            if tts_mode_type == 'voice_only':
                                logger.warning("TTS error in voice-only mode, sending text as fallback")
                    
                    # Determine if we should send text:
                    # - If TTS mode is disabled, always send text
                    # - If TTS mode is enabled and type is text_and_voice, send text
                    # - If TTS mode is enabled and type is voice_only:
                    #   - If TTS succeeded, don't send text (already returned above)
                    #   - If TTS failed, send text as fallback
                    should_send_text = not (tts_mode_enabled and tts_mode_type == 'voice_only' and tts_success)
                    
                    if enable_streaming and response_text and should_send_text:
                        # Split response into multiple messages for simulated streaming
                        parts = self._split_response(response_text)
                        logger.info(f"Split response into {len(parts)} parts for simulated streaming")
                        
                        last_result = None
                        for i, part in enumerate(parts):
                            if part.strip():
                                try:
                                    if message_type == 'group' and group_id:
                                        result = await onebot.send_message(str(group_id), part, "group")
                                        logger.debug(f"Sent part {i+1}/{len(parts)} to group {group_id}")
                                        last_result = result  # Keep track of the last result
                                    elif message_type == 'private' and user_id:
                                        result = await onebot.send_message(str(user_id), part, "private")
                                        logger.debug(f"Sent part {i+1}/{len(parts)} to user {user_id}")
                                        last_result = result  # Keep track of the last result
                                    
                                    # Add delay between messages (0.5-2 seconds)
                                    if i < len(parts) - 1:
                                        await asyncio.sleep(random.uniform(0.5, 2.0))
                                except Exception as e:
                                    logger.error(f"Failed to send part {i+1}: {e}", exc_info=True)
                        
                        # Update last sent message's message_id if available
                        if last_result and last_result.get("message_id"):
                            # Update the last assistant message in memory with message_id
                            if new_messages and new_messages[-1].get('role') == 'assistant':
                                new_messages[-1]['message_id'] = str(last_result.get("message_id"))
                                await self.ai_manager.create_or_update_memory(
                                    config_type, target_id, new_messages, preset_uuid
                                )
                        
                        logger.info(f"Sent all {len(parts)} parts to {'group ' + str(group_id) if message_type == 'group' else 'user ' + str(user_id)}")
                    elif should_send_text:
                        # Send as single message (only if not voice_only mode or TTS failed)
                        result = None
                        if message_type == 'group' and group_id:
                            result = await onebot.send_message(str(group_id), response_text, "group")
                            logger.info(f"Sent AI response to group {group_id}: {result}")
                        elif message_type == 'private' and user_id:
                            result = await onebot.send_message(str(user_id), response_text, "private")
                            logger.info(f"Sent AI response to user {user_id}: {result}")
                        
                        # Update assistant message with message_id if available
                        if result and result.get("message_id"):
                            if new_messages and new_messages[-1].get('role') == 'assistant':
                                new_messages[-1]['message_id'] = str(result.get("message_id"))
                                await self.ai_manager.create_or_update_memory(
                                    config_type, target_id, new_messages, preset_uuid
                                )
                else:
                    logger.warning("OneBot adapter not available for sending response")
            except Exception as e:
                logger.error(f"Failed to send AI response: {e}", exc_info=True)
            
        except Exception as e:
            logger.error(f"Error processing AI message: {e}", exc_info=True)

