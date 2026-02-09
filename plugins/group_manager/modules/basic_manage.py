"""基础群管模块"""

import asyncio
import platform
from typing import Dict
import sys
from pathlib import Path

# 添加父目录到路径
parent_dir = Path(__file__).parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from utils import utils


class BasicManageModule:
    """基础群管模块"""
    
    def __init__(self, api, data_manager, permission_manager):
        self.api = api
        self.data_manager = data_manager
        self.permission_manager = permission_manager
    
    async def handle_command(self, event: Dict, command: str) -> bool:
        """处理基础群管指令"""
        user_id = event.get('user_id')
        group_id = event.get('group_id')
        raw_message = event.get('raw_message', '').strip()
        message = event.get('message', [])
        
        self.api.log("debug", f"BasicManage处理指令: {command}, raw_message: {raw_message}")
        
        # 检查是否有群管权限
        if not self.permission_manager.has_group_permission(user_id, group_id):
            self.api.log("debug", f"用户 {user_id} 没有群管权限")
            return False
        
        # 清屏（发送多条空消息）
        if command == "清屏":
            for _ in range(10):
                await self.api.send_group_msg(group_id, "\n" * 20)
                await asyncio.sleep(0.1)
            return True
        
        # 踢人
        elif raw_message.startswith("踢"):
            target_qq = utils.extract_number_from_text(raw_message)
            if not target_qq:
                at_list = utils.parse_at(message)
                if at_list:
                    target_qq = at_list[0]
            
            if not target_qq:
                await self.api.send_group_msg(group_id, "❌ 请指定QQ号，格式：踢123456 或 @某人")
                return True
            
            # 检查目标权限
            if self.permission_manager.has_group_permission(target_qq, group_id):
                await self.api.send_group_msg(group_id, "❌ 无法踢出有权限的用户")
                return True
            
            try:
                await self.api.call_api('set_group_kick', group_id=group_id, user_id=target_qq, reject_add_request=False)
                await self.api.send_group_msg(group_id, f"✅ 已踢出 {target_qq}")
            except Exception as e:
                await self.api.send_group_msg(group_id, f"❌ 踢出失败：{str(e)}")
            return True
        
        # 禁言
        elif raw_message.startswith("禁言"):
            # 解析QQ和时间
            at_list = utils.parse_at(message)
            if not at_list:
                await self.api.send_group_msg(group_id, "❌ 请@要禁言的人，格式：禁言@某人 10")
                return True
            
            target_qq = at_list[0]
            
            # 提取时间（分钟）
            time_minutes = utils.extract_number_from_text(raw_message.replace("禁言", ""))
            if not time_minutes:
                time_minutes = 10  # 默认10分钟
            
            # 检查目标权限
            if self.permission_manager.has_group_permission(target_qq, group_id):
                await self.api.send_group_msg(group_id, "❌ 无法禁言有权限的用户")
                return True
            
            duration = time_minutes * 60  # 转为秒
            try:
                await self.api.call_api('set_group_ban', group_id=group_id, user_id=target_qq, duration=duration)
                await self.api.send_group_msg(group_id, f"✅ 已禁言 [CQ:at,qq={target_qq}] {time_minutes}分钟")
            except Exception as e:
                await self.api.send_group_msg(group_id, f"❌ 禁言失败：{str(e)}")
            return True
        
        # 解除禁言
        elif raw_message.startswith("解除禁言"):
            target_qq = utils.extract_number_from_text(raw_message)
            if not target_qq:
                at_list = utils.parse_at(message)
                if at_list:
                    target_qq = at_list[0]
            
            if not target_qq:
                await self.api.send_group_msg(group_id, "❌ 请指定QQ号")
                return True
            
            try:
                await self.api.call_api('set_group_ban', group_id=group_id, user_id=target_qq, duration=0)
                await self.api.send_group_msg(group_id, f"✅ 已解除 {target_qq} 的禁言")
            except Exception as e:
                await self.api.send_group_msg(group_id, f"❌ 解禁失败：{str(e)}")
            return True
        
        # 上管理
        elif raw_message.startswith("上管理"):
            target_qq = utils.extract_number_from_text(raw_message)
            if not target_qq:
                at_list = utils.parse_at(message)
                if at_list:
                    target_qq = at_list[0]
            
            if not target_qq:
                await self.api.send_group_msg(group_id, "❌ 请指定QQ号")
                return True
            
            try:
                await self.api.call_api('set_group_admin', group_id=group_id, user_id=target_qq, enable=True)
                await self.api.send_group_msg(group_id, f"✅ 已设置 {target_qq} 为管理员")
            except Exception as e:
                await self.api.send_group_msg(group_id, f"❌ 操作失败（需要机器人是群主）：{str(e)}")
            return True
        
        # 下管理
        elif raw_message.startswith("下管理"):
            target_qq = utils.extract_number_from_text(raw_message)
            if not target_qq:
                at_list = utils.parse_at(message)
                if at_list:
                    target_qq = at_list[0]
            
            if not target_qq:
                await self.api.send_group_msg(group_id, "❌ 请指定QQ号")
                return True
            
            try:
                await self.api.call_api('set_group_admin', group_id=group_id, user_id=target_qq, enable=False)
                await self.api.send_group_msg(group_id, f"✅ 已取消 {target_qq} 的管理员")
            except Exception as e:
                await self.api.send_group_msg(group_id, f"❌ 操作失败（需要机器人是群主）：{str(e)}")
            return True
        
        # 全群禁言
        elif command == "全群禁言":
            try:
                await self.api.call_api('set_group_whole_ban', group_id=group_id, enable=True)
                await self.api.send_group_msg(group_id, "✅ 已开启全群禁言")
            except Exception as e:
                await self.api.send_group_msg(group_id, f"❌ 操作失败：{str(e)}")
            return True
        
        # 全群解禁
        elif command == "全群解禁":
            try:
                await self.api.call_api('set_group_whole_ban', group_id=group_id, enable=False)
                await self.api.send_group_msg(group_id, "✅ 已关闭全群禁言")
            except Exception as e:
                await self.api.send_group_msg(group_id, f"❌ 操作失败：{str(e)}")
            return True
        
        # 截图桌面
        elif command == "截图桌面":
            await self.screenshot_desktop(group_id)
            return True
        
        # 开/关踢出拉黑
        elif command in ["开踢出拉黑", "关踢出拉黑"]:
            enabled = command.startswith("开")
            group_id_str = str(group_id)
            if group_id_str not in self.data_manager.basic_settings:
                self.data_manager.basic_settings[group_id_str] = {}
            
            self.data_manager.basic_settings[group_id_str]['kick_blacklist'] = enabled
            await self.data_manager._save_json('basic_settings', self.data_manager.basic_settings)
            await self.api.send_group_msg(group_id, f"✅ 已{'开启' if enabled else '关闭'}踢出拉黑")
            return True
        
        # 开/关退群拉黑
        elif command in ["开退群拉黑", "关退群拉黑"]:
            enabled = command.startswith("开")
            group_id_str = str(group_id)
            if group_id_str not in self.data_manager.basic_settings:
                self.data_manager.basic_settings[group_id_str] = {}
            
            self.data_manager.basic_settings[group_id_str]['leave_blacklist'] = enabled
            await self.data_manager._save_json('basic_settings', self.data_manager.basic_settings)
            await self.api.send_group_msg(group_id, f"✅ 已{'开启' if enabled else '关闭'}退群拉黑")
            return True
        
        # 开/关踢出撤回
        elif command in ["开踢出撤回", "关踢出撤回"]:
            enabled = command.startswith("开")
            group_id_str = str(group_id)
            if group_id_str not in self.data_manager.basic_settings:
                self.data_manager.basic_settings[group_id_str] = {}
            
            self.data_manager.basic_settings[group_id_str]['kick_recall'] = enabled
            await self.data_manager._save_json('basic_settings', self.data_manager.basic_settings)
            await self.api.send_group_msg(group_id, f"✅ 已{'开启' if enabled else '关闭'}踢出撤回")
            return True
        
        # 开/关菜单权限
        elif command in ["开菜单权限", "关菜单权限"]:
            enabled = command.startswith("开")
            group_id_str = str(group_id)
            if group_id_str not in self.data_manager.basic_settings:
                self.data_manager.basic_settings[group_id_str] = {}
            
            self.data_manager.basic_settings[group_id_str]['menu_permission'] = enabled
            await self.data_manager._save_json('basic_settings', self.data_manager.basic_settings)
            await self.api.send_group_msg(group_id, f"✅ 已{'开启' if enabled else '关闭'}菜单权限限制")
            return True
        
        # 一键踢出黑名单
        elif command == "一键踢出黑名单":
            # 获取黑名单
            from modules.blacklist import BlackWhiteListModule
            blacklist_module = BlackWhiteListModule(self.api, self.data_manager, self.permission_manager)
            
            group_id_str = str(group_id)
            blacklist = self.data_manager.blacklist.get('groups', {}).get(group_id_str, [])
            
            if not blacklist:
                await self.api.send_group_msg(group_id, "❌ 本群黑名单为空")
                return True
            
            kicked_count = 0
            for qq in blacklist:
                try:
                    await self.api.call_api('set_group_kick', group_id=group_id, user_id=qq, reject_add_request=False)
                    kicked_count += 1
                except:
                    pass
            
            await self.api.send_group_msg(group_id, f"✅ 已踢出 {kicked_count}/{len(blacklist)} 个黑名单成员")
            return True
        
        return False
    
    async def screenshot_desktop(self, group_id: int):
        """截图桌面功能"""
        try:
            # 检查操作系统
            system = platform.system()
            
            if system != 'Windows':
                await self.api.send_group_msg(group_id, "❌ 此功能仅支持Windows系统")
                return
            
            # 尝试导入截图库
            try:
                from PIL import ImageGrab
                import base64
                from io import BytesIO
            except ImportError:
                await self.api.send_group_msg(group_id, "❌ 缺少PIL库，请安装：pip install pillow")
                return
            
            # 截图
            await self.api.send_group_msg(group_id, "📸 正在截图...")
            
            # 截取屏幕
            screenshot = ImageGrab.grab()
            
            # 保存到内存并转换为base64
            buffer = BytesIO()
            screenshot.save(buffer, format='PNG')
            buffer.seek(0)
            img_base64 = base64.b64encode(buffer.read()).decode('utf-8')
            
            # 使用base64发送图片
            try:
                result = await self.api.send_group_msg(group_id, f"[CQ:image,file=base64://{img_base64}]")
                if result and 'message_id' in result:
                    self.api.log("info", f"已发送桌面截图到群 {group_id}")
                else:
                    self.api.log("warning", f"截图发送结果异常：{result}")
            except Exception as e:
                await self.api.send_group_msg(group_id, f"❌ 发送截图失败：{str(e)}")
        
        except Exception as e:
            self.api.log("error", f"截图失败: {e}")
            await self.api.send_group_msg(group_id, f"❌ 截图失败：{str(e)}")

