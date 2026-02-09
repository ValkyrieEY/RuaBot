"""刷屏检测和警告系统模块"""

import time
from typing import Dict, List
import sys
from pathlib import Path

# 添加父目录到路径
parent_dir = Path(__file__).parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from utils import utils


class SpamDetectionModule:
    """刷屏检测模块"""
    
    def __init__(self, api, data_manager, permission_manager):
        self.api = api
        self.data_manager = data_manager
        self.permission_manager = permission_manager
    
    async def handle_command(self, event: Dict, command: str) -> bool:
        """处理刷屏检测指令"""
        user_id = event.get('user_id')
        group_id = event.get('group_id')
        raw_message = event.get('raw_message', '').strip()
        
        if not self.permission_manager.has_group_permission(user_id, group_id):
            return False
        
        group_id_str = str(group_id)
        
        # 初始化设置
        if group_id_str not in self.data_manager.spam_settings:
            self.data_manager.spam_settings[group_id_str] = {
                'enabled': False,
                'tip_enabled': False,
                'check_times': 5,  # 检测次数
                'check_window': 10,  # 检测时间窗口（秒）
                'mute_duration': 600,  # 禁言时间（秒）
                'action': '撤回'  # 撤回/撤回禁言/撤回踢出
            }
        
        settings = self.data_manager.spam_settings[group_id_str]
        
        # 开/关刷屏提示
        if command in ["开刷屏提示", "关刷屏提示"]:
            enabled = command.startswith("开")
            settings['tip_enabled'] = enabled
            await self.data_manager._save_json('spam_settings', self.data_manager.spam_settings)
            await self.api.send_group_msg(group_id, f"已{'开启' if enabled else '关闭'}刷屏提示")
            return True
        
        # 开/关刷屏检测
        elif command in ["开刷屏检测", "关刷屏检测"]:
            enabled = command.startswith("开")
            settings['enabled'] = enabled
            await self.data_manager._save_json('spam_settings', self.data_manager.spam_settings)
            await self.api.send_group_msg(group_id, f"已{'开启' if enabled else '关闭'}刷屏检测")
            return True
        
        # 查看检测配置
        elif command == "查看检测配置":
            msg = f"""刷屏检测配置
检测状态：{'开启' if settings.get('enabled') else '关闭'}
提示状态：{'开启' if settings.get('tip_enabled') else '关闭'}
检测次数：{settings.get('check_times', 5)}次
检测窗口：{settings.get('check_window', 10)}秒
禁言时长：{utils.format_time(settings.get('mute_duration', 600))}
处罚方式：{settings.get('action', '撤回')}"""
            await self.api.send_group_msg(group_id, msg)
            return True
        
        # 设置检测次数+次数
        elif raw_message.startswith("设置检测次数"):
            times = utils.extract_number_from_text(raw_message)
            if not times:
                await self.api.send_group_msg(group_id, "请输入次数")
                return True
            
            settings['check_times'] = times
            await self.data_manager._save_json('spam_settings', self.data_manager.spam_settings)
            await self.api.send_group_msg(group_id, f"已设置检测次数为 {times}次")
            return True
        
        # 设置检测时间+时间
        elif raw_message.startswith("设置检测时间"):
            time_str = raw_message.replace("设置检测时间", "").strip()
            seconds = utils.parse_time_string(time_str)
            if not seconds:
                await self.api.send_group_msg(group_id, "时间格式错误")
                return True
            
            settings['check_window'] = seconds
            await self.data_manager._save_json('spam_settings', self.data_manager.spam_settings)
            await self.api.send_group_msg(group_id, f"已设置检测窗口为 {utils.format_time(seconds)}")
            return True
        
        # 设置禁言时间+时间
        elif raw_message.startswith("设置禁言时间") and "刷屏" not in raw_message:
            time_str = raw_message.replace("设置禁言时间", "").strip()
            seconds = utils.parse_time_string(time_str)
            if not seconds:
                await self.api.send_group_msg(group_id, "时间格式错误")
                return True
            
            settings['mute_duration'] = seconds
            await self.data_manager._save_json('spam_settings', self.data_manager.spam_settings)
            await self.api.send_group_msg(group_id, f"已设置刷屏禁言时长为 {utils.format_time(seconds)}")
            return True
        
        # 设置刷屏处罚+<类型>
        elif raw_message.startswith("设置刷屏处罚"):
            if "撤回踢出" in raw_message:
                action = "撤回踢出"
            elif "撤回禁言" in raw_message:
                action = "撤回禁言"
            elif "撤回" in raw_message:
                action = "撤回"
            else:
                await self.api.send_group_msg(group_id, "处罚类型错误，可选：撤回、撤回禁言、撤回踢出")
                return True
            
            settings['action'] = action
            await self.data_manager._save_json('spam_settings', self.data_manager.spam_settings)
            await self.api.send_group_msg(group_id, f"已设置刷屏处罚为：{action}")
            return True
        
        return False
    
    async def check_spam(self, event: Dict):
        """检查是否刷屏"""
        try:
            group_id = event.get('group_id')
            user_id = event.get('user_id')
            message_id = event.get('message_id')
            
            # 跳过有权限的用户
            if self.permission_manager.has_group_permission(user_id, group_id):
                return
            
            group_id_str = str(group_id)
            settings = self.data_manager.spam_settings.get(group_id_str, {})
            
            if not settings.get('enabled'):
                return
            
            # 初始化记录
            if group_id_str not in self.data_manager.spam_records:
                self.data_manager.spam_records[group_id_str] = {}
            
            user_id_str = str(user_id)
            if user_id_str not in self.data_manager.spam_records[group_id_str]:
                self.data_manager.spam_records[group_id_str][user_id_str] = []
            
            current_time = time.time()
            check_window = settings.get('check_window', 10)
            check_times = settings.get('check_times', 5)
            
            # 添加当前消息时间
            self.data_manager.spam_records[group_id_str][user_id_str].append(current_time)
            
            # 清理过期记录
            self.data_manager.spam_records[group_id_str][user_id_str] = [
                t for t in self.data_manager.spam_records[group_id_str][user_id_str]
                if current_time - t <= check_window
            ]
            
            # 检查是否刷屏
            if len(self.data_manager.spam_records[group_id_str][user_id_str]) >= check_times:
                # 触发刷屏
                action = settings.get('action', '撤回')
                
                # 撤回消息
                if message_id:
                    await self.api.call_api('delete_msg', {'message_id': message_id})
                
                # 提示
                if settings.get('tip_enabled'):
                    await self.api.send_group_msg(group_id, f"[CQ:at,qq={user_id}] 检测到刷屏行为")
                
                # 执行处罚
                if action == "撤回禁言" or action == "撤回踢出":
                    # 禁言
                    mute_duration = settings.get('mute_duration', 600)
                    await self.api.call_api('set_group_ban', {
                        'group_id': group_id,
                        'user_id': user_id,
                        'duration': mute_duration
                    })
                    
                    if action == "撤回踢出":
                        # 踢出
                        await self.api.call_api('set_group_kick', {
                            'group_id': group_id,
                            'user_id': user_id,
                            'reject_add_request': False
                        })
                
                # 清空记录
                self.data_manager.spam_records[group_id_str][user_id_str] = []
        
        except Exception as e:
            self.api.log("error", f"检查刷屏失败: {e}")


