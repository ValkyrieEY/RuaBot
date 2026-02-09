"""留言反馈、名片系统、远程系统、通知系统、卡密系统、头衔系统等其他功能模块"""

import time
import random
import string
from typing import Dict
from datetime import datetime, timedelta
import sys
from pathlib import Path

# 添加父目录到路径
parent_dir = Path(__file__).parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from utils import utils


class MessageFeedbackModule:
    """留言反馈模块"""
    
    def __init__(self, api, data_manager, permission_manager):
        self.api = api
        self.data_manager = data_manager
        self.permission_manager = permission_manager
    
    async def handle_command(self, event: Dict, command: str) -> bool:
        """处理留言反馈指令"""
        user_id = event.get('user_id')
        group_id = event.get('group_id')
        raw_message = event.get('raw_message', '').strip()
        
        group_id_str = str(group_id)
        
        # 初始化设置
        if group_id_str not in self.data_manager.feedback_settings:
            self.data_manager.feedback_settings[group_id_str] = {
                'enabled': True,
                'notify_enabled': True
            }
        
        settings = self.data_manager.feedback_settings[group_id_str]
        
        # 开/关留言反馈
        if command in ["开留言反馈", "关留言反馈"]:
            if not self.permission_manager.has_group_permission(user_id, group_id):
                return False
            
            enabled = command.startswith("开")
            settings['enabled'] = enabled
            await self.data_manager._save_json('feedback_settings', self.data_manager.feedback_settings)
            await self.api.send_group_msg(group_id, f"已{'开启' if enabled else '关闭'}留言反馈")
            return True
        
        # 开/关留言通知
        elif command in ["开留言通知", "关留言通知"]:
            if not self.permission_manager.has_group_permission(user_id, group_id):
                return False
            
            enabled = command.startswith("开")
            settings['notify_enabled'] = enabled
            await self.data_manager._save_json('feedback_settings', self.data_manager.feedback_settings)
            await self.api.send_group_msg(group_id, f"已{'开启' if enabled else '关闭'}留言通知")
            return True
        
        # 检查是否启用
        if not settings.get('enabled', True):
            return False
        
        # 留言/反馈#内容
        if raw_message.startswith(("留言#", "反馈#")):
            is_feedback = raw_message.startswith("反馈")
            parts = raw_message.split('#', 1)
            if len(parts) < 2 or not parts[1].strip():
                await self.api.send_group_msg(group_id, "请输入内容，格式：留言#内容 或 反馈#内容")
                return True
            
            content = parts[1].strip()
            msg_id = len(self.data_manager.messages) + 1
            
            msg_data = {
                'id': msg_id,
                'user_id': user_id,
                'group_id': group_id,
                'content': content,
                'type': '反馈' if is_feedback else '留言',
                'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            self.data_manager.messages.append(msg_data)
            await self.data_manager._save_json('messages', self.data_manager.messages)
            
            await self.api.send_group_msg(group_id, f"{'反馈' if is_feedback else '留言'}已提交，ID:{msg_id}")
            
            # 如果是反馈，通知主人（如果通知开启）
            if is_feedback and settings.get('notify_enabled', True) and self.permission_manager.owners:
                try:
                    owner_qq = self.permission_manager.owners[0]
                    notify_msg = f"收到新反馈（ID:{msg_id}）\n来自：{user_id}\n群：{group_id}\n内容：{content}"
                    await self.api.send_private_msg(owner_qq, notify_msg)
                except Exception as e:
                    # 通知失败时不影响主流程，只记录日志
                    self.api.log("warning", f"向主人发送反馈通知失败: {e}")
            
            return True
        
        # 删除留言/反馈#ID
        elif raw_message.startswith(("删除留言#", "删除反馈#")):
            if not self.permission_manager.has_group_permission(user_id, group_id):
                return False
            
            msg_id = utils.extract_number_from_text(raw_message)
            if not msg_id:
                await self.api.send_group_msg(group_id, "请指定ID")
                return True
            
            # 查找并删除
            original_len = len(self.data_manager.messages)
            self.data_manager.messages = [m for m in self.data_manager.messages if m['id'] != msg_id]
            
            if len(self.data_manager.messages) < original_len:
                await self.data_manager._save_json('messages', self.data_manager.messages)
                await self.api.send_group_msg(group_id, f"已删除ID:{msg_id}的记录")
            else:
                await self.api.send_group_msg(group_id, "未找到该记录")
            return True
        
        # 查看留言/反馈列表
        elif command in ["查看留言列表", "查看反馈列表"]:
            if not self.permission_manager.has_group_permission(user_id, group_id):
                return False
            
            msg_type = "留言" if "留言" in command else "反馈"
            filtered_msgs = [m for m in self.data_manager.messages if m['type'] == msg_type]
            
            if not filtered_msgs:
                await self.api.send_group_msg(group_id, f"{msg_type}列表为空")
                return True
            
            msg = f"{msg_type}列表（共{len(filtered_msgs)}条）\n"
            for m in filtered_msgs[:10]:
                msg += f"ID:{m['id']} | {m['user_id']} | {m['time']}\n"
            if len(filtered_msgs) > 10:
                msg += f"... 还有{len(filtered_msgs)-10}条\n"
            
            await self.api.send_group_msg(group_id, msg)
            return True
        
        # 清空留言/反馈列表
        elif command in ["清空留言列表", "清空反馈列表"]:
            if not self.permission_manager.has_group_permission(user_id, group_id):
                return False
            
            msg_type = "留言" if "留言" in command else "反馈"
            original_len = len(self.data_manager.messages)
            self.data_manager.messages = [m for m in self.data_manager.messages if m['type'] != msg_type]
            
            deleted_count = original_len - len(self.data_manager.messages)
            await self.data_manager._save_json('messages', self.data_manager.messages)
            await self.api.send_group_msg(group_id, f"已清空{msg_type}列表，删除{deleted_count}条记录")
            return True
        
        # 查看留言/反馈#ID
        elif raw_message.startswith(("查看留言#", "查看反馈#")):
            if not self.permission_manager.has_group_permission(user_id, group_id):
                return False
            
            msg_id = utils.extract_number_from_text(raw_message)
            if not msg_id:
                await self.api.send_group_msg(group_id, "请指定ID")
                return True
            
            msg = next((m for m in self.data_manager.messages if m['id'] == msg_id), None)
            if not msg:
                await self.api.send_group_msg(group_id, "未找到该记录")
                return True
            
            info = f"""{msg['type']}详情
ID：{msg['id']}
用户：{msg['user_id']}
群：{msg['group_id']}
时间：{msg['time']}
内容：{msg['content']}"""
            await self.api.send_group_msg(group_id, info)
            return True
        
        return False


class CardSystemModule:
    """名片系统模块"""
    
    def __init__(self, api, data_manager, permission_manager):
        self.api = api
        self.data_manager = data_manager
        self.permission_manager = permission_manager
    
    async def handle_command(self, event: Dict, command: str) -> bool:
        """处理名片系统指令"""
        user_id = event.get('user_id')
        group_id = event.get('group_id')
        raw_message = event.get('raw_message', '').strip()
        message = event.get('message', [])
        
        if not self.permission_manager.has_group_permission(user_id, group_id):
            return False
        
        group_id_str = str(group_id)
        
        # 开/关发言改名
        if command in ["开发言改名", "关发言改名"]:
            if group_id_str not in self.data_manager.card_settings:
                self.data_manager.card_settings[group_id_str] = {'auto_rename': False, 'prefix': ''}
            
            enabled = command.startswith("开")
            self.data_manager.card_settings[group_id_str]['auto_rename'] = enabled
            await self.data_manager._save_json('card_settings', self.data_manager.card_settings)
            await self.api.send_group_msg(group_id, f"已{'开启' if enabled else '关闭'}发言改名")
            return True
        
        # 改名@QQ+名片
        elif raw_message.startswith("改名"):
            at_list = utils.parse_at(message)
            if not at_list:
                await self.api.send_group_msg(group_id, "请@要改名的用户")
                return True
            
            target_qq = at_list[0]
            card_name = raw_message.replace("改名", "").replace(f"[CQ:at,qq={target_qq}]", "").strip()
            
            if not card_name:
                await self.api.send_group_msg(group_id, "请指定名片内容")
                return True
            
            try:
                await self.api.call_api('set_group_card', group_id=group_id, user_id=target_qq, card=card_name)
                await self.api.send_group_msg(group_id, f"已修改 {target_qq} 的名片为：{card_name}")
            except Exception as e:
                await self.api.send_group_msg(group_id, f"修改名片失败：{e}")
            return True
        
        # 取消锁定@QQ/+QQ
        elif raw_message.startswith("取消锁定"):
            target_qq = utils.extract_number_from_text(raw_message)
            if not target_qq:
                at_list = utils.parse_at(message)
                if at_list:
                    target_qq = at_list[0]
            
            if not target_qq:
                await self.api.send_group_msg(group_id, "请指定QQ号")
                return True
            
            if group_id_str in self.data_manager.card_locks:
                if str(target_qq) in self.data_manager.card_locks[group_id_str]:
                    del self.data_manager.card_locks[group_id_str][str(target_qq)]
                    await self.data_manager._save_json('card_locks', self.data_manager.card_locks)
                    await self.api.send_group_msg(group_id, f"已取消锁定 {target_qq} 的名片")
                else:
                    await self.api.send_group_msg(group_id, "该用户未锁定名片")
            else:
                await self.api.send_group_msg(group_id, "该用户未锁定名片")
            return True
        
        # 锁定名片@QQ+名片
        elif raw_message.startswith("锁定名片"):
            at_list = utils.parse_at(message)
            if not at_list:
                await self.api.send_group_msg(group_id, "请@要锁定的用户")
                return True
            
            target_qq = at_list[0]
            card_name = raw_message.replace("锁定名片", "").replace(f"[CQ:at,qq={target_qq}]", "").strip()
            
            if not card_name:
                await self.api.send_group_msg(group_id, "请指定名片内容")
                return True
            
            if group_id_str not in self.data_manager.card_locks:
                self.data_manager.card_locks[group_id_str] = {}
            
            self.data_manager.card_locks[group_id_str][str(target_qq)] = card_name
            await self.data_manager._save_json('card_locks', self.data_manager.card_locks)
            
            # 立即修改名片
            await self.api.call_api('set_group_card', group_id=group_id, user_id=target_qq, card=card_name)
            
            await self.api.send_group_msg(group_id, f"已锁定 {target_qq} 的名片为：{card_name}")
            return True
        
        # 查看锁定成员列表
        elif command == "查看锁定成员列表":
            if group_id_str not in self.data_manager.card_locks or not self.data_manager.card_locks[group_id_str]:
                await self.api.send_group_msg(group_id, "锁定成员列表为空")
                return True
            
            locks = self.data_manager.card_locks[group_id_str]
            msg = f"锁定成员列表（共{len(locks)}人）\n"
            for qq, card in locks.items():
                msg += f"  {qq}: {card}\n"
            
            await self.api.send_group_msg(group_id, msg)
            return True
        
        # 设置发言名片前缀+前缀
        elif raw_message.startswith("设置发言名片前缀"):
            prefix = raw_message.replace("设置发言名片前缀", "").strip()
            
            if group_id_str not in self.data_manager.card_settings:
                self.data_manager.card_settings[group_id_str] = {'auto_rename': False, 'prefix': ''}
            
            self.data_manager.card_settings[group_id_str]['prefix'] = prefix
            await self.data_manager._save_json('card_settings', self.data_manager.card_settings)
            await self.api.send_group_msg(group_id, f"已设置发言名片前缀：{prefix}")
            return True
        
        # 查看发言名片前缀
        elif command == "查看发言名片前缀":
            if group_id_str not in self.data_manager.card_settings:
                prefix = ""
            else:
                prefix = self.data_manager.card_settings[group_id_str].get('prefix', '')
            
            await self.api.send_group_msg(group_id, f"发言名片前缀：{prefix if prefix else '未设置'}")
            return True
        
        return False
    
    async def handle_message(self, event: Dict):
        """处理消息事件（用于发言改名）"""
        try:
            group_id = event.get('group_id')
            user_id = event.get('user_id')
            
            if not group_id:
                return
            
            group_id_str = str(group_id)
            
            # 检查是否开启发言改名
            settings = self.data_manager.card_settings.get(group_id_str, {})
            if not settings.get('auto_rename', False):
                return
            
            # 检查是否有权限（有权限的用户不自动改名）
            if self.permission_manager.has_group_permission(user_id, group_id):
                return
            
            # 检查是否锁定名片
            if group_id_str in self.data_manager.card_locks:
                if str(user_id) in self.data_manager.card_locks[group_id_str]:
                    # 已锁定，不处理
                    return
            
            # 获取用户信息
            try:
                member_info = await self.api.call_api('get_group_member_info', group_id=group_id, user_id=user_id)
                if member_info:
                    current_card = member_info.get('card', '')
                    nickname = member_info.get('nickname', '')
                    
                    # 如果名片为空，使用昵称
                    if not current_card:
                        current_card = nickname
                    
                    # 检查是否需要改名（添加前缀）
                    settings = self.data_manager.card_settings.get(group_id_str, {})
                    prefix = settings.get('prefix', '')
                    
                    if prefix and current_card:
                        # 如果名片已经有前缀，不重复添加
                        if not current_card.startswith(prefix):
                            new_card = prefix + current_card
                            try:
                                await self.api.call_api('set_group_card', group_id=group_id, user_id=user_id, card=new_card)
                            except Exception as e:
                                self.api.log("error", f"自动改名失败: {e}")
            except Exception as e:
                self.api.log("error", f"获取群成员信息失败: {e}")
        
        except Exception as e:
            self.api.log("error", f"处理名片系统消息失败: {e}")


class RemoteModule:
    """远程系统模块"""
    
    def __init__(self, api, data_manager, permission_manager):
        self.api = api
        self.data_manager = data_manager
        self.permission_manager = permission_manager
    
    async def handle_command(self, event: Dict, command: str) -> bool:
        """处理远程系统指令"""
        user_id = event.get('user_id')
        group_id = event.get('group_id')
        raw_message = event.get('raw_message', '').strip()
        
        # 只有主人和管理员可用
        if not self.permission_manager.is_owner_or_admin(user_id):
            return False
        
        # 远程全体禁言+群号
        if raw_message.startswith("远程全体禁言"):
            target_group = utils.extract_number_from_text(raw_message)
            if not target_group:
                await self.api.send_group_msg(group_id, "请指定群号")
                return True
            
            result = await self.api.call_api('set_group_whole_ban',
                group_id=target_group,
                enable=True
            )
            
            if result.get('success'):
                await self.api.send_group_msg(group_id, f"已对群 {target_group} 执行全体禁言")
            else:
                await self.api.send_group_msg(group_id, f"操作失败")
            return True
        
        # 远程发送#群号#内容
        elif raw_message.startswith("远程发送#"):
            parts = raw_message.split('#')
            if len(parts) < 3:
                await self.api.send_group_msg(group_id, "格式错误，格式：远程发送#群号#内容")
                return True
            
            target_group = int(parts[1]) if parts[1].isdigit() else None
            content = parts[2]
            
            if not target_group:
                await self.api.send_group_msg(group_id, "群号错误")
                return True
            
            try:
                result = await self.api.send_group_msg(target_group, content)
                # 检查返回结果：可能是 {'success': True, 'data': {...}} 或 {'message_id': ...} 或直接是 message_id
                success = False
                if isinstance(result, dict):
                    # 检查 success 字段
                    if result.get('success') is True:
                        success = True
                    # 或者有 message_id 字段也表示成功
                    elif 'message_id' in result:
                        success = True
                    # 或者有 data 字段且 data 中有 message_id
                    elif 'data' in result and isinstance(result.get('data'), dict) and 'message_id' in result.get('data', {}):
                        success = True
                # 如果返回的是整数或字符串（message_id），也表示成功
                elif isinstance(result, (int, str)) and result:
                    success = True
                # 如果返回 None 但没抛异常，也认为成功
                elif result is None:
                    success = True
                
                if success:
                    await self.api.send_group_msg(group_id, f"已发送消息到群 {target_group}")
                else:
                    error_msg = result.get('error', '未知错误') if isinstance(result, dict) else str(result)
                    await self.api.send_group_msg(group_id, f"发送失败：{error_msg}")
            except Exception as e:
                await self.api.send_group_msg(group_id, f"发送失败：{e}")
            return True
        
        return False


class NotificationModule:
    """通知系统模块"""
    
    def __init__(self, api, data_manager, permission_manager):
        self.api = api
        self.data_manager = data_manager
        self.permission_manager = permission_manager
    
    async def handle_command(self, event: Dict, command: str) -> bool:
        """处理通知系统指令"""
        user_id = event.get('user_id')
        group_id = event.get('group_id')
        raw_message = event.get('raw_message', '').strip()
        
        # 艾特全体+内容
        if raw_message.startswith("艾特全体"):
            content = raw_message.replace("艾特全体", "").strip()
            msg = "[CQ:at,qq=all]"
            if content:
                msg += f" {content}"
            
            await self.api.send_group_msg(group_id, msg)
            return True
        
        # 艾特管理+内容
        elif raw_message.startswith("艾特管理"):
            try:
                # 获取群管理列表
                result = await self.api.call_api('get_group_member_list', group_id=group_id)
                
                # 处理不同的返回格式
                members = []
                if isinstance(result, list):
                    # 直接返回列表
                    members = result
                elif isinstance(result, dict):
                    if 'data' in result:
                        members = result['data']
                    elif result.get('success') and 'data' in result:
                        members = result['data']
                
                if not members:
                    await self.api.send_group_msg(group_id, "获取管理列表失败")
                    return True
                
                # 筛选管理员（群主和管理员）
                admins = [m['user_id'] for m in members if m.get('role') in ['owner', 'admin']]
                
                if not admins:
                    await self.api.send_group_msg(group_id, "未找到群管理员")
                    return True
                
                content = raw_message.replace("艾特管理", "").strip()
                msg = ""
                for admin_qq in admins:
                    msg += f"[CQ:at,qq={admin_qq}] "
                
                if content:
                    msg += content
                
                await self.api.send_group_msg(group_id, msg)
            except Exception as e:
                self.api.log("error", f"艾特管理失败: {e}")
                await self.api.send_group_msg(group_id, f"艾特管理失败：{e}")
            return True
        
        return False


class CardKeyModule:
    """卡密系统模块"""
    
    def __init__(self, api, data_manager, permission_manager):
        self.api = api
        self.data_manager = data_manager
        self.permission_manager = permission_manager
    
    def _generate_key(self) -> str:
        """生成随机卡密"""
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
    
    async def handle_command(self, event: Dict, command: str) -> bool:
        """处理卡密系统指令"""
        user_id = event.get('user_id')
        group_id = event.get('group_id')
        raw_message = event.get('raw_message', '').strip()
        
        # 生成月卡/季卡/年卡+数量
        if raw_message.startswith(("生成月卡", "生成季卡", "生成年卡")):
            if not self.permission_manager.is_owner_or_admin(user_id):
                await self.api.send_group_msg(group_id, "只有主人或管理员可以生成卡密")
                return True
            
            count = utils.extract_number_from_text(raw_message)
            if not count or count < 1:
                count = 1
            
            if "月卡" in raw_message:
                days = 30
            elif "季卡" in raw_message:
                days = 90
            elif "年卡" in raw_message:
                days = 365
            else:
                days = 30
            
            keys = []
            for _ in range(min(count, 10)):  # 最多一次生成10个
                key = self._generate_key()
                self.data_manager.card_keys[key] = {
                    'days': days,
                    'used': False,
                    'used_by': None,
                    'used_time': None,
                    'create_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                keys.append(key)
            
            await self.data_manager._save_json('card_keys', self.data_manager.card_keys)
            
            msg = f"已生成{len(keys)}个{days}天卡密：\n"
            for key in keys:
                msg += f"{key}\n"
            
            await self.api.send_group_msg(group_id, msg)
            return True
        
        # 使用卡密+卡密
        elif raw_message.startswith("使用卡密"):
            key = raw_message.replace("使用卡密", "").strip()
            if not key:
                await self.api.send_group_msg(group_id, "请输入卡密")
                return True
            
            if key not in self.data_manager.card_keys:
                await self.api.send_group_msg(group_id, "卡密不存在")
                return True
            
            key_data = self.data_manager.card_keys[key]
            if key_data['used']:
                await self.api.send_group_msg(group_id, f"卡密已被使用（使用者：{key_data['used_by']}）")
                return True
            
            # 标记为已使用
            key_data['used'] = True
            key_data['used_by'] = user_id
            key_data['used_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            await self.data_manager._save_json('card_keys', self.data_manager.card_keys)
            
            # 增加群授权
            group_id_str = str(group_id)
            days = key_data['days']
            
            if group_id_str not in self.data_manager.group_auth:
                self.data_manager.group_auth[group_id_str] = {
                    'authorized': True,
                    'expire_date': (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d'),
                    'auto_leave': False,
                    'notify_owner': True,
                    'notify_group': True
                }
            else:
                current_expire = self.data_manager.group_auth[group_id_str].get('expire_date', 'unlimited')
                if current_expire == 'unlimited':
                    new_expire = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
                else:
                    try:
                        expire_date = datetime.strptime(current_expire, '%Y-%m-%d')
                        new_expire = (expire_date + timedelta(days=days)).strftime('%Y-%m-%d')
                    except:
                        new_expire = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
                
                self.data_manager.group_auth[group_id_str]['expire_date'] = new_expire
                self.data_manager.group_auth[group_id_str]['authorized'] = True
            
            await self.data_manager._save_json('group_auth', self.data_manager.group_auth)
            
            await self.api.send_group_msg(group_id, f"卡密使用成功！已为本群增加 {days} 天授权")
            return True
        
        return False


class TitleModule:
    """头衔系统模块"""
    
    def __init__(self, api, data_manager, permission_manager):
        self.api = api
        self.data_manager = data_manager
        self.permission_manager = permission_manager
    
    async def handle_command(self, event: Dict, command: str) -> bool:
        """处理头衔系统指令"""
        user_id = event.get('user_id')
        group_id = event.get('group_id')
        raw_message = event.get('raw_message', '').strip()
        message = event.get('message', [])
        
        group_id_str = str(group_id)
        
        # 初始化设置
        if group_id_str not in self.data_manager.title_settings:
            self.data_manager.title_settings[group_id_str] = {
                'auto_enabled': False,
                'banned_words': []
            }
        
        settings = self.data_manager.title_settings[group_id_str]
        
        # 开/关自助头衔
        if command in ["开自助头衔", "关自助头衔"]:
            if not self.permission_manager.has_group_permission(user_id, group_id):
                return False
            
            enabled = command.startswith("开")
            settings['auto_enabled'] = enabled
            await self.data_manager._save_json('title_settings', self.data_manager.title_settings)
            await self.api.send_group_msg(group_id, f"已{'开启' if enabled else '关闭'}自助头衔")
            return True
        
        # 申请头衔+头衔
        elif raw_message.startswith("申请头衔"):
            if not settings.get('auto_enabled'):
                await self.api.send_group_msg(group_id, "自助头衔未开启")
                return True
            
            title = raw_message.replace("申请头衔", "").strip()
            if not title:
                await self.api.send_group_msg(group_id, "请输入头衔内容")
                return True
            
            # 检查违禁词
            for banned in settings.get('banned_words', []):
                if banned in title:
                    await self.api.send_group_msg(group_id, "头衔包含违禁词，无法设置")
                    return True
            
            # 设置头衔（需要机器人是群主）
            result = await self.api.call_api('set_group_special_title',
                group_id=group_id,
                user_id=user_id,
                special_title=title,
                duration=-1  # 永久
            )
            
            if result.get('success'):
                await self.api.send_group_msg(group_id, f"已设置头衔：{title}")
            else:
                await self.api.send_group_msg(group_id, "设置失败（需要机器人是群主）")
            return True
        
        # 授头衔@QQ+头衔
        elif raw_message.startswith("授头衔"):
            if not self.permission_manager.has_group_permission(user_id, group_id):
                return False
            
            at_list = utils.parse_at(message)
            if not at_list:
                await self.api.send_group_msg(group_id, "请@要授予头衔的用户")
                return True
            
            target_qq = at_list[0]
            title = raw_message.replace("授头衔", "").replace(f"[CQ:at,qq={target_qq}]", "").strip()
            
            if not title:
                await self.api.send_group_msg(group_id, "请输入头衔内容")
                return True
            
            result = await self.api.call_api('set_group_special_title',
                group_id=group_id,
                user_id=target_qq,
                special_title=title,
                duration=-1
            )
            
            if result.get('success'):
                await self.api.send_group_msg(group_id, f"已为 {target_qq} 设置头衔：{title}")
            else:
                await self.api.send_group_msg(group_id, "设置失败（需要机器人是群主）")
            return True
        
        return False


class ProfileModule:
    """资料修改模块"""
    
    def __init__(self, api, data_manager, permission_manager):
        self.api = api
        self.data_manager = data_manager
        self.permission_manager = permission_manager
    
    async def handle_command(self, event: Dict, command: str) -> bool:
        """处理资料修改指令"""
        user_id = event.get('user_id')
        group_id = event.get('group_id')
        raw_message = event.get('raw_message', '').strip()
        
        # 只有主人可用
        if not self.permission_manager.is_owner(user_id):
            return False
        
        # 修改个签+内容
        if raw_message.startswith("修改个签"):
            content = raw_message.replace("修改个签", "").strip()
            if not content:
                await self.api.send_group_msg(group_id, "请输入个签内容")
                return True
            
            try:
                # set_qq_profile 要求必须同时提供 nickname 和 personal_note
                # 获取当前昵称
                current_nickname = "Bot"  # 默认值
                try:
                    login_info = await self.api.call_api('get_login_info')
                    if login_info and isinstance(login_info, dict):
                        current_nickname = login_info.get('nickname', 'Bot')
                except:
                    # 如果获取失败，使用默认值
                    pass
                
                # 调用 API，同时传递 nickname 和 personal_note
                await self.api.call_api('set_qq_profile',
                    nickname=current_nickname,
                    personal_note=content
                )
                await self.api.send_group_msg(group_id, f"已修改个签：{content}")
            except Exception as e:
                await self.api.send_group_msg(group_id, f"修改个签失败：{e}")
            return True
        
        # 修改昵称+内容
        elif raw_message.startswith("修改昵称"):
            content = raw_message.replace("修改昵称", "").strip()
            if not content:
                await self.api.send_group_msg(group_id, "请输入昵称")
                return True
            
            try:
                # set_qq_profile 要求必须同时提供 nickname 和 personal_note
                # 个签可以为空，所以直接使用空字符串
                await self.api.call_api('set_qq_profile',
                    nickname=content,
                    personal_note=''  # 个签可以为空
                )
                await self.api.send_group_msg(group_id, f"已修改昵称：{content}")
            except Exception as e:
                await self.api.send_group_msg(group_id, f"修改昵称失败：{e}")
            return True
        
        return False


class NotificationSettingsModule:
    """提示系统模块"""
    
    def __init__(self, api, data_manager, permission_manager):
        self.api = api
        self.data_manager = data_manager
        self.permission_manager = permission_manager
    
    async def handle_command(self, event: Dict, command: str) -> bool:
        """处理提示系统指令"""
        user_id = event.get('user_id')
        group_id = event.get('group_id')
        
        if not self.permission_manager.has_group_permission(user_id, group_id):
            return False
        
        group_id_str = str(group_id)
        
        if group_id_str not in self.data_manager.notification_settings:
            self.data_manager.notification_settings[group_id_str] = {
                'join': False, 'leave': False,
                'promote': False, 'demote': False,
                'kick': False, 'ban': False,
                'unban': False, 'rename': False
            }
        
        settings = self.data_manager.notification_settings[group_id_str]
        
        # 开/关各类提示
        type_map = {
            "入群提示": "join",
            "退群提示": "leave",
            "上管提示": "promote",
            "下管提示": "demote",
            "被踢提示": "kick",
            "被禁提示": "ban",
            "解禁提示": "unban",
            "改名提示": "rename"
        }
        
        for cmd_name, setting_key in type_map.items():
            if command in [f"开{cmd_name}", f"关{cmd_name}"]:
                enabled = command.startswith("开")
                settings[setting_key] = enabled
                await self.data_manager._save_json('notification_settings', self.data_manager.notification_settings)
                await self.api.send_group_msg(group_id, f"已{'开启' if enabled else '关闭'}{cmd_name}")
                return True
        
        return False


class RecallSelfModule:
    """撤回自身模块"""
    
    def __init__(self, api, data_manager, permission_manager):
        self.api = api
        self.data_manager = data_manager
        self.permission_manager = permission_manager
        self.sent_messages = {}  # {group_id: [{message_id, time}]}
    
    async def handle_command(self, event: Dict, command: str) -> bool:
        """处理撤回自身指令"""
        user_id = event.get('user_id')
        group_id = event.get('group_id')
        raw_message = event.get('raw_message', '').strip()
        
        if not self.permission_manager.has_group_permission(user_id, group_id):
            return False
        
        group_id_str = str(group_id)
        
        # 开/关撤回自身
        if command in ["开撤回自身", "关撤回自身"]:
            if group_id_str not in self.data_manager.recall_self_settings:
                self.data_manager.recall_self_settings[group_id_str] = {'enabled': False, 'interval': 60}
            
            enabled = command.startswith("开")
            self.data_manager.recall_self_settings[group_id_str]['enabled'] = enabled
            await self.data_manager._save_json('recall_self_settings', self.data_manager.recall_self_settings)
            await self.api.send_group_msg(group_id, f"已{'开启' if enabled else '关闭'}撤回自身")
            return True
        
        # 设置撤回间隔
        elif raw_message.startswith("设置撤回间隔"):
            seconds = utils.extract_number_from_text(raw_message)
            if not seconds:
                await self.api.send_group_msg(group_id, "请指定秒数")
                return True
            
            if group_id_str not in self.data_manager.recall_self_settings:
                self.data_manager.recall_self_settings[group_id_str] = {'enabled': False, 'interval': 60}
            
            self.data_manager.recall_self_settings[group_id_str]['interval'] = seconds
            await self.data_manager._save_json('recall_self_settings', self.data_manager.recall_self_settings)
            await self.api.send_group_msg(group_id, f"已设置撤回间隔为 {seconds}秒")
            return True
        
        return False
    
    async def handle_message_sent(self, event: Dict):
        """处理消息发送事件（用于撤回自身消息）"""
        try:
            group_id = event.get('group_id')
            message_id = event.get('message_id')
            user_id = event.get('user_id')
            
            if not group_id or not message_id:
                return
            
            # 检查是否是机器人自己发送的消息
            # 需要获取机器人自己的QQ号，这里假设从API获取
            # 如果无法判断，可以记录所有消息，然后在定时任务中检查
            
            group_id_str = str(group_id)
            settings = self.data_manager.recall_self_settings.get(group_id_str, {})
            
            if not settings.get('enabled', False):
                return
            
            interval = settings.get('interval', 60)
            
            # 记录消息
            if group_id_str not in self.sent_messages:
                self.sent_messages[group_id_str] = []
            
            import asyncio
            from datetime import datetime
            
            self.sent_messages[group_id_str].append({
                'message_id': message_id,
                'time': datetime.now()
            })
            
            # 延迟撤回
            async def recall_message():
                await asyncio.sleep(interval)
                try:
                    await self.api.call_api('delete_msg', message_id=message_id)
                except Exception as e:
                    self.api.log("error", f"撤回消息失败: {e}")
            
            asyncio.create_task(recall_message())
        
        except Exception as e:
            self.api.log("error", f"处理撤回自身消息失败: {e}")


class ReplySettingsModule:
    """回复设置模块"""
    
    def __init__(self, api, data_manager, permission_manager):
        self.api = api
        self.data_manager = data_manager
        self.permission_manager = permission_manager
        
        # reply_settings已在data_manager中初始化，无需再次初始化
    
    async def handle_command(self, event: Dict, command: str) -> bool:
        """处理回复设置指令"""
        user_id = event.get('user_id')
        group_id = event.get('group_id')
        group_id_str = str(group_id)
        
        if not self.permission_manager.has_group_permission(user_id, group_id):
            return False
        
        # 初始化群设置
        if group_id_str not in self.data_manager.reply_settings:
            self.data_manager.reply_settings[group_id_str] = {'at_reply': False, 'silent_mode': False}
        
        settings = self.data_manager.reply_settings[group_id_str]
        
        # 开/关艾特发送
        if command in ["开艾特发送", "关艾特发送"]:
            enabled = command.startswith("开")
            settings['at_reply'] = enabled
            await self.data_manager._save_json('reply_settings', self.data_manager.reply_settings)
            await self.api.send_group_msg(group_id, f"已{'开启' if enabled else '关闭'}艾特发送")
            return True
        
        # 开/关静默模式
        elif command in ["开静默模式", "关静默模式"]:
            enabled = command.startswith("开")
            settings['silent_mode'] = enabled
            await self.data_manager._save_json('reply_settings', self.data_manager.reply_settings)
            await self.api.send_group_msg(group_id, f"已{'开启' if enabled else '关闭'}静默模式")
            return True
        
        return False
    
    def is_at_reply_enabled(self, group_id: int) -> bool:
        """检查是否启用了艾特发送"""
        group_id_str = str(group_id)
        if group_id_str not in self.data_manager.reply_settings:
            return False
        return self.data_manager.reply_settings[group_id_str].get('at_reply', False)
    
    def is_silent_mode_enabled(self, group_id: int) -> bool:
        """检查是否启用了静默模式"""
        group_id_str = str(group_id)
        if group_id_str not in self.data_manager.reply_settings:
            return False
        return self.data_manager.reply_settings[group_id_str].get('silent_mode', False)
    
    def format_reply_message(self, group_id: int, message: str, user_id: int = None) -> str:
        """格式化回复消息（如果需要@用户则添加@）
        
        Args:
            group_id: 群号
            message: 原始消息
            user_id: 发送者QQ号（用于@）
        
        Returns:
            格式化后的消息
        """
        if user_id and self.is_at_reply_enabled(group_id):
            return f"[CQ:at,qq={user_id}] {message}"
        return message


class OwnerModule:
    """主人权限模块"""
    
    def __init__(self, api, data_manager, permission_manager):
        self.api = api
        self.data_manager = data_manager
        self.permission_manager = permission_manager
    
    async def handle_command(self, event: Dict, command: str) -> bool:
        """处理主人权限指令"""
        user_id = event.get('user_id')
        group_id = event.get('group_id')
        
        # 只有主人可用
        if not self.permission_manager.is_owner(user_id):
            return False
        
        # 插件版本
        if command == "插件版本":
            await self.api.send_group_msg(group_id, "小依群管插件\n版本：v1.0.0\n作者：XQNEXT")
            return True
        
        # 框架版本
        elif command == "框架版本":
            await self.api.send_group_msg(group_id, "XQNEXT框架\n版本：请查看框架信息")
            return True
        
        # 变量列表
        elif command == "变量列表":
            msg = f"""插件数据统计
授权群数：{len(self.data_manager.group_auth)}
权限配置：{len(self.data_manager.permissions)}
黑名单：{len(self.data_manager.blacklist.get('groups', {}))}
问答数量：{len(self.data_manager.qa_system.get('groups', {}))}
卡密数量：{len(self.data_manager.card_keys)}"""
            await self.api.send_group_msg(group_id, msg)
            return True
        
        # 重启插件
        elif command == "重启插件":
            try:
                # 获取插件名称
                plugin_name = self.api.get_plugin_name() if hasattr(self.api, 'get_plugin_name') else 'group_manager'
                
                # 插件运行在runtime进程中，可以通过runtime.reload_plugin来重新加载自己
                # 检查API是否有runtime属性（runtime进程中的PluginAPI）
                if hasattr(self.api, 'runtime') and hasattr(self.api.runtime, 'reload_plugin'):
                    # 先发送消息
                    await self.api.send_group_msg(group_id, "正在重启插件...")
                    
                    # 保存重启信息到文件，以便新实例加载时发送成功消息
                    import json
                    import os
                    from pathlib import Path
                    
                    # 获取插件数据目录
                    plugin_dir = Path(__file__).parent.parent
                    data_dir = plugin_dir / "data"
                    data_dir.mkdir(exist_ok=True)
                    
                    # 保存重启信息
                    reload_info = {
                        'group_id': group_id,
                        'user_id': user_id,
                        'timestamp': time.time()
                    }
                    reload_info_file = data_dir / "reload_info.json"
                    try:
                        with open(reload_info_file, 'w', encoding='utf-8') as f:
                            json.dump(reload_info, f)
                    except Exception as e:
                        self.api.log("warning", f"保存重启信息失败: {e}")
                    
                    # 通过消息请求主进程执行重启（确保配置正确传递）
                    # 使用asyncio.create_task在后台执行重启，避免阻塞当前消息处理
                    import asyncio
                    async def do_reload():
                        try:
                            # 稍微延迟一下，确保消息已经发送完成
                            await asyncio.sleep(0.3)
                            
                            # 通过消息请求主进程执行重启
                            # 这样主进程可以从数据库获取最新配置并传递
                            import uuid
                            request_id = str(uuid.uuid4())
                            future = asyncio.get_event_loop().create_future()
                            self.api.runtime.pending_requests[request_id] = future
                            
                            # 发送重启请求到主进程
                            self.api.runtime.send_message({
                                'type': 'reload_plugin_request',
                                'data': {
                                    'request_id': request_id,
                                    'plugin_name': plugin_name
                                }
                            })
                            
                            # 等待响应（但不需要处理结果，因为插件会被卸载）
                            try:
                                await asyncio.wait_for(future, timeout=5.0)
                            except asyncio.TimeoutError:
                                self.api.log("warning", "重启插件请求超时，但可能已成功")
                            except Exception as e:
                                self.api.log("warning", f"重启插件请求响应错误: {e}")
                        except Exception as e:
                            # 如果重启失败，记录错误并删除重启信息文件
                            self.api.log("error", f"通过消息请求重启插件失败: {e}")
                            try:
                                if reload_info_file.exists():
                                    reload_info_file.unlink()
                            except:
                                pass
                    
                    # 在后台任务中执行重启，不等待完成
                    asyncio.create_task(do_reload())
                    # 立即返回，不等待重启完成
                    return True
                else:
                    # 如果没有runtime属性，说明可能是在主进程中（不应该发生）
                    await self.api.send_group_msg(group_id, "插件重启功能需要runtime支持，请手动重启或通过Web界面重启")
                    return True
            except Exception as e:
                self.api.log("error", f"重启插件失败: {e}")
                await self.api.send_group_msg(group_id, f"插件重启失败：{e}，请手动重启")
                return True
        
        # 退出本群
        elif command == "退出本群":
            await self.api.send_group_msg(group_id, "机器人即将退出本群")
            result = await self.api.call_api('set_group_leave', group_id=group_id)
            if not result.get('success'):
                await self.api.send_group_msg(group_id, f"退群失败：{result.get('error')}")
            return True
        
        return False

