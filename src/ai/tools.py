"""Built-in tools for AI to interact with OneBot API."""

import httpx
import re
import asyncio
import base64
import os
import hashlib
import hmac
import time
import json
from typing import Dict, Any, List, Optional
from ..core.logger import get_logger
from ..core.app import get_app

logger = get_logger(__name__)


class AITools:
    """Built-in tools that AI can use."""
    
    # Define all available tools with metadata
    ALL_TOOLS = {
        "set_group_ban": {
            "name": "set_group_ban",
            "description": "禁言群成员。将指定用户禁言指定时长（单位：秒），0表示解除禁言。",
            "category": "群管理",
            "dangerous": True,
            "function": {
                "type": "function",
                "function": {
                    "name": "set_group_ban",
                    "description": "禁言群成员。将指定用户禁言指定时长（单位：秒），0表示解除禁言。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "group_id": {
                                "type": "string",
                                "description": "群号"
                            },
                            "user_id": {
                                "type": "string",
                                "description": "要禁言的用户QQ号"
                            },
                            "duration": {
                                "type": "integer",
                                "description": "禁言时长（秒），0表示解除禁言。最大30天（2592000秒）",
                                "minimum": 0,
                                "maximum": 2592000
                            }
                        },
                        "required": ["group_id", "user_id", "duration"]
                    }
                }
            }
        },
        "set_group_kick": {
            "name": "set_group_kick",
            "description": "踢出群成员。将指定用户踢出群，可选择是否拒绝其再次申请加入。",
            "category": "群管理",
            "dangerous": True,
            "function": {
                "type": "function",
                "function": {
                    "name": "set_group_kick",
                    "description": "踢出群成员。将指定用户踢出群，可选择是否拒绝其再次申请加入。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "group_id": {
                                "type": "string",
                                "description": "群号"
                            },
                            "user_id": {
                                "type": "string",
                                "description": "要踢出的用户QQ号"
                            },
                            "reject_add_request": {
                                "type": "boolean",
                                "description": "是否拒绝该用户的加群请求（默认false）"
                            }
                        },
                        "required": ["group_id", "user_id"]
                    }
                }
            }
        },
        "set_group_admin": {
            "name": "set_group_admin",
            "description": "设置群管理员。设置或取消指定用户的群管理员身份。",
            "category": "群管理",
            "dangerous": True,
            "function": {
                "type": "function",
                "function": {
                    "name": "set_group_admin",
                    "description": "设置群管理员。设置或取消指定用户的群管理员身份。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "group_id": {
                                "type": "string",
                                "description": "群号"
                            },
                            "user_id": {
                                "type": "string",
                                "description": "用户QQ号"
                            },
                            "enable": {
                                "type": "boolean",
                                "description": "true设置为管理员，false取消管理员"
                            }
                        },
                        "required": ["group_id", "user_id", "enable"]
                    }
                }
            }
        },
        "set_group_whole_ban": {
            "name": "set_group_whole_ban",
            "description": "全员禁言。开启或关闭群全员禁言。",
            "category": "群管理",
            "dangerous": True,
            "function": {
                "type": "function",
                "function": {
                    "name": "set_group_whole_ban",
                    "description": "全员禁言。开启或关闭群全员禁言。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "group_id": {
                                "type": "string",
                                "description": "群号"
                            },
                            "enable": {
                                "type": "boolean",
                                "description": "true开启全员禁言，false关闭全员禁言"
                            }
                        },
                        "required": ["group_id", "enable"]
                    }
                }
            }
        },
        "send_group_message": {
            "name": "send_group_message",
            "description": "【特殊用途】发送群消息，仅用于：1) 需要@（艾特）用户时；2) 需要引用/回复某条消息时；3) 给其他群发送消息时。注意：正常对话回复不要使用此工具，直接返回文本即可，系统会自动发送。",
            "category": "消息发送",
            "dangerous": False,
            "function": {
                "type": "function",
                "function": {
                    "name": "send_group_message",
                    "description": "【特殊用途工具】发送群消息，仅用于以下场景：1) 需要@（艾特）特定用户时（使用at_user_ids参数）；2) 需要引用/回复某条消息时（使用reply_to_message_id参数）；3) 给其他群发送消息时（指定不同的group_id）。\n\n[重要] 正常对话回复不要使用此工具！直接返回文本内容即可，系统会自动将你的文本回复发送到当前群。只有在需要@用户、回复消息、或跨群发送时，才使用此工具。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "group_id": {
                                "type": "string",
                                "description": "群号"
                            },
                            "message": {
                                "type": "string",
                                "description": "要发送的消息内容"
                            },
                            "at_user_ids": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                },
                                "description": "可选。要艾特的用户QQ号列表，可以传入多个用户ID。只在群消息中有效。"
                            },
                            "reply_to_message_id": {
                                "type": "string",
                                "description": "可选。要回复的消息ID。如果提供，消息将以回复形式发送。"
                            }
                        },
                        "required": ["group_id", "message"]
                    }
                }
            }
        },
        "send_private_message": {
            "name": "send_private_message",
            "description": "【特殊用途】发送私聊消息，仅用于：1) 需要引用/回复某条私聊消息时；2) 主动给其他用户发送私聊消息时。注意：正常对话回复不要使用此工具，直接返回文本即可，系统会自动发送。",
            "category": "消息发送",
            "dangerous": False,
            "function": {
                "type": "function",
                "function": {
                    "name": "send_private_message",
                    "description": "【特殊用途工具】发送私聊消息，仅用于以下场景：1) 需要引用/回复某条私聊消息时（使用reply_to_message_id参数）；2) 主动给其他用户发送私聊消息时（指定不同的user_id）。\n\n[重要] 正常对话回复不要使用此工具！直接返回文本内容即可，系统会自动将你的文本回复发送给当前用户。只有在需要回复消息或主动发送给其他用户时，才使用此工具。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_id": {
                                "type": "string",
                                "description": "用户QQ号"
                            },
                            "message": {
                                "type": "string",
                                "description": "要发送的消息内容"
                            },
                            "reply_to_message_id": {
                                "type": "string",
                                "description": "可选。要回复的消息ID。如果提供，消息将以回复形式发送。"
                            }
                        },
                        "required": ["user_id", "message"]
                    }
                }
            }
        },
        "get_group_info": {
            "name": "get_group_info",
            "description": "获取群信息。获取指定群的详细信息。",
            "category": "信息查询",
            "dangerous": False,
            "function": {
                "type": "function",
                "function": {
                    "name": "get_group_info",
                    "description": "获取群信息。获取指定群的详细信息。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "group_id": {
                                "type": "string",
                                "description": "群号"
                            }
                        },
                        "required": ["group_id"]
                    }
                }
            }
        },
        "get_group_member_list": {
            "name": "get_group_member_list",
            "description": "获取群成员列表。获取指定群的所有成员信息。",
            "category": "信息查询",
            "dangerous": False,
            "function": {
                "type": "function",
                "function": {
                    "name": "get_group_member_list",
                    "description": "获取群成员列表。获取指定群的所有成员信息。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "group_id": {
                                "type": "string",
                                "description": "群号"
                            }
                        },
                        "required": ["group_id"]
                    }
                }
            }
        },
        "get_group_member_info": {
            "name": "get_group_member_info",
            "description": "获取群成员信息。获取指定群中指定成员的详细信息。",
            "category": "信息查询",
            "dangerous": False,
            "function": {
                "type": "function",
                "function": {
                    "name": "get_group_member_info",
                    "description": "获取群成员信息。获取指定群中指定成员的详细信息。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "group_id": {
                                "type": "string",
                                "description": "群号"
                            },
                            "user_id": {
                                "type": "string",
                                "description": "用户QQ号"
                            }
                        },
                        "required": ["group_id", "user_id"]
                    }
                }
            }
        },
        "delete_message": {
            "name": "delete_message",
            "description": "撤回消息。撤回指定消息ID的消息。",
            "category": "消息管理",
            "dangerous": False,
            "function": {
                "type": "function",
                "function": {
                    "name": "delete_message",
                    "description": "撤回消息。撤回指定消息ID的消息。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "message_id": {
                                "type": "string",
                                "description": "消息ID"
                            }
                        },
                        "required": ["message_id"]
                    }
                }
            }
        },
        "browse_webpage": {
            "name": "browse_webpage",
            "description": "访问网页并获取内容。可以访问用户提供的URL，获取网页的文本内容、标题等信息。",
            "category": "信息查询",
            "dangerous": False,
            "function": {
                "type": "function",
                "function": {
                    "name": "browse_webpage",
                    "description": "访问网页并获取内容。可以访问用户提供的URL，获取网页的文本内容、标题等信息。支持访问任意网页，包括用户发送的链接。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "要访问的网页URL（必须以http://或https://开头）"
                            },
                            "follow_redirects": {
                                "type": "boolean",
                                "description": "是否跟随重定向（默认true）"
                            }
                        },
                        "required": ["url"]
                    }
                }
            }
        },
        "search_web_bing": {
            "name": "search_web_bing",
            "description": "使用必应(Bing)搜索引擎进行联网搜索，获取最新的网络信息。返回搜索结果的标题、摘要和链接。适合搜索最新新闻、技术信息、常识问题等。",
            "category": "联网搜索",
            "dangerous": False,
            "function": {
                "type": "function",
                "function": {
                    "name": "search_web_bing",
                    "description": "使用必应(Bing)搜索引擎进行联网搜索，获取最新的网络信息。返回搜索结果的标题、摘要和链接。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "搜索关键词或问题"
                            },
                            "count": {
                                "type": "integer",
                                "description": "返回结果数量，默认5条",
                                "default": 5,
                                "minimum": 1,
                                "maximum": 10
                            }
                        },
                        "required": ["query"]
                    }
                }
            }
        },
        "search_web_baidu": {
            "name": "search_web_baidu",
            "description": "使用百度搜索引擎进行联网搜索，获取最新的网络信息。返回搜索结果的标题、摘要和链接。对中文内容的搜索效果更好，适合搜索中文新闻、资讯等。",
            "category": "联网搜索",
            "dangerous": False,
            "function": {
                "type": "function",
                "function": {
                    "name": "search_web_baidu",
                    "description": "使用百度搜索引擎进行联网搜索，获取最新的网络信息。返回搜索结果的标题、摘要和链接。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "搜索关键词或问题"
                            },
                            "count": {
                                "type": "integer",
                                "description": "返回结果数量，默认5条",
                                "default": 5,
                                "minimum": 1,
                                "maximum": 10
                            }
                        },
                        "required": ["query"]
                    }
                }
            }
        },
        "text_to_speech": {
            "name": "text_to_speech",
            "description": "将文本转换为语音并发送语音消息。使用腾讯云TTS服务生成高质量的女性中文语音（音色ID：601005）。",
            "category": "消息发送",
            "dangerous": False,
            "function": {
                "type": "function",
                "function": {
                    "name": "text_to_speech",
                    "description": "将文本转换为语音并发送语音消息。使用腾讯云TTS服务，音色固定为601005（亲和女声），生成高质量的女性中文语音。可以发送到群或私聊。需要先在配置中设置腾讯云API密钥（SecretId和SecretKey）。参考文档：https://cloud.tencent.com/document/api/1073/37995",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "text": {
                                "type": "string",
                                "description": "要转换为语音的文本内容（最多1000字符）"
                            },
                            "message_type": {
                                "type": "string",
                                "enum": ["group", "private"],
                                "description": "消息类型：'group'发送到群，'private'发送到私聊"
                            },
                            "target_id": {
                                "type": "string",
                                "description": "目标ID：群号（如果message_type是group）或用户QQ号（如果message_type是private）"
                            },
                            "voice_type": {
                                "type": "integer",
                                "description": "音色ID。必须使用601005（亲和女声）。这是唯一支持的女性真实声音音色。",
                                "default": 601005
                            },
                            "codec": {
                                "type": "string",
                                "enum": ["wav", "mp3", "pcm"],
                                "description": "返回音频格式：wav（默认）、mp3、pcm。",
                                "default": "wav"
                            },
                            "sample_rate": {
                                "type": "integer",
                                "enum": [8000, 16000, 24000],
                                "description": "音频采样率：8000（8k）、16000（16k-默认）、24000（24k，部分音色支持）。",
                                "default": 16000
                            },
                            "speed": {
                                "type": "number",
                                "description": "语速，范围[-2, 6]：-2代表0.6倍、-1代表0.8倍、0代表1.0倍（默认）、1代表1.2倍、2代表1.5倍、6代表2.5倍。可以保留小数点后2位，如0.5/1.25/2.81等。",
                                "default": 0,
                                "minimum": -2,
                                "maximum": 6
                            },
                            "volume": {
                                "type": "number",
                                "description": "音量大小，范围[-10, 10]：0代表正常音量（默认），值越大音量越高。",
                                "default": 0,
                                "minimum": -10,
                                "maximum": 10
                            }
                        },
                        "required": ["text", "message_type", "target_id"]
                    }
                }
            }
        }
    }
    
    @staticmethod
    def get_tools(enabled_tools: Optional[Dict[str, bool]] = None) -> List[Dict[str, Any]]:
        """Get list of available tools in OpenAI function calling format.
        
        Args:
            enabled_tools: Dict mapping tool names to enabled status.
                          If None, all tools are enabled by default.
                          If provided, only enabled tools are returned.
        """
        if enabled_tools is None:
            # Default: all tools enabled
            enabled_tools = {name: True for name in AITools.ALL_TOOLS.keys()}
        
        tools = []
        for tool_name, tool_def in AITools.ALL_TOOLS.items():
            if enabled_tools.get(tool_name, True):  # Default to enabled if not specified
                tools.append(tool_def["function"])
        
        return tools
    
    @staticmethod
    def get_all_tools_metadata() -> List[Dict[str, Any]]:
        """Get metadata for all tools (for UI display)."""
        return [
            {
                "name": tool_name,
                "description": tool_def["description"],
                "category": tool_def["category"],
                "dangerous": tool_def.get("dangerous", False)
            }
            for tool_name, tool_def in AITools.ALL_TOOLS.items()
        ]
    
    @staticmethod
    async def _call_tencent_tts(
        text: str, 
        voice_type: str, 
        secret_id: str, 
        secret_key: str,
        codec: str = "wav",
        sample_rate: int = 16000,
        speed: float = 0,
        volume: float = 0
    ) -> Optional[bytes]:
        """Call Tencent Cloud TTS API to generate speech.
        
        Args:
            text: Text to convert to speech
            voice_type: Voice type (e.g., zh_female_shuangkuaisisiqin)
            secret_id: Tencent Cloud SecretId
            secret_key: Tencent Cloud SecretKey
            
        Returns:
            Audio data as bytes, or None if failed
        """
        try:
            import urllib.parse
            from urllib.parse import quote, urlencode
            
            # Tencent Cloud TTS API endpoint
            endpoint = "tts.tencentcloudapi.com"
            service = "tts"
            version = "2019-08-23"
            action = "TextToVoice"
            region = "ap-beijing"  # 可以根据需要修改区域
            
            # VoiceType必须是601005（根据用户要求）
            voice_type_int = 601005
            
            # Prepare request parameters (Tencent Cloud TTS API uses JSON body)
            # Action, Version, Region are in headers, not body
            params = {
                "Text": text,
                "SessionId": f"tts_{int(time.time())}",  # Unique session ID
                "ModelType": 1,  # 1: 基础音色, 2: 精品音色
                "VoiceType": voice_type_int,
                "Codec": codec,  # Audio format: wav or mp3
                "Speed": speed,  # Speed: -2 to 2, 0 is normal
                "Volume": volume,  # Volume: -6 to 6, 0 is normal
                "SampleRate": sample_rate,  # Sample rate: 8000, 16000, 24000, 48000
            }
            
            # For POST requests, parameters go in the request body, not query string
            # Build string to sign
            host = endpoint
            request_method = "POST"
            canonical_uri = "/"
            canonical_query_string = ""  # Empty for POST requests
            content_type = "application/json"
            # SignedHeaders must include 'host' and 'content-type' according to Tencent Cloud API requirements
            canonical_headers = f"content-type:{content_type}\nhost:{host}\n"
            signed_headers = "content-type;host"
            # Hash the request body (JSON) - must match the actual request body
            request_body_for_hash = json.dumps(params, ensure_ascii=False, separators=(',', ':'))
            hashed_request_payload = hashlib.sha256(request_body_for_hash.encode('utf-8')).hexdigest()
            
            canonical_request = f"{request_method}\n{canonical_uri}\n{canonical_query_string}\n{canonical_headers}\n{signed_headers}\n{hashed_request_payload}"
            
            # Create signature
            algorithm = "TC3-HMAC-SHA256"
            timestamp = int(time.time())
            date = time.strftime("%Y-%m-%d", time.gmtime(timestamp))
            
            # Calculate signature
            secret_date = hmac.new(f"TC3{secret_key}".encode(), date.encode(), hashlib.sha256).digest()
            secret_service = hmac.new(secret_date, service.encode(), hashlib.sha256).digest()
            secret_signing = hmac.new(secret_service, "tc3_request".encode(), hashlib.sha256).digest()
            signature = hmac.new(secret_signing, canonical_request.encode(), hashlib.sha256).hexdigest()
            
            # Build authorization header
            authorization = (
                f"{algorithm} "
                f"Credential={secret_id}/{date}/{service}/tc3_request, "
                f"SignedHeaders={signed_headers}, "
                f"Signature={signature}"
            )
            
            # Build request headers
            headers = {
                "Authorization": authorization,
                "Content-Type": "application/json",
                "Host": host,
                "X-TC-Action": action,
                "X-TC-Timestamp": str(timestamp),
                "X-TC-Version": version,
                "X-TC-Region": region,
            }
            
            # Build request body (must match the one used in signature calculation)
            request_body = json.dumps(params, ensure_ascii=False, separators=(',', ':'))
            
            # Make API request
            url = f"https://{endpoint}"
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, headers=headers, content=request_body)
                response.raise_for_status()
                
                result = response.json()
                
                # Check response
                if result.get("Response", {}).get("Error"):
                    error_info = result["Response"]["Error"]
                    logger.error(f"Tencent Cloud TTS API error: {error_info}")
                    return None
                
                # Get audio data (base64 encoded)
                audio_base64 = result.get("Response", {}).get("Audio")
                if not audio_base64:
                    logger.error("No audio data in TTS response")
                    return None
                
                # Decode base64 audio
                audio_data = base64.b64decode(audio_base64)
                logger.info(f"TTS generated audio: {len(audio_data)} bytes")
                
                return audio_data
                
        except Exception as e:
            logger.error(f"Error calling Tencent Cloud TTS API: {e}", exc_info=True)
            return None
    
    @staticmethod
    def _format_api_error(error_msg: str) -> str:
        """Format API error message to be more user-friendly."""
        # Map common error codes to friendly messages
        error_map = {
            "ERR_NOT_GROUP_ADMIN": "操作失败：机器人不是群管理员，无法执行此操作",
            "ERR_NOT_GROUP_OWNER": "操作失败：机器人不是群主，无法执行此操作",
            "ERR_GROUP_NOT_FOUND": "操作失败：群组不存在",
            "ERR_USER_NOT_FOUND": "操作失败：用户不存在",
            "ERR_PERMISSION_DENIED": "操作失败：权限不足",
            "ERR_INVALID_PARAM": "操作失败：参数错误",
            "ERR_RATE_LIMITED": "操作失败：操作过于频繁，请稍后再试",
        }
        
        # Try to extract error code from error message
        for error_code, friendly_msg in error_map.items():
            if error_code in error_msg:
                return friendly_msg
        
        # If no specific error code found, try to extract error message
        # Format: "API call failed: {'status': 'failed', 'message': 'ERR_XXX', ...}"
        match = re.search(r"'message':\s*['\"]([^'\"]+)['\"]", error_msg)
        if match:
            error_code = match.group(1)
            if error_code in error_map:
                return error_map[error_code]
            return f"操作失败：{error_code}"
        
        # Fallback to original error message (simplified)
        if "API call failed" in error_msg:
            return "操作失败：API调用失败，请检查权限和参数"
        return f"操作失败：{error_msg}"
    
    @staticmethod
    async def call_tool(
        tool_name: str,
        arguments: Dict[str, Any],
        user_qq: Optional[str] = None,
        chat_type: Optional[str] = None,
        chat_id: Optional[str] = None,
        user_nickname: Optional[str] = None,
        llm_client: Optional[Any] = None,
        skip_permission_check: bool = False
    ) -> Dict[str, Any]:
        """Call a built-in tool with permission checking.
        
        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments
            user_qq: User QQ number (for permission check)
            chat_type: 'group' or 'private' (for permission check)
            chat_id: Group ID or QQ number (for permission check)
            user_nickname: User nickname (for audit log)
            llm_client: LLM client (for AI approval)
            skip_permission_check: Skip permission check (for internal use)
            
        Returns:
            Tool execution result
        """
        try:
            # Check tool permission (unless skipped)
            if not skip_permission_check and user_qq:
                from .tool_permission_manager import get_tool_permission_manager
                
                tool_perm_mgr = get_tool_permission_manager()
                approved, reason, log_id = await tool_perm_mgr.check_tool_permission(
                    tool_name=tool_name,
                    user_qq=user_qq,
                    tool_args=arguments,
                    chat_type=chat_type or 'unknown',
                    chat_id=chat_id or 'unknown',
                    user_nickname=user_nickname,
                    llm_client=llm_client
                )
                
                if not approved:
                    logger.warning(f"Tool {tool_name} rejected: {reason}")
                    return {
                        "success": False,
                        "error": f"权限不足: {reason}",
                        "permission_denied": True,
                        "log_id": log_id
                    }
                
                # Store log_id for later execution tracking
                if log_id:
                    arguments['_permission_log_id'] = log_id
            
            app = get_app()
            if not app or not hasattr(app, 'onebot_adapter'):
                return {"success": False, "error": "OneBot adapter not available"}
            
            onebot = app.onebot_adapter
            
            if tool_name == "set_group_ban":
                group_id = str(arguments.get("group_id", ""))
                user_id = str(arguments.get("user_id", ""))
                duration = int(arguments.get("duration", 0))
                
                logger.info(f"Calling set_group_ban: group_id={group_id}, user_id={user_id}, duration={duration}")
                
                try:
                    result = await onebot.call_api(
                        "set_group_ban",
                        {
                            "group_id": int(group_id),
                            "user_id": int(user_id),
                            "duration": duration
                        }
                    )
                    
                    return {
                        "success": True,
                        "result": result,
                        "message": f"已{'禁言' if duration > 0 else '解除禁言'}用户 {user_id}，时长 {duration} 秒" if duration > 0 else f"已解除用户 {user_id} 的禁言"
                    }
                except RuntimeError as e:
                    # Format error message to be more user-friendly
                    error_msg = AITools._format_api_error(str(e))
                    return {
                        "success": False,
                        "error": error_msg
                    }
            
            elif tool_name == "send_group_message":
                group_id = str(arguments.get("group_id", ""))
                message = str(arguments.get("message", ""))
                at_user_ids = arguments.get("at_user_ids", [])  # List of user IDs to @
                reply_to_message_id = arguments.get("reply_to_message_id")  # Optional reply ID
                
                # Validate required parameters
                if not group_id:
                    return {
                        "success": False,
                        "error": "group_id参数缺失，无法发送群消息"
                    }
                if not message:
                    return {
                        "success": False,
                        "error": "message参数缺失，无法发送空消息"
                    }
                
                logger.info(f"Calling send_group_message: group_id={group_id}, at_users={at_user_ids}, reply_to={reply_to_message_id}")
                
                # Build message with @ mentions and reply if needed
                from ..protocol.base import MessageSegment
                message_segments = []
                
                # Add reply segment if provided
                if reply_to_message_id:
                    message_segments.append(MessageSegment.reply(str(reply_to_message_id)))
                
                # Add @ mentions if provided
                if at_user_ids:
                    for user_id in at_user_ids:
                        if user_id:
                            message_segments.append(MessageSegment.at(str(user_id)))
                
                # Add text message
                message_segments.append(MessageSegment.text(message))
                
                # Send message
                result = await onebot.send_message(group_id, message_segments, "group")
                
                return {
                    "success": True,
                    "result": result,
                    "message": f"消息已发送到群 {group_id}" + (f"，已艾特 {len(at_user_ids)} 个用户" if at_user_ids else "") + (f"，已回复消息 {reply_to_message_id}" if reply_to_message_id else ""),
                    "message_id": result.get("message_id") if result else None
                }
            
            elif tool_name == "send_private_message":
                user_id = str(arguments.get("user_id", ""))
                message = str(arguments.get("message", ""))
                reply_to_message_id = arguments.get("reply_to_message_id")  # Optional reply ID
                
                logger.info(f"Calling send_private_message: user_id={user_id}, reply_to={reply_to_message_id}")
                
                # Build message with reply if needed
                from ..protocol.base import MessageSegment
                message_segments = []
                
                # Add reply segment if provided
                if reply_to_message_id:
                    message_segments.append(MessageSegment.reply(str(reply_to_message_id)))
                
                # Add text message
                message_segments.append(MessageSegment.text(message))
                
                # Send message
                result = await onebot.send_message(user_id, message_segments, "private")
                
                return {
                    "success": True,
                    "result": result,
                    "message": f"消息已发送给用户 {user_id}" + (f"，已回复消息 {reply_to_message_id}" if reply_to_message_id else ""),
                    "message_id": result.get("message_id") if result else None
                }
            
            elif tool_name == "set_group_kick":
                group_id = str(arguments.get("group_id", ""))
                user_id = str(arguments.get("user_id", ""))
                reject_add_request = arguments.get("reject_add_request", False)
                
                logger.info(f"Calling set_group_kick: group_id={group_id}, user_id={user_id}")
                
                result = await onebot.call_api(
                    "set_group_kick",
                    {
                        "group_id": int(group_id),
                        "user_id": int(user_id),
                        "reject_add_request": reject_add_request
                    }
                )
                
                return {
                    "success": True,
                    "result": result,
                    "message": f"已将用户 {user_id} 踢出群 {group_id}"
                }
            
            elif tool_name == "set_group_admin":
                group_id = str(arguments.get("group_id", ""))
                user_id = str(arguments.get("user_id", ""))
                enable = arguments.get("enable", True)
                
                logger.info(f"Calling set_group_admin: group_id={group_id}, user_id={user_id}, enable={enable}")
                
                result = await onebot.call_api(
                    "set_group_admin",
                    {
                        "group_id": int(group_id),
                        "user_id": int(user_id),
                        "enable": enable
                    }
                )
                
                return {
                    "success": True,
                    "result": result,
                    "message": f"{'设置' if enable else '取消'}用户 {user_id} 为群 {group_id} 的管理员"
                }
            
            elif tool_name == "set_group_whole_ban":
                group_id = str(arguments.get("group_id", ""))
                enable = arguments.get("enable", True)
                
                logger.info(f"Calling set_group_whole_ban: group_id={group_id}, enable={enable}")
                
                result = await onebot.call_api(
                    "set_group_whole_ban",
                    {
                        "group_id": int(group_id),
                        "enable": enable
                    }
                )
                
                return {
                    "success": True,
                    "result": result,
                    "message": f"{'开启' if enable else '关闭'}群 {group_id} 的全员禁言"
                }
            
            elif tool_name == "get_group_info":
                group_id = str(arguments.get("group_id", ""))
                
                logger.info(f"Calling get_group_info: group_id={group_id}")
                
                result = await onebot.call_api(
                    "get_group_info",
                    {
                        "group_id": int(group_id)
                    }
                )
                
                return {
                    "success": True,
                    "result": result,
                    "message": f"已获取群 {group_id} 的信息"
                }
            
            elif tool_name == "get_group_member_list":
                group_id = str(arguments.get("group_id", ""))
                
                logger.info(f"Calling get_group_member_list: group_id={group_id}")
                
                result = await onebot.call_api(
                    "get_group_member_list",
                    {
                        "group_id": int(group_id)
                    }
                )
                
                member_count = len(result) if isinstance(result, list) else 0
                
                return {
                    "success": True,
                    "result": result,
                    "message": f"群 {group_id} 共有 {member_count} 名成员"
                }
            
            elif tool_name == "get_group_member_info":
                group_id = str(arguments.get("group_id", ""))
                user_id = str(arguments.get("user_id", ""))
                
                logger.info(f"Calling get_group_member_info: group_id={group_id}, user_id={user_id}")
                
                result = await onebot.call_api(
                    "get_group_member_info",
                    {
                        "group_id": int(group_id),
                        "user_id": int(user_id)
                    }
                )
                
                return {
                    "success": True,
                    "result": result,
                    "message": f"已获取群 {group_id} 中用户 {user_id} 的信息"
                }
            
            elif tool_name == "delete_message":
                message_id = str(arguments.get("message_id", ""))
                
                logger.info(f"Calling delete_message: message_id={message_id}")
                
                try:
                    result = await onebot.delete_message(message_id)
                    
                    return {
                        "success": result,
                        "result": {"deleted": result},
                        "message": f"{'已撤回' if result else '撤回失败'}消息 {message_id}"
                    }
                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"Failed to delete message | error={error_msg}", exc_info=True)
                    return {
                        "success": False,
                        "error": f"撤回消息失败: {error_msg}",
                        "message": f"撤回失败: {error_msg}"
                    }
            
            elif tool_name == "browse_webpage":
                url = str(arguments.get("url", ""))
                follow_redirects = arguments.get("follow_redirects", True)
                
                logger.info(f"Calling browse_webpage: url={url}")
                
                # Validate URL
                if not url.startswith(("http://", "https://")):
                    return {
                        "success": False,
                        "error": "URL必须以http://或https://开头"
                    }
                
                try:
                    # Fetch webpage content
                    async with httpx.AsyncClient(follow_redirects=follow_redirects, timeout=30.0) as client:
                        headers = {
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                        }
                        response = await client.get(url, headers=headers)
                        response.raise_for_status()
                        
                        content = response.text
                        
                        # Extract title if HTML
                        title = ""
                        if content.strip().startswith("<"):
                            title_match = re.search(r'<title[^>]*>([^<]+)</title>', content, re.IGNORECASE)
                            if title_match:
                                title = title_match.group(1).strip()
                            
                            # Extract text content (simple extraction)
                            # Remove script and style tags
                            content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
                            content = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL | re.IGNORECASE)
                            # Extract text from tags
                            content = re.sub(r'<[^>]+>', ' ', content)
                            # Clean up whitespace
                            content = re.sub(r'\s+', ' ', content).strip()
                        
                        # Limit content length
                        max_length = 10000
                        if len(content) > max_length:
                            content = content[:max_length] + "... (内容已截断)"
                        
                        result_data = {
                            "url": url,
                            "title": title,
                            "content": content,
                            "status_code": response.status_code,
                            "content_length": len(content)
                        }
                        
                        return {
                            "success": True,
                            "result": result_data,
                            "message": f"成功访问网页: {url}\n标题: {title}\n内容长度: {len(content)}字符"
                        }
                
                except httpx.HTTPStatusError as e:
                    return {
                        "success": False,
                        "error": f"HTTP错误: {e.response.status_code} - {e.response.reason_phrase}"
                    }
                except httpx.TimeoutException:
                    return {
                        "success": False,
                        "error": "请求超时，请稍后重试"
                    }
                except Exception as e:
                    logger.error(f"Error browsing webpage: {e}", exc_info=True)
                    return {
                        "success": False,
                        "error": f"访问网页时出错: {str(e)}"
                    }
            
            elif tool_name == "search_web_bing":
                query = str(arguments.get("query", ""))
                count = int(arguments.get("count", 5))
                
                logger.info(f"Calling search_web_bing: query={query}, count={count}")
                
                try:
                    import urllib.parse
                    import random
                    
                    search_url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}&count={count}"
                    
                    # More realistic browser headers to avoid anti-crawler
                    user_agents = [
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    ]
                    
                    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                        headers = {
                            "User-Agent": random.choice(user_agents),
                            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
                            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
                            "Accept-Encoding": "gzip, deflate, br",
                            "Referer": "https://www.bing.com/",
                            "Origin": "https://www.bing.com",
                            "Connection": "keep-alive",
                            "Upgrade-Insecure-Requests": "1",
                            "Sec-Fetch-Dest": "document",
                            "Sec-Fetch-Mode": "navigate",
                            "Sec-Fetch-Site": "same-origin",
                            "Sec-Fetch-User": "?1",
                            "Cache-Control": "max-age=0"
                        }
                        
                        # Add small random delay to appear more human-like
                        await asyncio.sleep(random.uniform(0.5, 1.5))
                        
                        response = await client.get(search_url, headers=headers)
                        response.raise_for_status()
                        
                        html = response.text
                        results = []
                        
                        # Try multiple patterns to extract search results
                        # Pattern 1: Standard Bing result format
                        result_pattern = r'<li class="b_algo"[^>]*>.*?<h2><a[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?<p[^>]*>(.*?)</p>'
                        matches = re.findall(result_pattern, html, re.DOTALL | re.IGNORECASE)
                        
                        if not matches:
                            # Pattern 2: Alternative format
                            result_pattern = r'<h2><a[^>]*href="([^"]+)"[^>]*>(.*?)</a></h2>.*?<p[^>]*>(.*?)</p>'
                            matches = re.findall(result_pattern, html, re.DOTALL | re.IGNORECASE)
                        
                        if not matches:
                            # Pattern 3: More flexible pattern
                            result_pattern = r'href="([^"]+)"[^>]*><h2[^>]*>(.*?)</h2>.*?<p[^>]*>(.*?)</p>'
                            matches = re.findall(result_pattern, html, re.DOTALL | re.IGNORECASE)
                        
                        for url_match, title, snippet in matches[:count]:
                            title = re.sub(r'<[^>]+>', '', title).strip()
                            snippet = re.sub(r'<[^>]+>', '', snippet).strip()
                            snippet = re.sub(r'\s+', ' ', snippet)
                            
                            # Clean up title and snippet
                            title = title.replace('\n', ' ').strip()
                            snippet = snippet.replace('\n', ' ').strip()
                            
                            if url_match and title:
                                results.append({
                                    "title": title,
                                    "url": url_match,
                                    "snippet": snippet[:200] if snippet else ""
                                })
                        
                        if not results:
                            return {"success": False, "error": "未找到搜索结果，可能被反爬虫拦截或页面结构已变化"}
                        
                        return {
                            "success": True,
                            "query": query,
                            "count": len(results),
                            "results": results,
                            "message": f"找到 {len(results)} 条必应搜索结果"
                        }
                        
                except httpx.HTTPStatusError as e:
                    logger.error(f"Bing search HTTP error: {e.response.status_code}")
                    return {"success": False, "error": f"搜索请求被拒绝: HTTP {e.response.status_code}"}
                except Exception as e:
                    logger.error(f"Bing search error: {e}", exc_info=True)
                    return {"success": False, "error": f"搜索失败: {str(e)}"}
            
            elif tool_name == "search_web_baidu":
                query = str(arguments.get("query", ""))
                count = int(arguments.get("count", 5))
                
                logger.info(f"Calling search_web_baidu: query={query}, count={count}")
                
                try:
                    import urllib.parse
                    import random
                    
                    search_url = f"https://www.baidu.com/s?wd={urllib.parse.quote(query)}&rn={count}"
                    
                    # More realistic browser headers to avoid anti-crawler
                    user_agents = [
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    ]
                    
                    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                        headers = {
                            "User-Agent": random.choice(user_agents),
                            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
                            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
                            "Accept-Encoding": "gzip, deflate, br",
                            "Referer": "https://www.baidu.com/",
                            "Origin": "https://www.baidu.com",
                            "Connection": "keep-alive",
                            "Upgrade-Insecure-Requests": "1",
                            "Sec-Fetch-Dest": "document",
                            "Sec-Fetch-Mode": "navigate",
                            "Sec-Fetch-Site": "same-origin",
                            "Sec-Fetch-User": "?1",
                            "Cache-Control": "max-age=0"
                        }
                        
                        # Add small random delay to appear more human-like
                        await asyncio.sleep(random.uniform(0.5, 1.5))
                        
                        response = await client.get(search_url, headers=headers)
                        response.raise_for_status()
                        
                        html = response.text
                        results = []
                        
                        # Try multiple patterns to extract Baidu search results
                        # Pattern 1: Standard Baidu result format with class "result"
                        result_pattern = r'<div[^>]*class="[^"]*result[^"]*"[^>]*>.*?<h3[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>([^<]+)</a>.*?<span[^>]*class="[^"]*content-right[^"]*"[^>]*>.*?<span[^>]*>(.*?)</span>'
                        matches = re.findall(result_pattern, html, re.DOTALL | re.IGNORECASE)
                        
                        if not matches:
                            # Pattern 2: Alternative format with c-abstract
                            result_pattern = r'<h3[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>([^<]+)</a></h3>.*?<span[^>]*class="[^"]*c-abstract[^"]*"[^>]*>(.*?)</span>'
                            matches = re.findall(result_pattern, html, re.DOTALL | re.IGNORECASE)
                        
                        if not matches:
                            # Pattern 3: More flexible pattern
                            result_pattern = r'<h3[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>(.*?)</a></h3>.*?<span[^>]*class="[^"]*[a-z-]*abstract[^"]*"[^>]*>(.*?)</span>'
                            matches = re.findall(result_pattern, html, re.DOTALL | re.IGNORECASE)
                        
                        for url_match, title, snippet in matches[:count]:
                            title = re.sub(r'<[^>]+>', '', title).strip()
                            snippet = re.sub(r'<[^>]+>', '', snippet).strip()
                            snippet = re.sub(r'\s+', ' ', snippet)
                            
                            # Clean up title and snippet
                            title = title.replace('\n', ' ').strip()
                            snippet = snippet.replace('\n', ' ').strip()
                            
                            # Extract actual URL from Baidu's redirect link
                            if url_match.startswith('/link?url='):
                                # Try to extract real URL from Baidu redirect
                                try:
                                    real_url_match = re.search(r'url=([^&]+)', url_match)
                                    if real_url_match:
                                        import urllib.parse
                                        url_match = urllib.parse.unquote(real_url_match.group(1))
                                except:
                                    pass
                            
                            if url_match and title:
                                results.append({
                                    "title": title,
                                    "url": url_match if url_match.startswith('http') else f"https://www.baidu.com{url_match}",
                                    "snippet": snippet[:200] if snippet else ""
                                })
                        
                        if not results:
                            return {"success": False, "error": "未找到搜索结果，可能被反爬虫拦截或页面结构已变化"}
                        
                        return {
                            "success": True,
                            "query": query,
                            "count": len(results),
                            "results": results,
                            "message": f"找到 {len(results)} 条百度搜索结果"
                        }
                        
                except httpx.HTTPStatusError as e:
                    logger.error(f"Baidu search HTTP error: {e.response.status_code}")
                    return {"success": False, "error": f"搜索请求被拒绝: HTTP {e.response.status_code}"}
                except Exception as e:
                    logger.error(f"Baidu search error: {e}", exc_info=True)
                    return {"success": False, "error": f"搜索失败: {str(e)}"}
            
            elif tool_name == "text_to_speech":
                text = str(arguments.get("text", ""))
                message_type = str(arguments.get("message_type", ""))
                target_id = str(arguments.get("target_id", ""))
                # VoiceType必须是601005（根据用户要求）
                voice_type_raw = arguments.get("voice_type", 601005)
                # 转换为整数，确保是601005
                if isinstance(voice_type_raw, str) and voice_type_raw.isdigit():
                    voice_type = int(voice_type_raw)
                elif isinstance(voice_type_raw, int):
                    voice_type = voice_type_raw
                else:
                    voice_type = 601005  # 默认值
                
                # 强制使用601005
                if voice_type != 601005:
                    logger.warning(f"VoiceType {voice_type} is not 601005, forcing to 601005")
                    voice_type = 601005
                
                codec = str(arguments.get("codec", "wav"))
                sample_rate = int(arguments.get("sample_rate", 16000))
                speed = float(arguments.get("speed", 0))
                volume = float(arguments.get("volume", 0))
                
                # 参数验证（根据官方文档）
                if codec not in ["wav", "mp3", "pcm"]:
                    codec = "wav"  # 默认值
                if sample_rate not in [8000, 16000, 24000]:
                    sample_rate = 16000  # 默认值
                if speed < -2 or speed > 6:
                    speed = 0  # 默认值
                if volume < -10 or volume > 10:
                    volume = 0  # 默认值
                
                logger.info(f"Calling text_to_speech: text_length={len(text)}, message_type={message_type}, target_id={target_id}, voice_type={voice_type}")
                
                # Validate input
                if not text:
                    return {"success": False, "error": "文本内容不能为空"}
                if len(text) > 1000:
                    return {"success": False, "error": "文本内容不能超过1000字符"}
                if message_type not in ["group", "private"]:
                    return {"success": False, "error": "消息类型必须是'group'或'private'"}
                if not target_id:
                    return {"success": False, "error": "目标ID不能为空"}
                
                try:
                    # Get Tencent Cloud credentials (priority: config file > environment variable)
                    import os
                    from ..core.config import get_config_manager
                    
                    # Try to get from config file first
                    config_manager = get_config_manager()
                    config_obj = config_manager.get()
                    secret_id = config_obj.tencent_cloud_secret_id or os.getenv("TENCENT_CLOUD_SECRET_ID", "")
                    secret_key = config_obj.tencent_cloud_secret_key or os.getenv("TENCENT_CLOUD_SECRET_KEY", "")
                    
                    if not secret_id or not secret_key:
                        return {
                            "success": False,
                            "error": "未配置腾讯云API密钥。\n\n配置方法：\n1. 在系统设置页面配置（推荐）\n2. 或在系统环境变量中设置 TENCENT_CLOUD_SECRET_ID 和 TENCENT_CLOUD_SECRET_KEY\n3. 或在项目根目录创建 .env 文件，添加：\n   TENCENT_CLOUD_SECRET_ID=your_secret_id\n   TENCENT_CLOUD_SECRET_KEY=your_secret_key"
                        }
                    
                    # Try to use Tencent Cloud SDK first, fallback to manual API call
                    audio_data = None
                    try:
                        # Try using SDK (if installed)
                        from tencentcloud.common import credential
                        from tencentcloud.common.profile.client_profile import ClientProfile
                        from tencentcloud.common.profile.http_profile import HttpProfile
                        from tencentcloud.tts.v20190823 import tts_client, models
                        import json as json_lib
                        
                        # Use SDK
                        cred = credential.Credential(secret_id, secret_key)
                        http_profile = HttpProfile()
                        http_profile.endpoint = "tts.tencentcloudapi.com"
                        
                        client_profile = ClientProfile()
                        client_profile.httpProfile = http_profile
                        
                        client = tts_client.TtsClient(cred, "ap-beijing", client_profile)
                        
                        req = models.TextToVoiceRequest()
                        req.Text = text
                        req.SessionId = f"tts_{int(time.time())}"
                        req.ModelType = 1  # 基础音色
                        # VoiceType必须是601005（根据用户要求）
                        req.VoiceType = 601005
                        req.Codec = codec
                        req.Speed = speed
                        req.Volume = volume
                        req.SampleRate = sample_rate
                        
                        resp = client.TextToVoice(req)
                        audio_base64 = resp.Audio
                        audio_data = base64.b64decode(audio_base64)
                        logger.info(f"TTS generated using SDK: {len(audio_data)} bytes")
                        
                    except ImportError:
                        # SDK not installed, use manual API call
                        logger.info("Tencent Cloud SDK not found, using manual API call")
                        audio_data = await AITools._call_tencent_tts(
                            text, voice_type, secret_id, secret_key, codec, sample_rate, speed, volume
                        )
                    except Exception as e:
                        logger.warning(f"SDK call failed: {e}, trying manual API call")
                        audio_data = await AITools._call_tencent_tts(
                            text, voice_type, secret_id, secret_key, codec, sample_rate, speed, volume
                        )
                    
                    if not audio_data:
                        return {"success": False, "error": "TTS API调用失败"}
                    
                    # Save audio to temporary file
                    import tempfile
                    import uuid
                    from pathlib import Path
                    
                    # Get data directory for storing temp files
                    app = get_app()
                    if app:
                        data_dir = Path(app.config.get_data_dir()) / "temp"
                    else:
                        data_dir = Path("./data/temp")
                    data_dir.mkdir(parents=True, exist_ok=True)
                    
                    # Use appropriate file extension based on codec
                    file_extension = codec if codec in ["wav", "mp3"] else "wav"
                    audio_file = data_dir / f"tts_{uuid.uuid4().hex}.{file_extension}"
                    with open(audio_file, "wb") as f:
                        f.write(audio_data)
                    
                    logger.info(f"Saved TTS audio to: {audio_file}")
                    
                    # Send voice message via OneBot
                    from ..protocol.base import MessageSegment
                    
                    # Read audio file and encode to base64 (like Xiaoyi_QQ does)
                    # This is the most compatible way to send voice messages
                    # base64 is already imported at the top of the file
                    with open(audio_file, "rb") as f:
                        audio_data_encoded = base64.b64encode(f.read()).decode('utf-8')
                    
                    # Use base64:// protocol for sending voice (OneBot standard)
                    # Format: base64://{base64_encoded_audio_data}
                    voice_file = f"base64://{audio_data_encoded}"
                    
                    # OneBot语音消息使用record类型
                    voice_message = [MessageSegment("record", {"file": voice_file})]
                    
                    logger.info(f"Sending voice message: type=record, file=base64://... (length={len(audio_data_encoded)} chars)")
                    logger.debug(f"Message segment: {voice_message[0].to_dict()}")
                    
                    result = await onebot.send_message(target_id, voice_message, message_type)
                    logger.info(f"Voice message sent: {result}")
                    
                    # Clean up temporary file after a delay (optional)
                    # You might want to keep it for a while in case upload fails
                    
                    return {
                        "success": True,
                        "result": result,
                        "message": f"语音消息已发送到{'群' if message_type == 'group' else '用户'} {target_id}",
                        "audio_file": str(audio_file),
                        "text": text,
                        "voice_type": voice_type
                    }
                    
                except Exception as e:
                    logger.error(f"TTS error: {e}", exc_info=True)
                    return {"success": False, "error": f"TTS生成失败: {str(e)}"}
            
            else:
                result = {
                    "success": False,
                    "error": f"Unknown tool: {tool_name}"
                }
            
            # Mark tool as executed in permission log (if exists)
            if not skip_permission_check and '_permission_log_id' in arguments:
                from .tool_permission_manager import get_tool_permission_manager
                tool_perm_mgr = get_tool_permission_manager()
                log_id = arguments['_permission_log_id']
                await tool_perm_mgr.mark_tool_executed(
                    log_id=log_id,
                    success=result.get('success', False),
                    result=result.get('message') or result.get('error') or str(result)
                )
            
            return result
        
        except Exception as e:
            logger.error(f"Error calling tool {tool_name}: {e}", exc_info=True)
            
            # Mark tool as failed in permission log (if exists)
            if not skip_permission_check and '_permission_log_id' in arguments:
                from .tool_permission_manager import get_tool_permission_manager
                tool_perm_mgr = get_tool_permission_manager()
                log_id = arguments['_permission_log_id']
                await tool_perm_mgr.mark_tool_executed(
                    log_id=log_id,
                    success=False,
                    result=f"Exception: {str(e)}"
                )
            
            return {
                "success": False,
                "error": str(e)
            }

