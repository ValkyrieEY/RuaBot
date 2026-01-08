"""Kawaii Status Plugin - 服务器状态查看插件

适配自 nonebot-plugin-kawaii-status
"""

import base64
import platform
import sys
import asyncio
import uuid
from datetime import datetime
from typing import Dict, Any
from pathlib import Path
import tempfile
import os
import importlib.util

# 动态导入同目录下的模块
_plugin_dir = Path(__file__).parent

def _load_module(name, file_path):
    """动态加载模块"""
    spec = importlib.util.spec_from_file_location(name, file_path)
    if spec and spec.loader:
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module
    return None

# 加载依赖模块
drawer_module = _load_module('kawaii_status_drawer', _plugin_dir / 'drawer.py')
data_source_module = _load_module('kawaii_status_data_source', _plugin_dir / 'data_source.py')

# 导入函数
draw = drawer_module.draw if drawer_module else None
set_framework_info = drawer_module.set_framework_info if drawer_module else None
set_framework_start_time = data_source_module.set_framework_start_time if data_source_module else None
get_framework_start_time = data_source_module.get_framework_start_time if data_source_module else None


class KawaiiStatusPlugin:
    """Kawaii Status 插件"""
    
    def __init__(self, api, config: Dict[str, Any]):
        """初始化插件
        
        Args:
            api: PluginAPI 实例
            config: 插件配置
        """
        self.api = api
        self.config = config
        self.to_me = config.get('to_me', False)
        self.only_superuser = config.get('only_superuser', False)
        self.nickname = config.get('nickname', 'Bot')
        self.running = False
        
        # 命令别名
        self.commands = ['status', '状态', '运行状态']
        
    async def on_load(self):
        """插件加载时调用"""
        self.api.log("info", "=" * 50)
        self.api.log("info", "Kawaii Status 插件开始加载...")
        self.api.log("info", f"插件配置: to_me={self.to_me}, only_superuser={self.only_superuser}, nickname={self.nickname}")
        self.api.log("info", f"支持的命令: {self.commands}")
        
        # 设置框架启动时间（使用当前时间作为启动时间）
        # 注意：实际框架启动时间可能更早，但插件加载时使用当前时间作为参考
        set_framework_start_time(datetime.now())
        self.api.log("info", "已设置框架启动时间")
        
        # 更新框架信息
        await self._update_framework_info()
        
        self.running = True
        self.api.log("info", "Kawaii Status 插件加载完成！")
        self.api.log("info", "=" * 50)
    
    async def _update_framework_info(self):
        """更新框架信息"""
        try:
            # 获取框架版本（使用默认值）
            framework_version = "XQNEXT"
            
            # 获取插件数量（简化处理，使用默认值）
            loaded_count = 0
            try:
                # 尝试通过事件总线获取插件信息
                # 如果无法获取，使用默认值
                pass
            except:
                pass
            
            # 获取 Bot 昵称
            nickname = self.nickname
            try:
                # 尝试从 OneBot 获取登录信息
                login_info = await self.api.get_login_info()
                if login_info.get('success') and login_info.get('data'):
                    nickname = login_info['data'].get('nickname', self.nickname)
            except:
                pass
            
            # 设置框架信息
            set_framework_info(
                framework_version=framework_version,
                plugin_version="0.2.0",
                nickname=nickname,
                loaded_plugins_count=loaded_count
            )
        except Exception as e:
            self.api.log("warning", f"更新框架信息失败: {e}")
    
    async def on_unload(self):
        """插件卸载时调用"""
        self.api.log("info", "Kawaii Status 插件已卸载")
        self.running = False
    
    async def on_event(self, event_name: str, data: Dict[str, Any]):
        """处理事件
        
        Args:
            event_name: 事件名称
            data: 事件数据
        """
        # 记录所有收到的事件（用于调试）
        self.api.log("info", f"[Kawaii Status] 收到事件: {event_name}")
        if event_name == "onebot.message":
            self.api.log("info", f"[Kawaii Status] 处理 onebot.message 事件")
            await self.handle_message(data)
        else:
            self.api.log("debug", f"[Kawaii Status] 忽略事件: {event_name}")
    
    def _should_respond(self, event: Dict[str, Any]) -> bool:
        """判断是否应该响应消息
        
        Args:
            event: 消息事件
            
        Returns:
            是否应该响应
        """
        # 获取原始消息，可能在不同字段中
        raw_message = event.get('raw_message', '').strip()
        if not raw_message:
            # 尝试从 message 字段提取文本
            message = event.get('message', '')
            if isinstance(message, list):
                # 提取所有文本段
                text_parts = []
                for seg in message:
                    if isinstance(seg, dict):
                        if seg.get('type') == 'text':
                            text_parts.append(seg.get('data', {}).get('text', ''))
                raw_message = ''.join(text_parts).strip()
            elif isinstance(message, str):
                raw_message = message.strip()
        
        self.api.log("debug", f"检查消息: raw_message='{raw_message}', event keys={list(event.keys())}, commands={self.commands}")
        
        # 检查是否是命令（支持 /status、status、/状态、状态 等格式）
        is_command = False
        matched_cmd = None
        for cmd in self.commands:
            # 支持多种格式：/status, status, /状态, 状态
            if (raw_message == f"/{cmd}" or 
                raw_message == cmd or
                raw_message.lower() == f"/{cmd.lower()}" or
                raw_message.lower() == cmd.lower()):
                is_command = True
                matched_cmd = cmd
                self.api.log("debug", f"匹配到命令: {cmd}")
                break
        
        if not is_command:
            self.api.log("debug", f"不是命令，跳过处理")
            return False
        
        # 检查是否需要 @Bot
        if self.to_me:
            # 检查消息中是否包含 @Bot
            message = event.get('message', [])
            if isinstance(message, list):
                for seg in message:
                    if isinstance(seg, dict) and seg.get('type') == 'at':
                        # 检查是否 @ 了 Bot
                        # 这里需要获取 Bot 的 QQ 号，暂时跳过检查
                        pass
            # 简化处理：如果配置了 to_me，但无法判断，则允许响应
            # 实际使用中可以通过 API 获取 Bot 的 QQ 号进行判断
        
        # 检查是否只允许超级用户
        if self.only_superuser:
            # 这里需要检查用户权限，暂时跳过
            # 可以通过 API 或配置来判断
            pass
        
        return True
    
    async def handle_message(self, event: Dict[str, Any]):
        """处理消息事件
        
        Args:
            event: OneBot 消息事件
        """
        self.api.log("debug", f"处理消息事件: {event}")
        if not self._should_respond(event):
            self.api.log("debug", "消息不匹配，不处理")
            return
        
        try:
            message_type = event.get('message_type')  # 'private' or 'group'
            user_id = event.get('user_id')
            group_id = event.get('group_id')
            
            self.api.log("info", f"收到状态查询请求: {message_type}, user_id={user_id}, group_id={group_id}")
            
            # 更新框架信息
            await self._update_framework_info()
            
            # 绘制状态图片
            if draw is None:
                self.api.log("error", "draw 函数未加载")
                return
            img_bytes = draw()
            
            # 压缩图片以减少 base64 大小（避免 readline 限制）
            # PNG 图片可能很大，需要压缩
            try:
                from PIL import Image
                from io import BytesIO
                
                # 打开图片
                img = Image.open(BytesIO(img_bytes))
                
                # 如果图片太大，进行压缩
                # 限制最大尺寸和文件大小
                max_size = (1920, 1080)  # 最大尺寸
                max_file_size = 300 * 1024  # 最大 300KB（压缩后）
                
                # 调整尺寸
                if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
                    img.thumbnail(max_size, Image.Resampling.LANCZOS)
                    self.api.log("debug", f"图片已调整尺寸: {img.size}")
                
                # 压缩并保存
                output = BytesIO()
                quality = 85
                attempts = 0
                while attempts < 5:  # 最多尝试 5 次
                    output.seek(0)
                    output.truncate()
                    # PNG 不支持 quality 参数，使用 optimize
                    img.save(output, format='PNG', optimize=True)
                    compressed_size = len(output.getvalue())
                    
                    if compressed_size <= max_file_size:
                        break
                    
                    # 如果还是太大，进一步缩小尺寸
                    new_size = (int(img.size[0] * 0.9), int(img.size[1] * 0.9))
                    img = img.resize(new_size, Image.Resampling.LANCZOS)
                    attempts += 1
                
                img_bytes = output.getvalue()
                self.api.log("debug", f"图片已压缩: {len(img_bytes)} bytes (原始: {len(img_bytes)} bytes)")
                
            except Exception as e:
                self.api.log("warning", f"图片压缩失败，使用原始图片: {e}")
                # 如果压缩失败，使用原始图片，但限制大小
                if len(img_bytes) > 500 * 1024:
                    self.api.log("error", f"图片太大 ({len(img_bytes)} bytes)，无法发送")
                    return
            
            # 转换为 base64
            img_base64 = base64.b64encode(img_bytes).decode('utf-8')
            self.api.log("debug", f"图片已转换为 base64，长度: {len(img_base64)} 字符")
            
            # 构建 CQ 码
            img_cq = f"[CQ:image,file=base64://{img_base64}]"
            
            # 发送图片
            if message_type == 'private':
                result = await self.api.send_private_msg(user_id, img_cq)
            elif message_type == 'group':
                result = await self.api.send_group_msg(group_id, img_cq)
            else:
                self.api.log("warning", f"未知的消息类型: {message_type}")
                return
            
            if result.get('success'):
                self.api.log("info", "状态图片发送成功")
            else:
                self.api.log("error", f"状态图片发送失败: {result.get('error')}")
        
        except Exception as e:
            self.api.log("error", f"处理状态查询请求失败: {e}", exc_info=True)


# Plugin entry point
async def create_plugin(api, config: Dict[str, Any]):
    """创建插件实例
    
    这个函数由插件运行时调用以创建插件。
    
    Args:
        api: PluginAPI 实例（提供 send_message, get_config 等）
        config: 插件配置
        
    Returns:
        插件实例
    """
    # 使用 api.log 记录插件创建
    try:
        api.log("info", "=" * 60)
        api.log("info", "正在创建 Kawaii Status 插件实例...")
        api.log("info", f"配置: {config}")
        
        plugin = KawaiiStatusPlugin(api, config)
        await plugin.on_load()
        
        api.log("info", "Kawaii Status 插件实例创建成功！")
        api.log("info", "=" * 60)
        return plugin
    except Exception as e:
        api.log("error", f"创建插件实例失败: {e}")
        import traceback
        api.log("error", traceback.format_exc())
        raise

