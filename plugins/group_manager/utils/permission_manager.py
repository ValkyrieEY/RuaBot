"""权限管理器 - 处理用户权限验证"""

from typing import Dict, Optional, List


class PermissionManager:
    """权限管理器"""
    
    # 权限等级
    OWNER = 0  # 主人（最高权限，全局）
    ADMIN = 1  # 管理员（全局管理）
    GROUP_OWNER = 2  # 群主（单群最高权限）
    GROUP_MANAGER = 3  # 群管（单群管理）
    USER = 4  # 普通用户
    
    def __init__(self, api, data_manager):
        """初始化权限管理器
        
        Args:
            api: PluginAPI 实例
            data_manager: DataManager 实例
        """
        self.api = api
        self.data_manager = data_manager
        
        # 主人和管理员列表（需要通过插件配置设置）
        self.owners: List[int] = []
        self.admins: List[int] = []
    
    def set_owners(self, owners: List[int]):
        """设置主人列表"""
        self.owners = owners
    
    def set_admins(self, admins: List[int]):
        """设置管理员列表"""
        self.admins = admins
    
    def get_permission_level(self, user_id: int, group_id: Optional[int] = None) -> int:
        """获取用户权限等级
        
        Args:
            user_id: 用户QQ号
            group_id: 群号（可选，如果提供则检查群内权限）
        
        Returns:
            权限等级
        """
        # 检查主人权限
        if user_id in self.owners:
            return self.OWNER
        
        # 检查管理员权限
        if user_id in self.admins:
            return self.ADMIN
        
        # 如果提供了群号，检查群内权限
        if group_id:
            group_id_str = str(group_id)
            perms = self.data_manager.permissions.get(group_id_str, {})
            
            # 检查群主权限
            if user_id in perms.get('owners', []):
                return self.GROUP_OWNER
            
            # 检查群管权限
            if user_id in perms.get('managers', []):
                return self.GROUP_MANAGER
        
        return self.USER
    
    def has_permission(self, user_id: int, required_level: int, group_id: Optional[int] = None) -> bool:
        """检查用户是否有足够权限
        
        Args:
            user_id: 用户QQ号
            required_level: 要求的权限等级
            group_id: 群号（可选）
        
        Returns:
            是否有权限
        """
        user_level = self.get_permission_level(user_id, group_id)
        return user_level <= required_level
    
    def is_owner(self, user_id: int) -> bool:
        """检查是否是主人"""
        return user_id in self.owners
    
    def is_admin(self, user_id: int) -> bool:
        """检查是否是管理员"""
        return user_id in self.admins
    
    def is_owner_or_admin(self, user_id: int) -> bool:
        """检查是否是主人或管理员"""
        return self.is_owner(user_id) or self.is_admin(user_id)
    
    def is_group_owner(self, user_id: int, group_id: int) -> bool:
        """检查是否是群主（插件定义的）"""
        group_id_str = str(group_id)
        perms = self.data_manager.permissions.get(group_id_str, {})
        return user_id in perms.get('owners', [])
    
    def is_group_manager(self, user_id: int, group_id: int) -> bool:
        """检查是否是群管"""
        group_id_str = str(group_id)
        perms = self.data_manager.permissions.get(group_id_str, {})
        return user_id in perms.get('managers', [])
    
    def has_group_permission(self, user_id: int, group_id: int) -> bool:
        """检查是否有群管理权限（群主或群管或更高）"""
        return self.has_permission(user_id, self.GROUP_MANAGER, group_id)
    
    def add_group_owner(self, user_id: int, group_id: int):
        """添加群主"""
        group_id_str = str(group_id)
        if group_id_str not in self.data_manager.permissions:
            self.data_manager.permissions[group_id_str] = {'owners': [], 'managers': []}
        
        if user_id not in self.data_manager.permissions[group_id_str].get('owners', []):
            if 'owners' not in self.data_manager.permissions[group_id_str]:
                self.data_manager.permissions[group_id_str]['owners'] = []
            self.data_manager.permissions[group_id_str]['owners'].append(user_id)
    
    def remove_group_owner(self, user_id: int, group_id: int):
        """删除群主"""
        group_id_str = str(group_id)
        if group_id_str in self.data_manager.permissions:
            owners = self.data_manager.permissions[group_id_str].get('owners', [])
            if user_id in owners:
                owners.remove(user_id)
    
    def add_group_manager(self, user_id: int, group_id: int):
        """添加群管"""
        group_id_str = str(group_id)
        if group_id_str not in self.data_manager.permissions:
            self.data_manager.permissions[group_id_str] = {'owners': [], 'managers': []}
        
        if user_id not in self.data_manager.permissions[group_id_str].get('managers', []):
            if 'managers' not in self.data_manager.permissions[group_id_str]:
                self.data_manager.permissions[group_id_str]['managers'] = []
            self.data_manager.permissions[group_id_str]['managers'].append(user_id)
    
    def remove_group_manager(self, user_id: int, group_id: int):
        """删除群管"""
        group_id_str = str(group_id)
        if group_id_str in self.data_manager.permissions:
            managers = self.data_manager.permissions[group_id_str].get('managers', [])
            if user_id in managers:
                managers.remove(user_id)
    
    def get_permission_name(self, level: int) -> str:
        """获取权限等级名称"""
        names = {
            self.OWNER: "主人",
            self.ADMIN: "管理员",
            self.GROUP_OWNER: "群主",
            self.GROUP_MANAGER: "群管",
            self.USER: "普通用户"
        }
        return names.get(level, "未知")
    
    async def sync_group_admins(self, group_id: int):
        """同步群内管理权限
        
        从QQ群获取实际的群主和管理员，自动添加到权限列表
        
        Args:
            group_id: 群号
        """
        try:
            # 获取群成员列表 - 根据main.py中的PluginAPI，使用关键字参数
            result = await self.api.call_api('get_group_member_list', group_id=group_id)
            # main.py中的call_api直接返回结果，不是包装的字典
            if not result or not isinstance(result, list):
                self.api.log("error", f"获取群成员列表失败: {result}")
                return False
            
            members = result
            group_id_str = str(group_id)
            
            # 初始化权限字典
            if group_id_str not in self.data_manager.permissions:
                self.data_manager.permissions[group_id_str] = {'owners': [], 'managers': []}
            
            # 扫描群成员
            for member in members:
                user_id = member.get('user_id')
                role = member.get('role', 'member')
                
                # 群主
                if role == 'owner':
                    if user_id not in self.data_manager.permissions[group_id_str]['owners']:
                        self.data_manager.permissions[group_id_str]['owners'].append(user_id)
                
                # 管理员
                elif role == 'admin':
                    if user_id not in self.data_manager.permissions[group_id_str]['managers']:
                        self.data_manager.permissions[group_id_str]['managers'].append(user_id)
            
            # 保存数据
            await self.data_manager._save_json('permissions', self.data_manager.permissions)
            
            self.api.log("info", f"已同步群 {group_id} 的管理权限")
            return True
            
        except Exception as e:
            self.api.log("error", f"同步管理权限失败: {e}")
            return False

