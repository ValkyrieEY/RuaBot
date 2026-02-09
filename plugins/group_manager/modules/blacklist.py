"""黑白名单模块"""

from typing import Dict
import sys
from pathlib import Path

# 添加父目录到路径
parent_dir = Path(__file__).parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from utils import utils


class BlackWhiteListModule:
    """黑白名单模块"""
    
    def __init__(self, api, data_manager, permission_manager):
        self.api = api
        self.data_manager = data_manager
        self.permission_manager = permission_manager
    
    async def handle_command(self, event: Dict, command: str) -> bool:
        """处理黑白名单指令"""
        user_id = event.get('user_id')
        group_id = event.get('group_id')
        raw_message = event.get('raw_message', '').strip()
        message = event.get('message', [])
        
        group_id_str = str(group_id) if group_id else None
        
        # 加黑@QQ/加黑+QQ#原因
        if raw_message.startswith("加黑"):
            if not self.permission_manager.has_group_permission(user_id, group_id):
                return False
            
            # 分离QQ和原因
            parts = raw_message.split('#')
            qq_part = parts[0]
            reason = parts[1] if len(parts) > 1 else "无"
            
            target_qq = utils.extract_number_from_text(qq_part)
            if not target_qq:
                at_list = utils.parse_at(message)
                if at_list:
                    target_qq = at_list[0]
            
            if not target_qq:
                await self.api.send_group_msg(group_id, " 请指定QQ号")
                return True
            
            if group_id_str not in self.data_manager.blacklist['groups']:
                self.data_manager.blacklist['groups'][group_id_str] = []
            
            self.data_manager.blacklist['groups'][group_id_str].append({
                'qq': target_qq,
                'reason': reason
            })
            
            await self.data_manager._save_json('blacklist', self.data_manager.blacklist)
            await self.api.send_group_msg(group_id, f"已将 {target_qq} 加入本群黑名单")
            return True
        
        # 全局加黑
        elif raw_message.startswith("全局加黑"):
            if not self.permission_manager.is_owner_or_admin(user_id):
                await self.api.send_group_msg(group_id, " 只有主人或管理员可以操作全局黑名单")
                return True
            
            parts = raw_message.split('#')
            qq_part = parts[0]
            reason = parts[1] if len(parts) > 1 else "无"
            
            target_qq = utils.extract_number_from_text(qq_part)
            if not target_qq:
                at_list = utils.parse_at(message)
                if at_list:
                    target_qq = at_list[0]
            
            if not target_qq:
                await self.api.send_group_msg(group_id, " 请指定QQ号")
                return True
            
            self.data_manager.blacklist['global'].append({
                'qq': target_qq,
                'reason': reason
            })
            
            await self.data_manager._save_json('blacklist', self.data_manager.blacklist)
            await self.api.send_group_msg(group_id, f" 已将 {target_qq} 加入全局黑名单")
            return True
        
        # 删黑（本群）
        elif raw_message.startswith("删黑") and not raw_message.startswith("全局删黑"):
            if not self.permission_manager.has_group_permission(user_id, group_id):
                return False
            
            target_qq = utils.extract_number_from_text(raw_message)
            if not target_qq:
                at_list = utils.parse_at(message)
                if at_list:
                    target_qq = at_list[0]
            
            if not target_qq:
                await self.api.send_group_msg(group_id, " 请指定QQ号")
                return True
            
            if group_id_str in self.data_manager.blacklist['groups']:
                self.data_manager.blacklist['groups'][group_id_str] = [
                    item for item in self.data_manager.blacklist['groups'][group_id_str]
                    if item['qq'] != target_qq
                ]
                await self.data_manager._save_json('blacklist', self.data_manager.blacklist)
                await self.api.send_group_msg(group_id, f"已将 {target_qq} 从本群黑名单移除")
            return True
        
        # 加白/删白/全局加白/全局删白 类似实现...
        elif raw_message.startswith(("加白", "删白", "全局加白", "全局删白")):
            is_global = raw_message.startswith("全局")
            is_add = "加白" in raw_message
            
            if is_global and not self.permission_manager.is_owner_or_admin(user_id):
                await self.api.send_group_msg(group_id, " 只有主人或管理员可以操作全局白名单")
                return True
            
            if not is_global and not self.permission_manager.has_group_permission(user_id, group_id):
                return False
            
            target_qq = utils.extract_number_from_text(raw_message)
            if not target_qq:
                at_list = utils.parse_at(message)
                if at_list:
                    target_qq = at_list[0]
            
            if not target_qq:
                await self.api.send_group_msg(group_id, " 请指定QQ号")
                return True
            
            if is_global:
                if is_add:
                    if target_qq not in self.data_manager.whitelist['global']:
                        self.data_manager.whitelist['global'].append(target_qq)
                else:
                    if target_qq in self.data_manager.whitelist['global']:
                        self.data_manager.whitelist['global'].remove(target_qq)
            else:
                if group_id_str not in self.data_manager.whitelist['groups']:
                    self.data_manager.whitelist['groups'][group_id_str] = []
                
                if is_add:
                    if target_qq not in self.data_manager.whitelist['groups'][group_id_str]:
                        self.data_manager.whitelist['groups'][group_id_str].append(target_qq)
                else:
                    if target_qq in self.data_manager.whitelist['groups'][group_id_str]:
                        self.data_manager.whitelist['groups'][group_id_str].remove(target_qq)
            
            await self.data_manager._save_json('whitelist', self.data_manager.whitelist)
            action = "加入" if is_add else "移除"
            scope = "全局" if is_global else "本群"
            await self.api.send_group_msg(group_id, f"已{action} {target_qq} {scope}白名单")
            return True
        
        # 查询黑名单列表
        elif command == "查询黑名单列表":
            if group_id_str not in self.data_manager.blacklist['groups']:
                await self.api.send_group_msg(group_id, "本群黑名单为空")
                return True
            
            blacklist = self.data_manager.blacklist['groups'][group_id_str]
            if not blacklist:
                await self.api.send_group_msg(group_id, "本群黑名单为空")
                return True
            
            msg = f"本群黑名单（{len(blacklist)}人）\n"
            for item in blacklist[:10]:
                msg += f"  - {item['qq']} (原因: {item.get('reason', '无')})\n"
            if len(blacklist) > 10:
                msg += f"  ... 还有{len(blacklist)-10}人\n"
            
            await self.api.send_group_msg(group_id, msg)
            return True
        
        # 清空黑名单列表
        elif command == "清空黑名单列表":
            if not self.permission_manager.has_group_permission(user_id, group_id):
                return False
            
            if group_id_str in self.data_manager.blacklist['groups']:
                self.data_manager.blacklist['groups'][group_id_str] = []
                await self.data_manager._save_json('blacklist', self.data_manager.blacklist)
            
            await self.api.send_group_msg(group_id, "已清空本群黑名单")
            return True
        
        # 设置黑名单提示/禁言/踢出（本群）
        elif raw_message.startswith("设置黑名单"):
            if not self.permission_manager.has_group_permission(user_id, group_id):
                return False
            
            if "提示" in raw_message:
                action = "提示"
            elif "禁言" in raw_message:
                action = "禁言"
            elif "踢出" in raw_message:
                action = "踢出"
            else:
                await self.api.send_group_msg(group_id, "请指定处理方式：提示/禁言/踢出")
                return True
            
            if 'groups' not in self.data_manager.blacklist_actions:
                self.data_manager.blacklist_actions['groups'] = {}
            
            self.data_manager.blacklist_actions['groups'][group_id_str] = action
            await self.data_manager._save_json('blacklist_actions', self.data_manager.blacklist_actions)
            await self.api.send_group_msg(group_id, f"已设置本群黑名单处理方式：{action}")
            return True
        
        # 设置全局黑名单提示/禁言/踢出
        elif raw_message.startswith("设置全局黑名单"):
            if not self.permission_manager.is_owner_or_admin(user_id):
                await self.api.send_group_msg(group_id, "只有主人或管理员可以操作")
                return True
            
            if "提示" in raw_message:
                action = "提示"
            elif "禁言" in raw_message:
                action = "禁言"
            elif "踢出" in raw_message:
                action = "踢出"
            else:
                await self.api.send_group_msg(group_id, "请指定处理方式：提示/禁言/踢出")
                return True
            
            self.data_manager.blacklist_actions['global'] = action
            await self.data_manager._save_json('blacklist_actions', self.data_manager.blacklist_actions)
            await self.api.send_group_msg(group_id, f"已设置全局黑名单处理方式：{action}")
            return True
        
        return False
    
    async def handle_blacklist_user(self, user_id: int, group_id: int, event: Dict):
        """处理黑名单用户（根据设置执行提示/禁言/踢出）"""
        try:
            group_id_str = str(group_id)
            
            # 获取处理方式（优先使用群设置，否则使用全局设置）
            action = '提示'  # 默认提示
            if 'groups' in self.data_manager.blacklist_actions:
                if group_id_str in self.data_manager.blacklist_actions['groups']:
                    action = self.data_manager.blacklist_actions['groups'][group_id_str]
                elif 'global' in self.data_manager.blacklist_actions:
                    action = self.data_manager.blacklist_actions['global']
            
            # 查找黑名单原因
            reason = "无"
            # 检查全局黑名单
            for item in self.data_manager.blacklist['global']:
                if isinstance(item, dict) and item['qq'] == user_id:
                    reason = item.get('reason', '无')
                    break
                elif item == user_id:
                    break
            
            # 检查群黑名单
            if group_id_str in self.data_manager.blacklist['groups']:
                for item in self.data_manager.blacklist['groups'][group_id_str]:
                    if isinstance(item, dict) and item['qq'] == user_id:
                        reason = item.get('reason', '无')
                        break
            
            # 执行处理
            if action == "提示":
                await self.api.send_group_msg(group_id, f"[CQ:at,qq={user_id}] 检测到黑名单用户（原因：{reason}）")
            
            elif action == "禁言":
                # 先提示
                await self.api.send_group_msg(group_id, f"[CQ:at,qq={user_id}] 检测到黑名单用户（原因：{reason}），已禁言")
                # 执行禁言（10分钟）
                try:
                    await self.api.call_api('set_group_ban', group_id=group_id, user_id=user_id, duration=600)
                except Exception as e:
                    self.api.log("error", f"禁言黑名单用户失败: {e}")
            
            elif action == "踢出":
                # 先提示
                await self.api.send_group_msg(group_id, f"[CQ:at,qq={user_id}] 检测到黑名单用户（原因：{reason}），已踢出")
                # 执行踢出
                try:
                    await self.api.call_api('set_group_kick', group_id=group_id, user_id=user_id, reject_add_request=False)
                except Exception as e:
                    self.api.log("error", f"踢出黑名单用户失败: {e}")
        
        except Exception as e:
            self.api.log("error", f"处理黑名单用户失败: {e}")
    
    def is_in_blacklist(self, user_id: int, group_id: int) -> bool:
        """检查用户是否在黑名单中"""
        # 检查全局黑名单
        for item in self.data_manager.blacklist['global']:
            if isinstance(item, dict):
                if item['qq'] == user_id:
                    return True
            elif item == user_id:
                return True
        
        # 检查群黑名单
        group_id_str = str(group_id)
        if group_id_str in self.data_manager.blacklist['groups']:
            for item in self.data_manager.blacklist['groups'][group_id_str]:
                if isinstance(item, dict):
                    if item['qq'] == user_id:
                        return True
                elif item == user_id:
                    return True
        
        return False
    
    def is_in_whitelist(self, user_id: int, group_id: int) -> bool:
        """检查用户是否在白名单中"""
        # 检查全局白名单
        if user_id in self.data_manager.whitelist['global']:
            return True
        
        # 检查群白名单
        group_id_str = str(group_id)
        if group_id_str in self.data_manager.whitelist['groups']:
            if user_id in self.data_manager.whitelist['groups'][group_id_str]:
                return True
        
        return False

