"""入群设置模块"""

from typing import Dict
import sys
from pathlib import Path

# 添加父目录到路径
parent_dir = Path(__file__).parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from utils import utils


class JoinSettingsModule:
    """入群设置模块"""
    
    def __init__(self, api, data_manager, permission_manager):
        self.api = api
        self.data_manager = data_manager
        self.permission_manager = permission_manager
    
    async def handle_command(self, event: Dict, command: str) -> bool:
        """处理入群设置指令"""
        user_id = event.get('user_id')
        group_id = event.get('group_id')
        raw_message = event.get('raw_message', '').strip()
        
        if not self.permission_manager.has_group_permission(user_id, group_id):
            return False
        
        group_id_str = str(group_id)
        
        # 初始化设置
        if group_id_str not in self.data_manager.join_settings:
            self.data_manager.join_settings[group_id_str] = {
                'welcome_enabled': False,
                'mute_enabled': False,
                'audit_enabled': False,
                'private_msg_enabled': False,
                'auto_rename_enabled': False,
                'mute_duration': 60,
                'welcome_msg': '欢迎新成员 [CQ:at,qq={qq}] 加入本群！',
                'private_msg': '欢迎加入本群！请遵守群规。',
                'name_prefix': '新人·',
                'min_level': 0,
                'join_action': '审核'  # 审核/同意/拒绝/忽略
            }
        
        settings = self.data_manager.join_settings[group_id_str]
        
        # 开/关入群提示
        if command in ["开入群提示", "关入群提示"]:
            enabled = command.startswith("开")
            settings['welcome_enabled'] = enabled
            await self.data_manager._save_json('join_settings', self.data_manager.join_settings)
            await self.api.send_group_msg(group_id, f"已{'开启' if enabled else '关闭'}入群提示")
            return True
        
        # 开/关入群禁言
        elif command in ["开入群禁言", "关入群禁言"]:
            enabled = command.startswith("开")
            settings['mute_enabled'] = enabled
            await self.data_manager._save_json('join_settings', self.data_manager.join_settings)
            await self.api.send_group_msg(group_id, f"已{'开启' if enabled else '关闭'}入群禁言")
            return True
        
        # 开/关入群审核
        elif command in ["开入群审核", "关入群审核"]:
            enabled = command.startswith("开")
            settings['audit_enabled'] = enabled
            await self.data_manager._save_json('join_settings', self.data_manager.join_settings)
            await self.api.send_group_msg(group_id, f"已{'开启' if enabled else '关闭'}入群审核")
            return True
        
        # 开/关入群私聊
        elif command in ["开入群私聊", "关入群私聊"]:
            enabled = command.startswith("开")
            settings['private_msg_enabled'] = enabled
            await self.data_manager._save_json('join_settings', self.data_manager.join_settings)
            await self.api.send_group_msg(group_id, f"已{'开启' if enabled else '关闭'}入群私聊")
            return True
        
        # 开/关入群改名片
        elif command in ["开入群改名片", "关入群改名片"]:
            enabled = command.startswith("开")
            settings['auto_rename_enabled'] = enabled
            await self.data_manager._save_json('join_settings', self.data_manager.join_settings)
            await self.api.send_group_msg(group_id, f"已{'开启' if enabled else '关闭'}入群改名片")
            return True
        
        # 查看入群设置变量
        elif command == "查看入群设置变量":
            msg = f"""入群设置
入群提示：{'开启' if settings.get('welcome_enabled') else '关闭'}
入群禁言：{'开启' if settings.get('mute_enabled') else '关闭'}
入群审核：{'开启' if settings.get('audit_enabled') else '关闭'}
入群私聊：{'开启' if settings.get('private_msg_enabled') else '关闭'}
入群改名片：{'开启' if settings.get('auto_rename_enabled') else '关闭'}
-
禁言时长：{settings.get('mute_duration', 60)}秒
名片前缀：{settings.get('name_prefix', '新人·')}
最低等级：{settings.get('min_level', 0)}级
入群处理：{settings.get('join_action', '审核')}"""
            await self.api.send_group_msg(group_id, msg)
            return True
        
        # 设置入群禁言时间+时间
        elif raw_message.startswith("设置入群禁言时间"):
            time_str = raw_message.replace("设置入群禁言时间", "").strip()
            seconds = utils.parse_time_string(time_str)
            if not seconds:
                await self.api.send_group_msg(group_id, "时间格式错误，格式：设置入群禁言时间60 或 设置入群禁言时间1分钟")
                return True
            
            settings['mute_duration'] = seconds
            await self.data_manager._save_json('join_settings', self.data_manager.join_settings)
            await self.api.send_group_msg(group_id, f"已设置入群禁言时间为 {utils.format_time(seconds)}")
            return True
        
        # 设置入群提示内容+内容
        elif raw_message.startswith("设置入群提示内容"):
            content = raw_message.replace("设置入群提示内容", "").strip()
            if not content:
                await self.api.send_group_msg(group_id, "请输入提示内容，可用变量：{qq} {nickname}")
                return True
            
            settings['welcome_msg'] = content
            await self.data_manager._save_json('join_settings', self.data_manager.join_settings)
            await self.api.send_group_msg(group_id, f"已设置入群提示内容")
            return True
        
        # 设置入群私聊内容+内容
        elif raw_message.startswith("设置入群私聊内容"):
            content = raw_message.replace("设置入群私聊内容", "").strip()
            if not content:
                await self.api.send_group_msg(group_id, "请输入私聊内容")
                return True
            
            settings['private_msg'] = content
            await self.data_manager._save_json('join_settings', self.data_manager.join_settings)
            await self.api.send_group_msg(group_id, f"已设置入群私聊内容")
            return True
        
        # 设置入群名片前缀+前缀
        elif raw_message.startswith("设置入群名片前缀"):
            prefix = raw_message.replace("设置入群名片前缀", "").strip()
            settings['name_prefix'] = prefix
            await self.data_manager._save_json('join_settings', self.data_manager.join_settings)
            await self.api.send_group_msg(group_id, f"已设置入群名片前缀：{prefix}")
            return True
        
        # 设置入群最低等级+级数
        elif raw_message.startswith("设置入群最低等级"):
            level = utils.extract_number_from_text(raw_message)
            if level is None:
                await self.api.send_group_msg(group_id, "请输入等级数字")
                return True
            
            settings['min_level'] = level
            await self.data_manager._save_json('join_settings', self.data_manager.join_settings)
            await self.api.send_group_msg(group_id, f"已设置入群最低等级：{level}级")
            return True
        
        # 设置入群自动/同意/拒绝/忽略
        elif raw_message.startswith("设置入群"):
            if "同意" in raw_message:
                action = "同意"
            elif "拒绝" in raw_message:
                action = "拒绝"
            elif "忽略" in raw_message:
                action = "忽略"
            elif "审核" in raw_message or "自动" in raw_message:
                action = "审核"
            else:
                return False
            
            settings['join_action'] = action
            await self.data_manager._save_json('join_settings', self.data_manager.join_settings)
            await self.api.send_group_msg(group_id, f"已设置入群处理方式：{action}")
            return True
        
        return False
    
    async def handle_group_increase(self, event: Dict):
        """处理群成员增加事件"""
        try:
            group_id = event.get('group_id')
            user_id = event.get('user_id')
            
            group_id_str = str(group_id)
            settings = self.data_manager.join_settings.get(group_id_str, {})
            
            # 入群提示
            if settings.get('welcome_enabled'):
                welcome_msg = settings.get('welcome_msg', '欢迎新成员加入本群！')
                welcome_msg = welcome_msg.replace('{qq}', str(user_id))
                
                # 获取昵称
                try:
                    result = await self.api.call_api('get_stranger_info', {'user_id': user_id})
                    if result.get('success'):
                        nickname = result.get('data', {}).get('nickname', '')
                        welcome_msg = welcome_msg.replace('{nickname}', nickname)
                except:
                    pass
                
                await self.api.send_group_msg(group_id, welcome_msg)
            
            # 入群禁言
            if settings.get('mute_enabled'):
                duration = settings.get('mute_duration', 60)
                await self.api.call_api('set_group_ban', {
                    'group_id': group_id,
                    'user_id': user_id,
                    'duration': duration
                })
            
            # 入群私聊
            if settings.get('private_msg_enabled'):
                private_msg = settings.get('private_msg', '欢迎加入本群！')
                await self.api.send_private_msg(user_id, private_msg)
            
            # 入群改名片
            if settings.get('auto_rename_enabled'):
                prefix = settings.get('name_prefix', '新人·')
                # 获取当前名片
                try:
                    result = await self.api.call_api('get_group_member_info', {
                        'group_id': group_id,
                        'user_id': user_id
                    })
                    if result.get('success'):
                        member_info = result.get('data', {})
                        current_card = member_info.get('card', '')
                        nickname = member_info.get('nickname', '')
                        
                        new_card = prefix + (current_card if current_card else nickname)
                        
                        await self.api.call_api('set_group_card', {
                            'group_id': group_id,
                            'user_id': user_id,
                            'card': new_card
                        })
                except Exception as e:
                    self.api.log("error", f"修改名片失败: {e}")
        
        except Exception as e:
            self.api.log("error", f"处理入群事件失败: {e}")

