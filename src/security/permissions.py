"""Permission management system."""

from enum import Enum
from typing import Dict, List, Set, Optional
from dataclasses import dataclass, field

from ..core.logger import get_logger

logger = get_logger(__name__)


class Permission(str, Enum):
    """System permissions."""
    # Admin permissions
    ADMIN_ALL = "admin:all"
    ADMIN_USERS = "admin:users"
    ADMIN_PLUGINS = "admin:plugins"
    ADMIN_CONFIG = "admin:config"
    
    # Plugin permissions
    PLUGIN_LOAD = "plugin:load"
    PLUGIN_UNLOAD = "plugin:unload"
    PLUGIN_RELOAD = "plugin:reload"
    PLUGIN_ENABLE = "plugin:enable"
    PLUGIN_DISABLE = "plugin:disable"
    PLUGIN_CONFIGURE = "plugin:configure"
    PLUGIN_VIEW = "plugin:view"
    
    # Message permissions
    MESSAGE_SEND = "message:send"
    MESSAGE_DELETE = "message:delete"
    MESSAGE_VIEW = "message:view"
    
    # System permissions
    SYSTEM_CONFIG_VIEW = "system:config:view"
    SYSTEM_CONFIG_EDIT = "system:config:edit"
    SYSTEM_LOGS_VIEW = "system:logs:view"
    SYSTEM_METRICS_VIEW = "system:metrics:view"
    
    # Audit permissions
    AUDIT_VIEW = "audit:view"
    AUDIT_EXPORT = "audit:export"


@dataclass
class Role:
    """Role definition with permissions."""
    
    name: str
    permissions: Set[Permission] = field(default_factory=set)
    description: str = ""


class PermissionManager:
    """Manage roles and permissions."""

    def __init__(self):
        self._roles: Dict[str, Role] = {}
        self._user_roles: Dict[str, Set[str]] = {}
        
        # Initialize default roles
        self._init_default_roles()

    def _init_default_roles(self) -> None:
        """Initialize default roles."""
        # Admin role with all permissions
        self.create_role(
            "admin",
            list(Permission),
            "Administrator with full access"
        )
        
        # Plugin manager role
        self.create_role(
            "plugin_manager",
            [
                Permission.PLUGIN_LOAD,
                Permission.PLUGIN_UNLOAD,
                Permission.PLUGIN_RELOAD,
                Permission.PLUGIN_ENABLE,
                Permission.PLUGIN_DISABLE,
                Permission.PLUGIN_CONFIGURE,
                Permission.PLUGIN_VIEW,
                Permission.SYSTEM_LOGS_VIEW,
                Permission.SYSTEM_METRICS_VIEW,
            ],
            "Plugin manager with plugin management permissions"
        )
        
        # User role with limited permissions
        self.create_role(
            "user",
            [
                Permission.PLUGIN_VIEW,
                Permission.MESSAGE_VIEW,
                Permission.SYSTEM_METRICS_VIEW,
            ],
            "Regular user with read-only access"
        )
        
        # Readonly role
        self.create_role(
            "readonly",
            [
                Permission.PLUGIN_VIEW,
                Permission.SYSTEM_METRICS_VIEW,
            ],
            "Read-only access to system information"
        )

    def create_role(
        self,
        name: str,
        permissions: List[Permission],
        description: str = ""
    ) -> bool:
        """Create a new role."""
        if name in self._roles:
            logger.warning("Role already exists", role=name)
            return False
        
        self._roles[name] = Role(
            name=name,
            permissions=set(permissions),
            description=description
        )
        
        logger.info("Role created", role=name, permissions=len(permissions))
        return True

    def delete_role(self, name: str) -> bool:
        """Delete a role."""
        if name in ["admin", "user"]:
            logger.warning("Cannot delete default role", role=name)
            return False
        
        if name in self._roles:
            del self._roles[name]
            logger.info("Role deleted", role=name)
            return True
        
        return False

    def add_permission_to_role(self, role_name: str, permission: Permission) -> bool:
        """Add a permission to a role."""
        role = self._roles.get(role_name)
        if not role:
            return False
        
        role.permissions.add(permission)
        logger.debug("Permission added to role", role=role_name, permission=permission.value)
        return True

    def remove_permission_from_role(self, role_name: str, permission: Permission) -> bool:
        """Remove a permission from a role."""
        role = self._roles.get(role_name)
        if not role:
            return False
        
        role.permissions.discard(permission)
        logger.debug("Permission removed from role", role=role_name, permission=permission.value)
        return True

    def assign_role_to_user(self, username: str, role_name: str) -> bool:
        """Assign a role to a user."""
        if role_name not in self._roles:
            logger.warning("Role not found", role=role_name)
            return False
        
        if username not in self._user_roles:
            self._user_roles[username] = set()
        
        # Only add if not already assigned
        if role_name not in self._user_roles[username]:
            self._user_roles[username].add(role_name)
            logger.info("Role assigned to user", username=username, role=role_name)
        
        return True

    def remove_role_from_user(self, username: str, role_name: str) -> bool:
        """Remove a role from a user."""
        if username in self._user_roles:
            self._user_roles[username].discard(role_name)
            logger.info("Role removed from user", username=username, role=role_name)
            return True
        return False

    def get_user_permissions(self, username: str) -> Set[Permission]:
        """Get all permissions for a user."""
        permissions: Set[Permission] = set()
        
        roles = self._user_roles.get(username, set())
        for role_name in roles:
            role = self._roles.get(role_name)
            if role:
                permissions.update(role.permissions)
        
        return permissions

    def has_permission(self, username: str, permission: Permission) -> bool:
        """Check if a user has a specific permission."""
        user_permissions = self.get_user_permissions(username)
        
        # Admin has all permissions
        if Permission.ADMIN_ALL in user_permissions:
            return True
        
        return permission in user_permissions

    def has_any_permission(self, username: str, permissions: List[Permission]) -> bool:
        """Check if a user has any of the specified permissions."""
        user_permissions = self.get_user_permissions(username)
        
        if Permission.ADMIN_ALL in user_permissions:
            return True
        
        return any(perm in user_permissions for perm in permissions)

    def has_all_permissions(self, username: str, permissions: List[Permission]) -> bool:
        """Check if a user has all of the specified permissions."""
        user_permissions = self.get_user_permissions(username)
        
        if Permission.ADMIN_ALL in user_permissions:
            return True
        
        return all(perm in user_permissions for perm in permissions)

    def get_role(self, role_name: str) -> Role:
        """Get a role by name."""
        return self._roles.get(role_name)

    def get_all_roles(self) -> List[Role]:
        """Get all roles."""
        return list(self._roles.values())

    def get_user_roles(self, username: str) -> Set[str]:
        """Get roles assigned to a user."""
        return self._user_roles.get(username, set()).copy()


# Global permission manager
_permission_manager: Optional[PermissionManager] = None


def get_permission_manager() -> PermissionManager:
    """Get the global permission manager."""
    global _permission_manager
    if _permission_manager is None:
        _permission_manager = PermissionManager()
        # Initialize admin user with admin role
        _permission_manager.assign_role_to_user("admin", "admin")
    return _permission_manager


def has_permission(username: str, permission: Permission) -> bool:
    """Check if a user has a permission."""
    return get_permission_manager().has_permission(username, permission)

