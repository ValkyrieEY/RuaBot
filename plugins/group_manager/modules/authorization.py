"""授权中心模块 - 管理群授权"""

from datetime import datetime, timedelta
from typing import Dict, Optional
import sys
from pathlib import Path

# 添加父目录到路径
parent_dir = Path(__file__).parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from utils import utils


class AuthorizationModule:
    """授权中心模块"""
    
    def __init__(self, api, data_manager, permission_manager):
        self.api = api
        self.data_manager = data_manager
        self.permission_manager = permission_manager
    
    async def handle_command(self, event: Dict, command: str) -> bool:
        """处理授权相关指令"""
        user_id = event.get('user_id')
        group_id = event.get('group_id')
        raw_message = event.get('raw_message', '').strip()
        
        group_id_str = str(group_id) if group_id else None
        
        # 授权本群
        if command == "授权本群":
            if not self.permission_manager.is_owner_or_admin(user_id):
                await self.api.send_group_msg(group_id, "只有主人或管理员可以授权群")
                return True
            
            if group_id_str not in self.data_manager.group_auth:
                self.data_manager.group_auth[group_id_str] = {
                    'authorized': True,
                    'expire_date': 'unlimited',
                    'auto_leave': False,
                    'notify_owner': True,
                    'notify_group': True
                }
            else:
                self.data_manager.group_auth[group_id_str]['authorized'] = True
            
            await self.data_manager._save_json('group_auth', self.data_manager.group_auth)
            await self.api.send_group_msg(group_id, "本群已授权（无限期）")
            return True
        
        # 查询本群授权
        elif command == "查询本群授权":
            auth_info = self.data_manager.group_auth.get(group_id_str, {})
            if not auth_info.get('authorized', False):
                await self.api.send_group_msg(group_id, "本群未授权")
                return True
            
            expire = auth_info.get('expire_date', 'unlimited')
            if expire == 'unlimited':
                msg = "本群授权状态：已授权\n到期时间：无限期"
            else:
                msg = f"本群授权状态：已授权\n到期时间：{expire}"
            
            await self.api.send_group_msg(group_id, msg)
            return True
        
        # 删除本群授权
        elif command == "删除本群授权":
            if not self.permission_manager.is_owner_or_admin(user_id):
                await self.api.send_group_msg(group_id, "只有主人或管理员可以删除授权")
                return True
            
            if group_id_str in self.data_manager.group_auth:
                self.data_manager.group_auth[group_id_str]['authorized'] = False
                await self.data_manager._save_json('group_auth', self.data_manager.group_auth)
            
            await self.api.send_group_msg(group_id, "本群授权已删除")
            return True
        
        # 本群开机
        elif command == "本群开机":
            if not self.permission_manager.has_group_permission(user_id, group_id):
                await self.api.send_group_msg(group_id, "权限不足")
                return True
            
            # 如果没有授权，自动授权无限期
            if group_id_str not in self.data_manager.group_auth or not self.data_manager.group_auth[group_id_str].get('authorized', False):
                self.data_manager.group_auth[group_id_str] = {
                    'authorized': True,
                    'expire_date': 'unlimited',
                    'auto_leave': False,
                    'notify_owner': True,
                    'notify_group': True,
                    'enabled': True
                }
            else:
                self.data_manager.group_auth[group_id_str]['enabled'] = True
            
            await self.data_manager._save_json('group_auth', self.data_manager.group_auth)
            await self.api.send_group_msg(group_id, "本群已开机")
            return True
        
        # 本群关机
        elif command == "本群关机":
            if not self.permission_manager.has_group_permission(user_id, group_id):
                await self.api.send_group_msg(group_id, "权限不足")
                return True
            
            if group_id_str in self.data_manager.group_auth:
                self.data_manager.group_auth[group_id_str]['enabled'] = False
                await self.data_manager._save_json('group_auth', self.data_manager.group_auth)
            
            await self.api.send_group_msg(group_id, "本群已关机")
            return True
        
        # 增加授权天数
        elif raw_message.startswith("增加授权") and "天" in raw_message:
            if not self.permission_manager.is_owner_or_admin(user_id):
                await self.api.send_group_msg(group_id, "只有主人或管理员可以操作")
                return True
            
            days = utils.extract_number_from_text(raw_message)
            if not days:
                await self.api.send_group_msg(group_id, "请指定天数，格式：增加授权30")
                return True
            
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
            
            await self.data_manager._save_json('group_auth', self.data_manager.group_auth)
            await self.api.send_group_msg(group_id, f"已增加授权 {days} 天")
            return True
        
        # 减少授权天数
        elif raw_message.startswith("减少授权") and "天" in raw_message:
            if not self.permission_manager.is_owner_or_admin(user_id):
                await self.api.send_group_msg(group_id, "只有主人或管理员可以操作")
                return True
            
            days = utils.extract_number_from_text(raw_message)
            if not days:
                await self.api.send_group_msg(group_id, "请指定天数，格式：减少授权30")
                return True
            
            if group_id_str not in self.data_manager.group_auth:
                await self.api.send_group_msg(group_id, "本群尚未授权")
                return True
            
            current_expire = self.data_manager.group_auth[group_id_str].get('expire_date', 'unlimited')
            if current_expire == 'unlimited':
                new_expire = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            else:
                try:
                    expire_date = datetime.strptime(current_expire, '%Y-%m-%d')
                    new_expire = (expire_date - timedelta(days=days)).strftime('%Y-%m-%d')
                    
                    # 检查是否已经过期
                    if datetime.strptime(new_expire, '%Y-%m-%d') < datetime.now():
                        await self.api.send_group_msg(group_id, f"减少后授权已过期（{new_expire}），已自动关机")
                        self.data_manager.group_auth[group_id_str]['authorized'] = False
                        self.data_manager.group_auth[group_id_str]['enabled'] = False
                except:
                    new_expire = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            
            self.data_manager.group_auth[group_id_str]['expire_date'] = new_expire
            await self.data_manager._save_json('group_auth', self.data_manager.group_auth)
            await self.api.send_group_msg(group_id, f"已减少授权 {days} 天")
            return True
        
        # 开/关到期自动退群
        elif command in ["开到期自动退群", "关到期自动退群"]:
            if not self.permission_manager.is_owner_or_admin(user_id):
                await self.api.send_group_msg(group_id, "只有主人或管理员可以操作")
                return True
            
            enabled = command.startswith("开")
            if group_id_str not in self.data_manager.group_auth:
                self.data_manager.group_auth[group_id_str] = {'auto_leave': enabled}
            else:
                self.data_manager.group_auth[group_id_str]['auto_leave'] = enabled
            
            await self.data_manager._save_json('group_auth', self.data_manager.group_auth)
            await self.api.send_group_msg(group_id, f"已{'开启' if enabled else '关闭'}到期自动退群")
            return True
        
        # 开/关到期通知主人
        elif command in ["开到期通知主人", "关到期通知主人"]:
            if not self.permission_manager.is_owner_or_admin(user_id):
                await self.api.send_group_msg(group_id, "只有主人或管理员可以操作")
                return True
            
            enabled = command.startswith("开")
            if group_id_str not in self.data_manager.group_auth:
                self.data_manager.group_auth[group_id_str] = {'notify_owner': enabled}
            else:
                self.data_manager.group_auth[group_id_str]['notify_owner'] = enabled
            
            await self.data_manager._save_json('group_auth', self.data_manager.group_auth)
            await self.api.send_group_msg(group_id, f"已{'开启' if enabled else '关闭'}到期通知主人")
            return True
        
        # 开/关到期通知提醒
        elif command in ["开到期通知提醒", "关到期通知提醒"]:
            if not self.permission_manager.is_owner_or_admin(user_id):
                await self.api.send_group_msg(group_id, "只有主人或管理员可以操作")
                return True
            
            enabled = command.startswith("开")
            if group_id_str not in self.data_manager.group_auth:
                self.data_manager.group_auth[group_id_str] = {'notify_group': enabled}
            else:
                self.data_manager.group_auth[group_id_str]['notify_group'] = enabled
            
            await self.data_manager._save_json('group_auth', self.data_manager.group_auth)
            await self.api.send_group_msg(group_id, f"已{'开启' if enabled else '关闭'}到期通知提醒")
            return True
        
        return False
    
    def is_group_authorized(self, group_id: int) -> bool:
        """检查群是否已授权且未过期"""
        group_id_str = str(group_id)
        auth_info = self.data_manager.group_auth.get(group_id_str, {})
        
        if not auth_info.get('authorized', False):
            return False
        
        if not auth_info.get('enabled', True):
            return False
        
        expire = auth_info.get('expire_date', 'unlimited')
        if expire == 'unlimited':
            return True
        
        try:
            expire_date = datetime.strptime(expire, '%Y-%m-%d')
            return datetime.now() <= expire_date
        except:
            return True

