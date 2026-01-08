"""LLM client for calling various LLM providers."""

import httpx
import json
import re
from typing import Optional, List, Dict, Any, AsyncIterator
from ..core.logger import get_logger

logger = get_logger(__name__)


class LLMClient:
    """Client for calling LLM APIs (OpenAI-compatible)."""
    
    def __init__(self, api_key: str, base_url: str, model_name: str, provider: str = "openai"):
        """
        Initialize LLM client.
        
        Args:
            api_key: API key for the LLM provider
            base_url: Base URL for the API (e.g., https://api.openai.com/v1)
            model_name: Model name (e.g., gpt-4, deepseek-chat)
            provider: Provider name (openai, deepseek, etc.)
        """
        self.api_key = api_key
        # Normalize base_url - remove /chat/completions if present
        base_url = base_url.rstrip('/')
        if base_url.endswith('/chat/completions'):
            base_url = base_url[:-15].rstrip('/')
        self.base_url = base_url
        self.model_name = model_name
        self.provider = provider
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=60.0
            )
        return self._client
    
    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    @staticmethod
    def _parse_tool_call_from_text(text: str, tools: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Try to parse tool call from text response (fallback for models that don't support tool_calls format).
        
        This is a heuristic parser for models like GLM that describe tool calls in text rather than
        using the standard tool_calls format.
        
        Args:
            text: The text response from the model
            tools: List of available tools
            
        Returns:
            Dict with tool call structure if parsed successfully, None otherwise
        """
        if not text or not tools:
            return None
        
        # Create a mapping of tool names
        tool_map = {}
        for tool in tools:
            if isinstance(tool, dict) and "function" in tool:
                func = tool["function"]
                tool_name = func.get("name", "")
                tool_map[tool_name.lower()] = tool_name
        
        # Try to find tool name mentions in text
        text_lower = text.lower()
        matched_tool = None
        
        for tool_name_lower, tool_name in tool_map.items():
            # Look for patterns like "调用text_to_speech工具" or "使用text_to_speech" or "text_to_speech工具"
            patterns = [
                rf"调用\s*{re.escape(tool_name_lower)}\s*工具",
                rf"使用\s*{re.escape(tool_name_lower)}",
                rf"{re.escape(tool_name_lower)}\s*工具",
                rf"调用\s*{re.escape(tool_name)}",
                rf"使用\s*{re.escape(tool_name)}",
            ]
            
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    matched_tool = tool_name
                    break
            
            if matched_tool:
                break
        
        if not matched_tool:
            return None
        
        # Try to extract parameters from text
        # Look for patterns like "参数：text是"你好"", "text是'你好'", "text=\"你好\"", etc.
        args = {}
        
        # Find the tool definition
        tool_def = None
        for tool in tools:
            if isinstance(tool, dict) and "function" in tool:
                func = tool["function"]
                if func.get("name", "") == matched_tool:
                    tool_def = func
                    break
        
        if not tool_def:
            return None
        
        # Try to extract common parameters
        params_schema = tool_def.get("parameters", {}).get("properties", {})
        
        # Common patterns for parameter extraction
        for param_name, param_schema in params_schema.items():
            # Try different patterns (including Chinese quotes)
            # Note: Character class matches: " (U+0022), ' (U+0027), " (U+201C), " (U+201D), ' (U+2018), ' (U+2019)
            quote_chars = r'"\'"\u201C\u201D\u2018\u2019'
            patterns = [
                rf"{re.escape(param_name)}\s*[是=:：]\s*[{quote_chars}]([^{quote_chars}]+)[{quote_chars}]",  # Chinese/English quotes
                rf"{re.escape(param_name)}\s*[是=:：]\s*([^\s,，。]+)",  # No quotes
                rf"{re.escape(param_name)}\s*:\s*[{quote_chars}]([^{quote_chars}]+)[{quote_chars}]",
                rf"{re.escape(param_name)}\s*=\s*[{quote_chars}]([^{quote_chars}]+)[{quote_chars}]",
                rf"{re.escape(param_name)}\s*[是=:：]\s*([0-9]+)",  # Numeric values
            ]
            
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    value = match.group(1).strip()
                    # Remove quotes if present
                    value = value.strip('"\'""')
                    if value:
                        args[param_name] = value
                        break
        
        # Create tool call structure
        return {
            "id": f"call_{matched_tool}_{hash(text) % 100000}",
            "type": "function",
            "function": {
                "name": matched_tool,
                "arguments": json.dumps(args, ensure_ascii=False)
            }
        }
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 1.0,
        max_tokens: int = 2000,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        stream: bool = False,
        thread_pool=None,
        **kwargs
    ):
        """
        Generate chat completion.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            top_p: Nucleus sampling parameter
            top_k: Top-k sampling parameter
            tools: Optional list of tools
            stream: If True, returns an async generator. If False, returns a dict.
            thread_pool: Optional thread pool manager for blocking operations
            **kwargs: Additional parameters
        
        Returns:
            If stream=True: AsyncIterator[str] - yields content chunks
            If stream=False: Dict with 'type' and 'content' or 'tool_calls'
        """
        if stream:
            # Return the streaming generator directly
            return self._chat_completion_stream(
                messages, temperature, max_tokens, top_p, top_k, tools, **kwargs
            )
        else:
            # Call and return the non-streaming result
            return await self._chat_completion_non_stream(
                messages, temperature, max_tokens, top_p, top_k, tools, thread_pool=thread_pool, **kwargs
            )
    
    async def _chat_completion_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        top_p: Optional[float],
        top_k: Optional[int],
        tools: Optional[List[Dict[str, Any]]],
        **kwargs
    ) -> AsyncIterator[str]:
        """Handle streaming chat completion."""
        client = await self._get_client()
        
        # Prepare request payload
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        
        # Add optional parameters
        if top_p is not None:
            payload["top_p"] = top_p
        if top_k is not None:
            payload["top_k"] = top_k
        
        # Add tools if provided
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        
        # Add any additional parameters
        payload.update(kwargs)
        
        try:
            endpoint = "/chat/completions"
            logger.debug(f"Calling LLM API (stream): {self.base_url}{endpoint}, model={self.model_name}")
            
            async with client.stream("POST", endpoint, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    if line.startswith("data: "):
                        line = line[6:]
                    if line.strip() == "[DONE]":
                        break
                    try:
                        chunk_data = json.loads(line)
                        if "choices" in chunk_data and len(chunk_data["choices"]) > 0:
                            choice = chunk_data["choices"][0]
                            delta = choice.get("delta", {})
                            if "content" in delta and delta["content"]:
                                yield delta["content"]
                    except json.JSONDecodeError:
                        continue
                    except Exception as e:
                        logger.debug(f"Error parsing stream chunk: {e}")
                        continue
        except httpx.HTTPStatusError as e:
            error_text = e.response.text if e.response else str(e)
            logger.error(f"LLM API HTTP error: {e.response.status_code} - {error_text}")
            raise RuntimeError(f"LLM API error: {e.response.status_code} - {error_text}")
        except Exception as e:
            logger.error(f"LLM API call failed: {e}", exc_info=True)
            raise
    
    def _parse_response_sync(self, result: Dict[str, Any], tools: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
        """Synchronously parse LLM response (can be run in thread pool)."""
        # Debug: log the raw response to understand what model returns
        logger.debug(f"LLM API raw response (first 500 chars): {str(result)[:500]}")
        
        # Extract response
        if "choices" in result and len(result["choices"]) > 0:
            choice = result["choices"][0]
            message = choice.get("message", {})
            
            # Check if model wants to call a tool (standard OpenAI format)
            if "tool_calls" in message and message["tool_calls"]:
                logger.info(f"Model returned tool_calls: {len(message['tool_calls'])} tool(s)")
                return {
                    "type": "tool_calls",
                    "tool_calls": message["tool_calls"],
                    "content": message.get("content", "")
                }
            
            # Check for alternative tool call formats (some models use different field names)
            # Check if finish_reason indicates tool use
            finish_reason = choice.get("finish_reason", "")
            if finish_reason == "tool_calls" and tools:
                logger.info(f"Model finish_reason indicates tool_calls, but tool_calls field missing")
            
            # For GLM models or models that don't support standard tool calling,
            # try to parse tool calls from reasoning_content or content
            if tools and ("reasoning_content" in message or "content" in message):
                reasoning = message.get("reasoning_content", "")
                content = message.get("content", "")
                combined_text = (reasoning + "\n" + content).strip()
                
                # Try to extract tool call intent from text
                # This is a fallback for models that don't support tool_calls format
                tool_call_match = self._parse_tool_call_from_text(combined_text, tools)
                if tool_call_match:
                    tool_name = tool_call_match.get("function", {}).get("name", "unknown")
                    logger.info(f"Parsed tool call from text: {tool_name}")
                    return {
                        "type": "tool_calls",
                        "tool_calls": [tool_call_match],
                        "content": content
                    }
            
            # Log when tool_calls is missing but tools were provided
            if tools:
                logger.debug(f"Tools were provided but model returned text response. Message keys: {list(message.keys())}, finish_reason: {finish_reason}")
            
            # Regular text response
            content = message.get("content", "").strip() if "content" in message else ""
            if not content and "text" in choice:
                content = choice["text"].strip()
            
            return {
                "type": "text",
                "content": content
            }
        
        logger.error(f"Unexpected API response format: {result}")
        raise RuntimeError("Unexpected API response format")
    
    async def _chat_completion_non_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        top_p: Optional[float],
        top_k: Optional[int],
        tools: Optional[List[Dict[str, Any]]],
        thread_pool=None,
        **kwargs
    ) -> Dict[str, Any]:
        """Handle non-streaming chat completion."""
        client = await self._get_client()
        
        # Prepare request payload
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        # Add optional parameters
        if top_p is not None:
            payload["top_p"] = top_p
        if top_k is not None:
            payload["top_k"] = top_k
        
        # Add tools if provided
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        
        # Add any additional parameters
        payload.update(kwargs)
        
        try:
            endpoint = "/chat/completions"
            logger.debug(f"Calling LLM API (non-stream): {self.base_url}{endpoint}, model={self.model_name}")
            
            # Async HTTP request (stays in event loop)
            response = await client.post(endpoint, json=payload)
            response.raise_for_status()
            
            # Parse JSON response (can be blocking, run in thread pool if provided)
            if thread_pool:
                # Run JSON parsing in thread pool to avoid blocking event loop
                result = await thread_pool.run_in_executor(
                    lambda: response.json()
                )
                # Parse response structure in thread pool
                return await thread_pool.run_in_executor(
                    self._parse_response_sync,
                    result,
                    tools
                )
            else:
                # Fallback: parse synchronously (may block event loop)
                result = response.json()
                return self._parse_response_sync(result, tools)
            
        except httpx.HTTPStatusError as e:
            error_text = e.response.text if e.response else str(e)
            logger.error(f"LLM API HTTP error: {e.response.status_code} - {error_text}")
            raise RuntimeError(f"LLM API error: {e.response.status_code} - {error_text}")
        except Exception as e:
            logger.error(f"LLM API call failed: {e}", exc_info=True)
            raise