class WarningModule:
    """警告系统模块"""
    
    def __init__(self, api, data_manager, permission_manager):
        self.api = api
        self.data_manager = data_manager
        self.permission_manager = permission_manager
    
    async def handle_command(self, event: Dict, command: str) -> bool:
        """处理警告系统指令"""
        user_id = event.get('user_id')
        group_id = event.get('group_id')
        raw_message = event.get('raw_message', '').strip()
        message = event.get('message', [])
        
        group_id_str = str(group_id)
        
        # 初始化设置
        if group_id_str not in self.data_manager.warning_settings:
            self.data_manager.warning_settings[group_id_str] = {
                'notify_enabled': True,
                'query_enabled': True,
                'action_type': '禁言',  # 禁言/踢出
                'max_warnings': 3,
                'mute_duration': 600
            }
        
        settings = self.data_manager.warning_settings[group_id_str]
        
        # 警告@
        if raw_message.startswith("警告"):
            if not self.permission_manager.has_group_permission(user_id, group_id):
                return False
            
            at_list = utils.parse_at(message)
            if not at_list:
                await self.api.send_group_msg(group_id, "请@要警告的人")
                return True
            
            target_qq = at_list[0]
            
            # 不能警告有权限的人
            if self.permission_manager.has_group_permission(target_qq, group_id):
                await self.api.send_group_msg(group_id, "无法警告有权限的用户")
                return True
            
            # 初始化警告记录
            if group_id_str not in self.data_manager.warnings:
                self.data_manager.warnings[group_id_str] = {}
            
            target_str = str(target_qq)
            if target_str not in self.data_manager.warnings[group_id_str]:
                self.data_manager.warnings[group_id_str][target_str] = 0
            
            self.data_manager.warnings[group_id_str][target_str] += 1
            current_warnings = self.data_manager.warnings[group_id_str][target_str]
            max_warnings = settings.get('max_warnings', 3)
            
            await self.data_manager._save_json('warnings', self.data_manager.warnings)
            
            msg = f"[CQ:at,qq={target_qq}] 你已被警告！\n当前警告次数：{current_warnings}/{max_warnings}"
            
            # 检查是否达到限制
            if current_warnings >= max_warnings:
                action_type = settings.get('action_type', '禁言')
                
                try:
                    if action_type == '踢出':
                        await self.api.call_api('set_group_kick', group_id=group_id, user_id=target_qq, reject_add_request=False)
                        msg += f"\n已达到警告上限，执行：踢出"
                    else:
                        mute_duration = settings.get('mute_duration', 600)
                        await self.api.call_api('set_group_ban', group_id=group_id, user_id=target_qq, duration=mute_duration)
                        msg += f"\n已达到警告上限，执行：禁言{utils.format_time(mute_duration)}"
                    
                    # 清空警告
                    self.data_manager.warnings[group_id_str][target_str] = 0
                    await self.data_manager._save_json('warnings', self.data_manager.warnings)
                except Exception as e:
                    # 直接使用框架返回的错误信息
                    msg += f"\n已达到警告上限，但执行失败：{str(e)}"
                    self.api.log("warning", f"警告执行失败: {e}")
            
            await self.api.send_group_msg(group_id, msg)
            return True
        
        # 我的警告
        elif command == "我的警告":
            if group_id_str not in self.data_manager.warnings:
                await self.api.send_group_msg(group_id, "你当前没有警告记录")
                return True
            
            user_str = str(user_id)
            warnings = self.data_manager.warnings[group_id_str].get(user_str, 0)
            max_warnings = settings.get('max_warnings', 3)
            
            await self.api.send_group_msg(group_id, f"你当前警告次数：{warnings}/{max_warnings}")
            return True
        
        # 查看警告
        elif command == "查看警告":
            if not settings.get('query_enabled'):
                return False
            
            if group_id_str not in self.data_manager.warnings:
                await self.api.send_group_msg(group_id, "本群暂无警告记录")
                return True
            
            warnings_list = self.data_manager.warnings[group_id_str]
            if not warnings_list:
                await self.api.send_group_msg(group_id, "本群暂无警告记录")
                return True
            
            msg = "警告记录\n"
            for qq, count in list(warnings_list.items())[:10]:
                if count > 0:
                    msg += f"  - {qq}: {count}次\n"
            
            await self.api.send_group_msg(group_id, msg)
            return True
        
        # 清空警告
        elif command == "清空警告":
            if not self.permission_manager.has_group_permission(user_id, group_id):
                return False
            
            if group_id_str in self.data_manager.warnings:
                self.data_manager.warnings[group_id_str] = {}
                await self.data_manager._save_json('warnings', self.data_manager.warnings)
            
            await self.api.send_group_msg(group_id, "已清空所有警告记录")
            return True
        
        # 开/关警告通知
        elif command in ["开警告通知", "关警告通知"]:
            if not self.permission_manager.has_group_permission(user_id, group_id):
                return False
            
            enabled = command.startswith("开")
            settings['notify_enabled'] = enabled
            await self.data_manager._save_json('warning_settings', self.data_manager.warning_settings)
            await self.api.send_group_msg(group_id, f"已{'开启' if enabled else '关闭'}警告通知")
            return True
        
        # 开/关警告查询
        elif command in ["开警告查询", "关警告查询"]:
            if not self.permission_manager.has_group_permission(user_id, group_id):
                return False
            
            enabled = command.startswith("开")
            settings['query_enabled'] = enabled
            await self.data_manager._save_json('warning_settings', self.data_manager.warning_settings)
            await self.api.send_group_msg(group_id, f"已{'开启' if enabled else '关闭'}警告查询")
            return True
        
        # 设置警告执行类型+类型
        elif raw_message.startswith("设置警告执行类型"):
            if not self.permission_manager.has_group_permission(user_id, group_id):
                return False
            
            if "踢出" in raw_message:
                action_type = "踢出"
            elif "禁言" in raw_message:
                action_type = "禁言"
            else:
                await self.api.send_group_msg(group_id, "类型错误，可选：禁言、踢出")
                return True
            
            settings['action_type'] = action_type
            await self.data_manager._save_json('warning_settings', self.data_manager.warning_settings)
            await self.api.send_group_msg(group_id, f"已设置警告执行类型为：{action_type}")
            return True
        
        # 设置警告限制次数+内容
        elif raw_message.startswith("设置警告限制次数"):
            if not self.permission_manager.has_group_permission(user_id, group_id):
                return False
            
            times = utils.extract_number_from_text(raw_message)
            if not times:
                await self.api.send_group_msg(group_id, "请输入次数")
                return True
            
            settings['max_warnings'] = times
            await self.data_manager._save_json('warning_settings', self.data_manager.warning_settings)
            await self.api.send_group_msg(group_id, f"已设置警告限制次数为 {times}次")
            return True
        
        # 设置警告禁言时间+时间
        elif raw_message.startswith("设置警告禁言时间"):
            if not self.permission_manager.has_group_permission(user_id, group_id):
                return False
            
            time_str = raw_message.replace("设置警告禁言时间", "").strip()
            seconds = utils.parse_time_string(time_str)
            if not seconds:
                await self.api.send_group_msg(group_id, "时间格式错误")
                return True
            
            settings['mute_duration'] = seconds
            await self.data_manager._save_json('warning_settings', self.data_manager.warning_settings)
            await self.api.send_group_msg(group_id, f"已设置警告禁言时长为 {utils.format_time(seconds)}")
            return True
        
        return False

