"""权限管理模块"""

from typing import Dict
import sys
from pathlib import Path

# 添加父目录到路径
parent_dir = Path(__file__).parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from utils import utils


class PermissionModule:
    """权限管理模块"""
    
    def __init__(self, api, data_manager, permission_manager):
        self.api = api
        self.data_manager = data_manager
        self.permission_manager = permission_manager
    
    async def handle_command(self, event: Dict, command: str) -> bool:
        """处理权限相关指令"""
        user_id = event.get('user_id')
        group_id = event.get('group_id')
        raw_message = event.get('raw_message', '').strip()
        message = event.get('message', [])
        
        # 我的身份
        if command == "我的身份":
            level = self.permission_manager.get_permission_level(user_id, group_id)
            level_name = self.permission_manager.get_permission_name(level)
            await self.api.send_group_msg(group_id, f"你的身份：{level_name}")
            return True
        
        # 查询身份+QQ
        elif raw_message.startswith("查询身份"):
            target_qq = utils.extract_number_from_text(raw_message)
            if not target_qq:
                at_list = utils.parse_at(message)
                if at_list:
                    target_qq = at_list[0]
            
            if not target_qq:
                await self.api.send_group_msg(group_id, "请指定QQ号，格式：查询身份123456 或 @某人")
                return True
            
            level = self.permission_manager.get_permission_level(target_qq, group_id)
            level_name = self.permission_manager.get_permission_name(level)
            await self.api.send_group_msg(group_id, f"[CQ:at,qq={target_qq}] 的身份：{level_name}")
            return True
        
        # 同步管理权限
        elif command == "同步管理权限":
            self.api.log("debug", f"收到同步管理权限指令，用户: {user_id}, 群: {group_id}")
            
            # 主人、管理员、群主、群管都可以执行
            is_owner_or_admin = self.permission_manager.is_owner_or_admin(user_id)
            has_group_perm = self.permission_manager.has_group_permission(user_id, group_id)
            
            self.api.log("debug", f"权限检查 - 主人/管理员: {is_owner_or_admin}, 群权限: {has_group_perm}")
            
            if not (is_owner_or_admin or has_group_perm):
                await self.api.send_group_msg(group_id, "权限不足")
                return True
            
            await self.api.send_group_msg(group_id, "正在同步管理权限...")
            try:
                success = await self.permission_manager.sync_group_admins(group_id)
                if success:
                    await self.api.send_group_msg(group_id, "已同步管理权限")
                else:
                    await self.api.send_group_msg(group_id, "同步失败，请检查日志")
            except Exception as e:
                self.api.log("error", f"同步管理权限异常: {e}", exc_info=True)
                await self.api.send_group_msg(group_id, f"同步失败：{str(e)}")
            return True
        
        # 查询群管列表
        elif command == "查询群管列表":
            group_id_str = str(group_id)
            perms = self.data_manager.permissions.get(group_id_str, {})
            
            owners = perms.get('owners', [])
            managers = perms.get('managers', [])
            
            msg = "群管列表\n"
            msg += f"群主：{len(owners)}人\n"
            for qq in owners:  # 显示所有
                msg += f"  - {qq}\n"
            
            msg += f"群管：{len(managers)}人\n"
            for qq in managers:  # 显示所有
                msg += f"  - {qq}\n"
            
            await self.api.send_group_msg(group_id, msg)
            return True
        
        # 清空群管列表
        elif command == "清空群管列表":
            if not self.permission_manager.is_owner_or_admin(user_id):
                await self.api.send_group_msg(group_id, "只有主人或管理员可以操作")
                return True
            
            group_id_str = str(group_id)
            if group_id_str in self.data_manager.permissions:
                self.data_manager.permissions[group_id_str] = {'owners': [], 'managers': []}
                await self.data_manager._save_json('permissions', self.data_manager.permissions)
            
            await self.api.send_group_msg(group_id, "已清空群管列表")
            return True
        
        # 加/删群主+QQ
        elif raw_message.startswith(("加群主", "删群主")):
            if not self.permission_manager.is_owner_or_admin(user_id):
                await self.api.send_group_msg(group_id, "只有主人或管理员可以操作")
                return True
            
            is_add = raw_message.startswith("加")
            target_qq = utils.extract_number_from_text(raw_message)
            if not target_qq:
                at_list = utils.parse_at(message)
                if at_list:
                    target_qq = at_list[0]
            
            if not target_qq:
                await self.api.send_group_msg(group_id, "请指定QQ号")
                return True
            
            if is_add:
                self.permission_manager.add_group_owner(target_qq, group_id)
                await self.data_manager._save_json('permissions', self.data_manager.permissions)
                await self.api.send_group_msg(group_id, f"已添加 {target_qq} 为群主")
            else:
                self.permission_manager.remove_group_owner(target_qq, group_id)
                await self.data_manager._save_json('permissions', self.data_manager.permissions)
                await self.api.send_group_msg(group_id, f"已删除群主 {target_qq}")
            return True
        
        # 加/删群管+QQ
        elif raw_message.startswith(("加群管", "删群管")):
            if not self.permission_manager.has_group_permission(user_id, group_id):
                await self.api.send_group_msg(group_id, "权限不足")
                return True
            
            is_add = raw_message.startswith("加")
            target_qq = utils.extract_number_from_text(raw_message)
            if not target_qq:
                at_list = utils.parse_at(message)
                if at_list:
                    target_qq = at_list[0]
            
            if not target_qq:
                await self.api.send_group_msg(group_id, "请指定QQ号")
                return True
            
            if is_add:
                self.permission_manager.add_group_manager(target_qq, group_id)
                await self.data_manager._save_json('permissions', self.data_manager.permissions)
                await self.api.send_group_msg(group_id, f"已添加 {target_qq} 为群管")
            else:
                self.permission_manager.remove_group_manager(target_qq, group_id)
                await self.data_manager._save_json('permissions', self.data_manager.permissions)
                await self.api.send_group_msg(group_id, f"已删除群管 {target_qq}")
            return True
        
        # 加/删管理员+QQ
        elif raw_message.startswith(("加管理员", "删管理员")):
            if not self.permission_manager.is_owner(user_id):
                await self.api.send_group_msg(group_id, "只有主人可以操作")
                return True
            
            is_add = raw_message.startswith("加")
            target_qq = utils.extract_number_from_text(raw_message)
            if not target_qq:
                at_list = utils.parse_at(message)
                if at_list:
                    target_qq = at_list[0]
            
            if not target_qq:
                await self.api.send_group_msg(group_id, "请指定QQ号")
                return True
            
            if is_add:
                if target_qq not in self.permission_manager.admins:
                    self.permission_manager.admins.append(target_qq)
                    # 需要更新配置，转换为字符串数组
                    admin_list_str = [str(qq) for qq in self.permission_manager.admins]
                    await self.api.set_config('admin_qq_list', admin_list_str)
                    await self.api.send_group_msg(group_id, f"已添加 {target_qq} 为管理员")
            else:
                if target_qq in self.permission_manager.admins:
                    self.permission_manager.admins.remove(target_qq)
                    # 需要更新配置，转换为字符串数组
                    admin_list_str = [str(qq) for qq in self.permission_manager.admins]
                    await self.api.set_config('admin_qq_list', admin_list_str)
                    await self.api.send_group_msg(group_id, f"已删除管理员 {target_qq}")
            return True
        
        return False

