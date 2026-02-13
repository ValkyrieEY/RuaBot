"""消息中继客户端插件 - 第三方机器人端

功能：
- 拦截所有要发送的消息
- 通过HTTP API将消息提交到官方机器人
- 官方机器人代为发送消息，突破第三方限制
"""

import asyncio
import json
import hashlib
import time
import aiohttp
import os
import sys
from typing import Dict, Any, Optional

# 导入拦截器基类
try:
    from src.plugins import MessageInterceptor, InterceptorResult
except ImportError:
    # 如果直接导入失败，尝试从父目录导入
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))
    from src.plugins import MessageInterceptor, InterceptorResult


class MessageRelayInterceptor(MessageInterceptor):
    """消息拦截器 - 拦截所有发送的消息并通过官方机器人转发"""
    
    def __init__(self, plugin_id: str, relay_client, priority: int = 50):
        """初始化拦截器
        
        Args:
            plugin_id: 插件ID
            relay_client: MessageRelayClient实例
            priority: 优先级（数字越小越早执行）
        """
        super().__init__(plugin_id, priority)
        self.relay_client = relay_client
    
    async def intercept_message(
        self,
        action: str,
        params: Dict[str, Any],
        source_plugin: Optional[str] = None
    ) -> InterceptorResult:
        """拦截消息发送
        
        Args:
            action: API动作名称（如 'send_group_msg', 'send_private_msg'）
            params: 消息参数
            source_plugin: 发起消息的插件ID（如果是插件发起的）
        
        Returns:
            InterceptorResult: 拦截结果
        """
        # 如果中继未启用，直接放行
        if not self.relay_client.enabled:
            return InterceptorResult(allow=True)
        
        # 检查配置是否完整
        if not self.relay_client.official_bot_appid or not self.relay_client.official_bot_qq:
            return InterceptorResult(allow=True)  # 配置不完整，放行原消息
        
        if not self.relay_client.api_url or not self.relay_client.relay_secret:
            return InterceptorResult(allow=True)  # 配置不完整，放行原消息
        
        # 只拦截群消息（私聊暂不支持）
        if action == 'send_group_msg':
            group_id = params.get('group_id')
            message = params.get('message', '')
            auto_escape = params.get('auto_escape', False)
            
            # 如果是本插件自己发送的消息，放行（避免循环）
            # 优先检查 source_plugin，这是最快的检查
            if source_plugin and 'message_relay_client' in source_plugin:
                return InterceptorResult(allow=True)
            
            # 如果是自己发送的触发消息（@官方机器人 [群号]），放行
            # 快速检查：先检查是否包含 @官方机器人，再检查格式
            if isinstance(message, str):
                # 快速检查：是否包含 @官方机器人的 CQ 码
                at_pattern = f"[CQ:at,qq={self.relay_client.official_bot_qq}]"
                if at_pattern in message:
                    # 进一步检查是否包含群号（触发消息格式：@官方机器人 603033293）
                    import re
                    # 匹配格式：[CQ:at,qq=3889084862] 603033293
                    trigger_pattern = rf"\[CQ:at,qq={self.relay_client.official_bot_qq}\]\s*\d+"
                    if re.search(trigger_pattern, message):
                        # 快速返回，不记录日志（避免阻塞）
                        return InterceptorResult(allow=True)
            
            # 拦截其他插件或框架发送的消息，通过中继发送
            # 先返回结果，再异步记录日志和发送到中继（避免阻塞）
            asyncio.create_task(
                self._handle_intercepted_message(group_id, message, source_plugin)
            )
            
            # 阻止原消息发送
            return InterceptorResult(allow=False, block_reason="消息已通过官方机器人中继发送")
        
        # 其他消息类型放行
        return InterceptorResult(allow=True)
    
    async def _handle_intercepted_message(self, group_id: int, message: str, source_plugin: Optional[str]):
        """异步处理被拦截的消息（记录日志并发送到中继）"""
        try:
            self.relay_client.api.log("info", f"拦截到消息发送: 群{group_id}, 来源: {source_plugin or '框架'}")
            await self.relay_client._send_to_relay(
                group_id=group_id,
                message=message if isinstance(message, str) else str(message),
                sender_id=0  # 拦截器无法获取发送者ID，使用0
            )
        except Exception as e:
            self.relay_client.api.log("error", f"处理拦截消息失败: {e}")


