"""Access control for users and groups."""

from typing import Set, List
from ..core.logger import get_logger
from ..core.storage import get_storage

logger = get_logger(__name__)


class AccessControl:
    """Access control manager."""
    
    def __init__(self):
        self.storage = get_storage()
        self._owners: Set[str] = set()
        self._blacklist: Set[str] = set()
        self._whitelist: Set[str] = set()
        self._silent_list: Set[str] = set()
        
        self._load_lists()
    
    def _load_lists(self):
        """Load access control lists from storage."""
        try:
            self._owners = set(self.storage.get("access_control:owners") or [])
            self._blacklist = set(self.storage.get("access_control:blacklist") or [])
            self._whitelist = set(self.storage.get("access_control:whitelist") or [])
            self._silent_list = set(self.storage.get("access_control:silent") or [])
        except Exception as e:
            logger.warning(f"Failed to load access control lists: {e}")
    
    def _save_lists(self):
        """Save access control lists to storage."""
        try:
            self.storage.set("access_control:owners", list(self._owners))
            self.storage.set("access_control:blacklist", list(self._blacklist))
            self.storage.set("access_control:whitelist", list(self._whitelist))
            self.storage.set("access_control:silent", list(self._silent_list))
        except Exception as e:
            logger.error(f"Failed to save access control lists: {e}")
    
    # Owner management
    def is_owner(self, user_id: str) -> bool:
        """Check if user is owner."""
        return user_id in self._owners
    
    def add_owner(self, user_id: str):
        """Add user to owner list."""
        self._owners.add(user_id)
        self._save_lists()
        logger.info(f"Added owner: {user_id}")
    
    def remove_owner(self, user_id: str):
        """Remove user from owner list."""
        self._owners.discard(user_id)
        self._save_lists()
        logger.info(f"Removed owner: {user_id}")
    
    def get_owners(self) -> List[str]:
        """Get all owners."""
        return list(self._owners)
    
    # Blacklist management
    def is_blocked(self, user_id: str) -> bool:
        """Check if user/group is blocked."""
        return user_id in self._blacklist
    
    def add_to_blacklist(self, user_id: str):
        """Add user/group to blacklist."""
        self._blacklist.add(user_id)
        self._save_lists()
        logger.info(f"Added to blacklist: {user_id}")
    
    def remove_from_blacklist(self, user_id: str):
        """Remove user/group from blacklist."""
        self._blacklist.discard(user_id)
        self._save_lists()
        logger.info(f"Removed from blacklist: {user_id}")
    
    def get_blacklist(self) -> List[str]:
        """Get blacklist."""
        return list(self._blacklist)
    
    # Whitelist management
    def is_whitelisted(self, user_id: str) -> bool:
        """Check if user/group is whitelisted."""
        return user_id in self._whitelist
    
    def add_to_whitelist(self, user_id: str):
        """Add user/group to whitelist."""
        self._whitelist.add(user_id)
        self._save_lists()
        logger.info(f"Added to whitelist: {user_id}")
    
    def remove_from_whitelist(self, user_id: str):
        """Remove user/group from whitelist."""
        self._whitelist.discard(user_id)
        self._save_lists()
        logger.info(f"Removed from whitelist: {user_id}")
    
    def get_whitelist(self) -> List[str]:
        """Get whitelist."""
        return list(self._whitelist)
    
    # Silent mode management
    def is_silent(self, user_id: str) -> bool:
        """Check if user/group is in silent mode."""
        return user_id in self._silent_list
    
    def add_to_silent(self, user_id: str):
        """Add user/group to silent list."""
        self._silent_list.add(user_id)
        self._save_lists()
        logger.info(f"Added to silent list: {user_id}")
    
    def remove_from_silent(self, user_id: str):
        """Remove user/group from silent list."""
        self._silent_list.discard(user_id)
        self._save_lists()
        logger.info(f"Removed from silent list: {user_id}")
    
    def get_silent_list(self) -> List[str]:
        """Get silent list."""
        return list(self._silent_list)
    
    # Permission check
    def can_process(self, user_id: str, group_id: str = None) -> bool:
        """Check if message should be processed."""
        # Check blacklist
        if self.is_blocked(user_id):
            return False
        if group_id and self.is_blocked(group_id):
            return False
        
        # Check whitelist (if whitelist is enabled)
        if self._whitelist:
            if not (self.is_whitelisted(user_id) or 
                   (group_id and self.is_whitelisted(group_id))):
                return False
        
        return True
    
    def should_reply(self, user_id: str, group_id: str = None) -> bool:
        """Check if bot should reply."""
        # Silent mode check
        if self.is_silent(user_id):
            return False
        if group_id and self.is_silent(group_id):
            return False
        
        return True


# Global instance
_access_control = None


def get_access_control() -> AccessControl:
    """Get global access control instance."""
    global _access_control
    if _access_control is None:
        _access_control = AccessControl()
    return _access_control