class MessageRelayClient:
    """消息中继客户端插件"""
    
    def __init__(self, api, config: Dict[str, Any]):
        """初始化插件
        
        Args:
            api: PluginAPI 实例
            config: 插件配置
        """
        self.api = api
        self.config = config
        self._update_config(config)
        
        # 消息发送计数：{group_id: {'count': int, 'last_trigger': float}}
        self.send_counters: Dict[int, Dict[str, Any]] = {}
        
        # 拦截器实例
        self.interceptor: Optional[MessageRelayInterceptor] = None
        
    def _update_config(self, config: Dict[str, Any]):
        """更新配置"""
        self.config = config
        self.official_bot_appid = config.get('official_bot_appid', '')  # AppID（推荐）
        self.official_bot_qq = config.get('official_bot_qq', '')        # QQ号（备用）
        self.api_url = config.get('api_url', '')
        self.relay_secret = config.get('relay_secret', '')
        self.max_messages = config.get('max_messages_per_batch', 5)
        self.enabled = config.get('enabled', True)
        self.verify_ssl = config.get('verify_ssl', True)  # SSL证书验证（默认开启）
    
    async def on_load(self):
        """插件加载时调用"""
        # 检查配置
        if not self.official_bot_appid or not self.official_bot_qq or not self.relay_secret or not self.api_url:
            self.api.log("warning", "未完整配置官方机器人信息，插件将不会工作")
            self.api.log("warning", f"需要配置：")
            self.api.log("warning", f"  - 官方机器人AppID（用于API识别）")
            self.api.log("warning", f"  - 官方机器人QQ号（用于@触发）")
            self.api.log("warning", f"  - API地址")
            self.api.log("warning", f"  - 中继密钥")
        else:
            self.api.log("info", f"消息中继客户端已启用")
            self.api.log("info", f"官方机器人AppID: {self.official_bot_appid}")
            self.api.log("info", f"官方机器人QQ号: {self.official_bot_qq}")
            self.api.log("info", f"API地址: {self.api_url}")
            
            # 注册消息拦截器
            if self.enabled:
                try:
                    # 获取插件名称（PluginAPI有plugin_name属性）
                    plugin_id = getattr(self.api, 'plugin_name', 'XQNEXT/message_relay_client')
                    self.interceptor = MessageRelayInterceptor(plugin_id, self, priority=50)
                    
                    # 检查方法是否存在
                    if not hasattr(self.api, 'register_message_interceptor'):
                        self.api.log("error", "❌ PluginAPI 不支持拦截器注册，请确保框架版本已更新")
                        self.api.log("error", f"API对象类型: {type(self.api)}")
                        self.api.log("error", f"API对象属性: {dir(self.api)}")
                        return
                    
                    self.api.register_message_interceptor(self.interceptor)
                    self.api.log("info", "✅ 消息拦截器已注册，将拦截所有群消息并通过官方机器人转发")
                except Exception as e:
                    self.api.log("error", f"注册消息拦截器失败: {e}")
                    import traceback
                    self.api.log("error", f"详细错误: {traceback.format_exc()}")
    
    async def on_unload(self):
        """插件卸载时调用"""
        # 取消注册拦截器
        if self.interceptor:
            try:
                self.api.unregister_message_interceptor()
                self.api.log("info", "消息拦截器已取消注册")
            except Exception as e:
                self.api.log("error", f"取消注册拦截器失败: {e}")
        
        self.api.log("info", "消息中继客户端已卸载")
    
    async def on_event_context(self, ctx):
        """处理事件上下文"""
        # 监听接收到的消息（检测官方机器人的触发响应）
        if ctx.event_name == "message.received":
            # 从事件上下文获取消息数据
            event_data = ctx.event_data
            # 快速返回，异步处理消息（避免阻塞事件处理）
            asyncio.create_task(self.handle_message(event_data))
            return ctx
        return None
    
    async def handle_message(self, event: Dict[str, Any]):
        """处理接收到的消息"""
        try:
            message_type = event.get('message_type')
            if message_type != 'group':
                return
            
            user_id = event.get('user_id')
            group_id = event.get('group_id')
            raw_message = event.get('raw_message', '')
            message = event.get('message', [])
            
            # 获取纯文本消息
            text_parts = []
            if isinstance(message, list):
                for seg in message:
                    if isinstance(seg, dict):
                        if seg.get('type') == 'text':
                            text_parts.append(seg.get('data', {}).get('text', ''))
            
            text_message = ''.join(text_parts).strip()
            
            # 检查是否是绑定中继指令（不需要@）
            if text_message in ['绑定中继', '绑定群组', '#绑定中继', '/绑定中继']:
                await self._bind_group(group_id, user_id)
                return
            
            # 检查是否是测试指令（不需要@）
            if text_message in ['测试中继', '测试转发', '#测试中继', '#测试转发', '/测试中继', '/测试转发']:
                if self.enabled:
                    await self._test_relay(group_id, user_id)
                return
            
            # 检查是否是ping测试指令
            if text_message in ['ping中继', 'ping测试', '#ping', '/ping']:
                await self._ping_test(group_id, user_id)
                return
            
            # 检查是否是echo指令（不需要@）
            # 格式：echo <内容> 或 #echo <内容> 或 /echo <内容>
            if text_message.startswith('echo ') or text_message.startswith('#echo ') or text_message.startswith('/echo '):
                # 提取echo内容
                parts = text_message.split(' ', 1)
                echo_content = parts[1] if len(parts) > 1 else ''
                if echo_content:
                    await self._echo_message(group_id, user_id, echo_content)
                else:
                    await self.api.send_group_msg(
                        group_id,
                        "❌ Echo命令格式错误\n"
                        "正确格式：echo <内容>\n"
                        "示例：echo 你好世界"
                    )
                return
            
            # 检查是否是官方机器人回复的群openid
            if '群OpenID:' in text_message or '群OpenID: ' in text_message:
                await self._save_group_openid(group_id, text_message)
                return
            
            # 检查是否@了官方机器人（触发消息格式：@官方机器人 [群号]）
            is_at_official_bot = False
            extracted_group_id = None
            
            if isinstance(message, list):
                for seg in message:
                    if isinstance(seg, dict) and seg.get('type') == 'at':
                        at_qq = str(seg.get('data', {}).get('qq', ''))
                        if at_qq == str(self.official_bot_qq):
                            is_at_official_bot = True
                            # 尝试从文本中提取群号
                            if text_message and text_message.strip().isdigit():
                                try:
                                    extracted_group_id = int(text_message.strip())
                                except:
                                    pass
                            break
            
            # 如果@了官方机器人且消息是群号，触发中继发送
            if is_at_official_bot and self.enabled:
                if extracted_group_id:
                    # 这是触发消息，不需要处理（拦截器会放行）
                    self.api.log("info", f"检测到触发消息: @官方机器人 {extracted_group_id}")
                elif text_message:
                    # 如果@了官方机器人但消息不是群号，可能是其他指令，暂时忽略
                    pass
        
        except Exception as e:
            self.api.log("error", f"处理消息异常: {e}")
    
    async def _get_bot_qq(self) -> int:
        """获取本机器人QQ号"""
        try:
            result = await self.api.get_login_info()
            if result.get('success'):
                data = result.get('data', {})
                return data.get('user_id', 0)
        except:
            pass
        return 0
    
    async def _bind_group(self, group_id: int, user_id: int):
        """绑定群组，获取群OpenID"""
        try:
            await self.api.send_group_msg(group_id, "🔗 开始绑定群组，正在获取群OpenID...")
            
            # 检查配置
            if not self.official_bot_qq:
                await self.api.send_group_msg(group_id, "❌ 未配置官方机器人QQ号，无法绑定")
                return
            
            # @官方机器人请求获取群openid
            request_msg = f"[CQ:at,qq={self.official_bot_qq}] #获取群openid"
            await self.api.send_group_msg(group_id, request_msg, auto_escape=False)
            
            await self.api.send_group_msg(
                group_id,
                "✅ 已发送请求，请等待官方机器人回复群OpenID\n"
                "回复后将自动保存映射关系"
            )
            
        except Exception as e:
            await self.api.send_group_msg(group_id, f"❌ 绑定失败: {e}")
    
    async def _save_group_openid(self, group_id: int, message: str):
        """保存群OpenID映射到JSON文件"""
        try:
            self.api.log("info", f"开始保存群OpenID，群号: {group_id}, 原始消息: {message}")
            
            # 解析消息：可能包含@信息，格式如：@机器人 群OpenID: xxxxxx
            # 提取 "群OpenID:" 后面的内容
            if '群OpenID:' in message:
                parts = message.split('群OpenID:')
                if len(parts) >= 2:
                    openid = parts[1].strip()
                    self.api.log("info", f"解析出OpenID: {openid}")
                else:
                    self.api.log("error", "split后长度不足")
                    return
            else:
                self.api.log("error", "消息中不包含'群OpenID:'")
                return
            
            if not openid or len(openid) < 10:
                self.api.log("error", f"解析的OpenID无效: {openid}")
                return
            
            # 保存到JSON文件
            mapping_file = os.path.join(os.path.dirname(__file__), 'data', 'group_mapping.json')
            
            # 确保data目录存在
            os.makedirs(os.path.dirname(mapping_file), exist_ok=True)
            
            # 读取现有映射
            mappings = {}
            if os.path.exists(mapping_file):
                try:
                    with open(mapping_file, 'r', encoding='utf-8') as f:
                        mappings = json.load(f)
                    self.api.log("info", f"读取到现有映射: {len(mappings)} 个群组")
                except:
                    self.api.log("warning", "读取现有映射失败，将创建新文件")
            
            # 添加/更新映射
            mappings[str(group_id)] = {
                'group_id': group_id,
                'group_openid': openid,
                'bind_time': time.strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # 保存到文件
            with open(mapping_file, 'w', encoding='utf-8') as f:
                json.dump(mappings, f, ensure_ascii=False, indent=2)
            
            self.api.log("info", f"群 {group_id} 的OpenID已保存到文件: {mapping_file}")
            
            # 立即读取验证
            with open(mapping_file, 'r', encoding='utf-8') as f:
                verify_data = json.load(f)
                if str(group_id) in verify_data:
                    self.api.log("info", f"✅ 验证成功: {verify_data[str(group_id)]}")
                else:
                    self.api.log("error", "❌ 验证失败：保存后读取不到数据")
            
            await self.api.send_group_msg(
                group_id,
                f"✅ 群组绑定成功！\n"
                f"群号: {group_id}\n"
                f"OpenID: {openid[:20]}...\n"
                f"已保存到: {mapping_file}\n"
                f"后续消息中继将使用OpenID发送"
            )
            
        except Exception as e:
            self.api.log("error", f"保存群OpenID失败: {e}")
            import traceback
            self.api.log("error", f"详细错误: {traceback.format_exc()}")
            await self.api.send_group_msg(group_id, f"❌ 保存失败: {e}")
    
    async def _get_group_openid(self, group_id: int) -> str:
        """从JSON文件获取群OpenID"""
        try:
            mapping_file = os.path.join(os.path.dirname(__file__), 'data', 'group_mapping.json')
            self.api.log("info", f"尝试从文件读取群OpenID: {mapping_file}")
            
            if not os.path.exists(mapping_file):
                self.api.log("warning", f"映射文件不存在: {mapping_file}")
                return ''
            
            with open(mapping_file, 'r', encoding='utf-8') as f:
                mappings = json.load(f)
            
            group_key = str(group_id)
            if group_key in mappings:
                openid = mappings[group_key].get('group_openid', '')
                self.api.log("info", f"✅ 找到群 {group_id} 的OpenID: {openid[:20]}...")
                return openid
            else:
                self.api.log("warning", f"未找到群 {group_id} 的OpenID映射，文件中有 {len(mappings)} 个群组")
                self.api.log("info", f"文件中的群组: {list(mappings.keys())}")
                return ''
        except Exception as e:
            self.api.log("error", f"获取群OpenID失败: {e}")
            import traceback
            self.api.log("error", f"详细错误: {traceback.format_exc()}")
        
        return ''
    
    async def _ping_test(self, group_id: int, user_id: int):
        """测试网络连接"""
        try:
            await self.api.send_group_msg(group_id, "🔍 开始网络连接诊断...")
            
            results = []
            
            # 1. 检查配置
            results.append("【配置检查】")
            results.append(f"API地址: {self.api_url if self.api_url else '❌未配置'}")
            results.append(f"AppID: {self.official_bot_appid if self.official_bot_appid else '❌未配置'}")
            results.append(f"QQ号: {self.official_bot_qq if self.official_bot_qq else '❌未配置'}")
            results.append(f"密钥: {'✅已配置' if self.relay_secret else '❌未配置'}")
            results.append("")
            
            if not self.api_url:
                await self.api.send_group_msg(group_id, "\n".join(results) + "\n❌ API地址未配置，无法继续测试")
                return
            
            # 2. 解析URL
            results.append("【URL解析】")
            try:
                from urllib.parse import urlparse
                parsed = urlparse(self.api_url)
                results.append(f"协议: {parsed.scheme}")
                results.append(f"域名: {parsed.hostname}")
                results.append(f"端口: {parsed.port if parsed.port else ('443' if parsed.scheme == 'https' else '80')}")
                results.append(f"路径: {parsed.path}")
            except Exception as e:
                results.append(f"❌ 解析失败: {e}")
            results.append("")
            
            # 3. DNS解析测试
            results.append("【DNS解析】")
            try:
                import socket
                from urllib.parse import urlparse
                parsed = urlparse(self.api_url)
                hostname = parsed.hostname
                ip = socket.gethostbyname(hostname)
                results.append(f"✅ {hostname} -> {ip}")
            except Exception as e:
                results.append(f"❌ DNS解析失败: {e}")
            results.append("")
            
            # 4. HTTP连接测试（不验证SSL）
            results.append("【HTTP连接测试】")
            try:
                import ssl
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                
                connector = aiohttp.TCPConnector(ssl=ssl_context)
                async with aiohttp.ClientSession(connector=connector) as session:
                    test_url = self.api_url.split('?')[0]  # 移除可能的参数
                    async with session.get(test_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                        results.append(f"✅ 连接成功")
                        results.append(f"状态码: {response.status}")
                        results.append(f"响应头: {dict(list(response.headers.items())[:3])}")
            except asyncio.TimeoutError:
                results.append("❌ 连接超时（10秒）")
            except Exception as e:
                results.append(f"❌ 连接失败: {type(e).__name__}")
                results.append(f"详细: {str(e)}")
            
            # 发送结果
            message = "\n".join(results)
            # 分段发送（避免消息过长）
            max_length = 500
            if len(message) > max_length:
                parts = [message[i:i+max_length] for i in range(0, len(message), max_length)]
                for part in parts:
                    await self.api.send_group_msg(group_id, part)
                    await asyncio.sleep(0.5)
            else:
                await self.api.send_group_msg(group_id, message)
        
        except Exception as e:
            await self.api.send_group_msg(group_id, f"❌ 诊断异常: {e}")
    
    async def _test_relay(self, group_id: int, user_id: int):
        """测试消息中继功能"""
        try:
            # 检查是否已绑定群组
            group_openid = await self._get_group_openid(group_id)
            if not group_openid:
                await self.api.send_group_msg(
                    group_id,
                    "❌ 未绑定群组！\n"
                    "请先发送 '绑定中继' 进行群组绑定"
                )
                return
            
            # 检查配置是否完整
            if not self.official_bot_appid or not self.official_bot_qq:
                await self.api.send_group_msg(
                    group_id,
                    "❌ 配置不完整！\n"
                    "需要配置：\n"
                    "1. 官方机器人AppID\n"
                    "2. 官方机器人QQ号\n"
                    "3. API地址\n"
                    "4. 中继密钥"
                )
                return
            
            if not self.api_url or not self.relay_secret:
                await self.api.send_group_msg(
                    group_id,
                    "❌ 配置不完整！请检查API地址和密钥配置"
                )
                return
            
            # 发送提示
            await self.api.send_group_msg(
                group_id,
                f"🔄 开始测试消息中继...\n"
                f"AppID: {self.official_bot_appid}\n"
                f"QQ号: {self.official_bot_qq}\n"
                f"群OpenID: {group_openid[:20]}..."
            )
            
            # 发送测试消息到中继服务器
            test_message = f"✅ 消息中继测试成功！\n发起者：{user_id}\n时间：{time.strftime('%Y-%m-%d %H:%M:%S')}"
            
            # 获取群OpenID
            group_openid = await self._get_group_openid(group_id)
            target_group_id = group_openid if group_openid else str(group_id)
            
            # 生成签名
            timestamp = str(int(time.time()))
            sign_str = f"{self.relay_secret}{target_group_id}{test_message}{timestamp}"
            signature = hashlib.md5(sign_str.encode()).hexdigest()
            
            # 构建请求数据
            data = {
                'group_id': target_group_id,
                'message': test_message,
                'sender_id': str(user_id),
                'timestamp': timestamp,
                'signature': signature
            }
            
            # 添加机器人标识
            if self.official_bot_appid:
                data['bot_appid'] = self.official_bot_appid
            else:
                data['bot_qq'] = self.official_bot_qq
            
            # 发送HTTP GET请求（参数通过URL传递）
            import urllib.parse
            import ssl
            
            params = {k: str(v) for k, v in data.items()}
            url_with_params = f"{self.api_url}?{urllib.parse.urlencode(params)}"
            
            # 创建SSL上下文（不验证证书）
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(
                    url_with_params,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get('success'):
                            # 发送触发消息：@官方机器人 [群号]
                            trigger_msg = f"[CQ:at,qq={self.official_bot_qq}] {group_id}"
                            trigger_result = await self.api.send_group_msg(group_id, trigger_msg, auto_escape=False)
                            
                            # 获取消息ID并撤回
                            trigger_message_id = None
                            if isinstance(trigger_result, dict):
                                if trigger_result.get('success') and 'data' in trigger_result:
                                    trigger_message_id = trigger_result['data'].get('message_id')
                                elif 'message_id' in trigger_result:
                                    trigger_message_id = trigger_result.get('message_id')
                            elif isinstance(trigger_result, (int, str)):
                                trigger_message_id = trigger_result
                            
                            if trigger_message_id:
                                try:
                                    await asyncio.sleep(0.5)
                                    await self.api.delete_msg(trigger_message_id)
                                    self.api.log("info", f"已撤回测试触发消息: {trigger_message_id}")
                                except Exception as e:
                                    self.api.log("warning", f"撤回测试触发消息失败: {e}")
                            
                            await self.api.send_group_msg(
                                group_id,
                                f"✅ 测试消息已提交到中继服务器"
                            )
                        else:
                            error = result.get('error', '未知错误')
                            await self.api.send_group_msg(
                                group_id,
                                f"❌ 测试失败: {error}"
                            )
                    else:
                        await self.api.send_group_msg(
                            group_id,
                            f"❌ API连接失败 (HTTP {response.status})\n"
                            f"请检查API地址是否正确"
                        )
        
        except asyncio.TimeoutError:
            await self.api.send_group_msg(
                group_id,
                "❌ 连接超时\n可能原因：\n1. API地址错误\n2. 网络不通\n3. 服务器无响应"
            )
        except Exception as e:
            await self.api.send_group_msg(
                group_id,
                f"❌ 测试异常: {str(e)}"
            )
    
    async def _send_to_relay(self, group_id: int, message: str, sender_id: int):
        """发送消息到中继服务器"""
        try:
            # 获取群OpenID（如果已绑定）
            group_openid = await self._get_group_openid(group_id)
            
            # 使用OpenID（如果有）或群号
            target_group_id = group_openid if group_openid else str(group_id)
            
            if group_openid:
                self.api.log("info", f"使用群OpenID发送: {group_openid[:20]}...")
            else:
                self.api.log("warning", f"未绑定群OpenID，使用群号发送。建议先发送'绑定中继'进行绑定")
            
            # 生成签名
            timestamp = str(int(time.time()))
            sign_str = f"{self.relay_secret}{target_group_id}{message}{timestamp}"
            signature = hashlib.md5(sign_str.encode()).hexdigest()
            
            # 构建请求数据（优先使用AppID）
            data = {
                'group_id': target_group_id,
                'message': message,
                'sender_id': str(sender_id),
                'timestamp': timestamp,
                'signature': signature
            }
            
            # 添加机器人标识（优先AppID，其次QQ号）
            if self.official_bot_appid:
                data['bot_appid'] = self.official_bot_appid
            else:
                data['bot_qq'] = self.official_bot_qq
            
            # 先发送触发消息：@官方机器人 [群号]
            trigger_msg = f"[CQ:at,qq={self.official_bot_qq}] {group_id}"
            self.api.log("info", f"发送触发消息: @官方机器人 {group_id}")
            
            # 发送触发消息并获取消息ID
            try:
                # 使用 send_group_msg 方法（会被拦截器拦截，但拦截器会识别触发消息并放行）
                trigger_result = await self.api.send_group_msg(group_id, trigger_msg, auto_escape=False)
                trigger_message_id = None
                
                # 解析返回的消息ID
                if isinstance(trigger_result, dict):
                    if trigger_result.get('success') and 'data' in trigger_result:
                        trigger_message_id = trigger_result['data'].get('message_id')
                    elif 'message_id' in trigger_result:
                        trigger_message_id = trigger_result.get('message_id')
                elif isinstance(trigger_result, (int, str)):
                    trigger_message_id = trigger_result
                
                # 立即撤回触发消息
                if trigger_message_id:
                    try:
                        await asyncio.sleep(0.3)  # 稍微延迟确保消息已发送
                        await self.api.delete_msg(trigger_message_id)
                        self.api.log("info", f"已撤回触发消息: {trigger_message_id}")
                    except Exception as e:
                        self.api.log("warning", f"撤回触发消息失败: {e}")
            except Exception as e:
                self.api.log("error", f"发送触发消息失败: {e}")
                # 继续执行，即使触发消息失败也尝试发送到中继
            
            # 发送HTTP GET请求（参数通过URL传递）
            import urllib.parse
            import ssl
            
            params = {k: str(v) for k, v in data.items()}
            url_with_params = f"{self.api_url}?{urllib.parse.urlencode(params)}"
            
            # 创建SSL上下文（不验证证书）
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(
                    url_with_params,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get('success'):
                            self.api.log("info", f"消息已提交到中继服务器: 群{group_id}")
                        else:
                            error = result.get('error', '未知错误')
                            self.api.log("error", f"中继服务器返回错误: {error}")
                    else:
                        self.api.log("error", f"HTTP请求失败: {response.status}")
        
        except asyncio.TimeoutError:
            self.api.log("error", "请求官方机器人API超时")
        except Exception as e:
            self.api.log("error", f"发送到中继服务器失败: {e}")
    
    async def _echo_message(self, group_id: int, user_id: int, content: str):
        """Echo功能 - 通过官方机器人发送指定内容
        
        Args:
            group_id: 群号
            user_id: 发送者QQ号
            content: 要发送的内容
        """
        try:
            # 检查是否已绑定群组
            group_openid = await self._get_group_openid(group_id)
            if not group_openid:
                await self.api.send_group_msg(
                    group_id,
                    "❌ 未绑定群组！\n"
                    "请先发送 '绑定中继' 进行群组绑定"
                )
                return
            
            # 检查配置是否完整
            if not self.official_bot_appid or not self.official_bot_qq:
                await self.api.send_group_msg(
                    group_id,
                    "❌ 配置不完整！\n"
                    "需要配置：\n"
                    "1. 官方机器人AppID\n"
                    "2. 官方机器人QQ号\n"
                    "3. API地址\n"
                    "4. 中继密钥"
                )
                return
            
            if not self.api_url or not self.relay_secret:
                await self.api.send_group_msg(
                    group_id,
                    "❌ 配置不完整！请检查API地址和密钥配置"
                )
                return
            
            # 通过中继发送echo内容
            await self._send_to_relay(
                group_id=group_id,
                message=content,
                sender_id=user_id
            )
            
            self.api.log("info", f"Echo消息已提交: 群{group_id}, 内容: {content[:50]}...")
        
        except Exception as e:
            self.api.log("error", f"Echo消息发送失败: {e}")
            await self.api.send_group_msg(
                group_id,
                f"❌ Echo发送失败: {str(e)}"
            )


# 插件入口点
async def create_plugin(api, config: Dict[str, Any]):
    """创建插件实例
    
    Args:
        api: PluginAPI 实例
        config: 插件配置
        
    Returns:
        Plugin 实例
    """
    plugin = MessageRelayClient(api, config)
    await plugin.on_load()
    return plugin
