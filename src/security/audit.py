"""Audit logging for security and compliance."""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum

from ..core.logger import get_logger
from ..core.storage import get_storage

logger = get_logger(__name__)


class AuditEventType(str, Enum):
    """Types of audit events."""
    # Authentication
    AUTH_LOGIN = "auth.login"
    AUTH_LOGOUT = "auth.logout"
    AUTH_FAILED = "auth.failed"
    
    # User management
    USER_CREATED = "user.created"
    USER_DELETED = "user.deleted"
    USER_UPDATED = "user.updated"
    
    # Plugin management
    PLUGIN_LOADED = "plugin.loaded"
    PLUGIN_UNLOADED = "plugin.unloaded"
    PLUGIN_ENABLED = "plugin.enabled"
    PLUGIN_DISABLED = "plugin.disabled"
    PLUGIN_CONFIGURED = "plugin.configured"
    
    # Permission changes
    PERMISSION_GRANTED = "permission.granted"
    PERMISSION_REVOKED = "permission.revoked"
    ROLE_ASSIGNED = "role.assigned"
    ROLE_REMOVED = "role.removed"
    
    # Configuration
    CONFIG_CHANGED = "config.changed"
    CONFIG_RELOADED = "config.reloaded"
    
    # System
    SYSTEM_STARTED = "system.started"
    SYSTEM_STOPPED = "system.stopped"
    
    # Security
    SECURITY_VIOLATION = "security.violation"
    ACCESS_DENIED = "access.denied"


@dataclass
class AuditEvent:
    """Audit event data structure."""
    
    event_type: AuditEventType
    timestamp: datetime
    username: Optional[str] = None
    ip_address: Optional[str] = None
    resource: Optional[str] = None
    action: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    success: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data["event_type"] = self.event_type.value
        data["timestamp"] = self.timestamp.isoformat()
        return data


class AuditLogger:
    """Audit logger for tracking security events."""

    def __init__(self):
        self._events: List[AuditEvent] = []
        self._max_events = 10000
        self.storage = None

    async def log(self, event: AuditEvent) -> None:
        """
        Log an audit event.
        
        Args:
            event: Audit event to log
        """
        # Add to in-memory buffer
        self._events.append(event)
        if len(self._events) > self._max_events:
            self._events.pop(0)
        
        # Log to structured logger
        logger.info(
            "Audit event",
            event_type=event.event_type.value,
            username=event.username,
            resource=event.resource,
            action=event.action,
            success=event.success,
            details=event.details
        )
        
        # Store persistently
        if self.storage:
            key = f"audit:{event.timestamp.timestamp()}:{event.event_type.value}"
            await self.storage.set(key, event.to_dict())

    async def log_login(self, username: str, success: bool, ip_address: Optional[str] = None):
        """Log a login attempt."""
        await self.log(AuditEvent(
            event_type=AuditEventType.AUTH_LOGIN if success else AuditEventType.AUTH_FAILED,
            timestamp=datetime.utcnow(),
            username=username,
            ip_address=ip_address,
            action="login",
            success=success
        ))

    async def log_logout(self, username: str, ip_address: Optional[str] = None):
        """Log a logout."""
        await self.log(AuditEvent(
            event_type=AuditEventType.AUTH_LOGOUT,
            timestamp=datetime.utcnow(),
            username=username,
            ip_address=ip_address,
            action="logout"
        ))

    async def log_plugin_action(
        self,
        action: str,
        plugin_name: str,
        username: Optional[str] = None,
        success: bool = True,
        details: Optional[Dict[str, Any]] = None
    ):
        """Log a plugin management action."""
        event_type_map = {
            "load": AuditEventType.PLUGIN_LOADED,
            "unload": AuditEventType.PLUGIN_UNLOADED,
            "enable": AuditEventType.PLUGIN_ENABLED,
            "disable": AuditEventType.PLUGIN_DISABLED,
            "configure": AuditEventType.PLUGIN_CONFIGURED,
        }
        
        await self.log(AuditEvent(
            event_type=event_type_map.get(action, AuditEventType.PLUGIN_CONFIGURED),
            timestamp=datetime.utcnow(),
            username=username,
            resource=f"plugin:{plugin_name}",
            action=action,
            success=success,
            details=details or {}
        ))

    async def log_permission_change(
        self,
        action: str,
        username_target: str,
        username_actor: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Log a permission change."""
        event_type = (
            AuditEventType.PERMISSION_GRANTED if action == "grant"
            else AuditEventType.PERMISSION_REVOKED
        )
        
        await self.log(AuditEvent(
            event_type=event_type,
            timestamp=datetime.utcnow(),
            username=username_actor,
            resource=f"user:{username_target}",
            action=action,
            details=details or {}
        ))

    async def log_access_denied(
        self,
        username: str,
        resource: str,
        action: str,
        reason: str
    ):
        """Log an access denied event."""
        await self.log(AuditEvent(
            event_type=AuditEventType.ACCESS_DENIED,
            timestamp=datetime.utcnow(),
            username=username,
            resource=resource,
            action=action,
            success=False,
            details={"reason": reason}
        ))

    def get_events(
        self,
        event_type: Optional[AuditEventType] = None,
        username: Optional[str] = None,
        limit: int = 100
    ) -> List[AuditEvent]:
        """
        Get audit events with optional filtering.
        
        Args:
            event_type: Filter by event type
            username: Filter by username
            limit: Maximum number of events to return
            
        Returns:
            List of audit events
        """
        events = self._events.copy()
        
        # Apply filters
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        if username:
            events = [e for e in events if e.username == username]
        
        # Return most recent first
        events.reverse()
        return events[:limit]

    def get_stats(self) -> Dict[str, Any]:
        """Get audit statistics."""
        total = len(self._events)
        by_type = {}
        by_user = {}
        failed = 0
        
        for event in self._events:
            # By type
            event_type = event.event_type.value
            by_type[event_type] = by_type.get(event_type, 0) + 1
            
            # By user
            if event.username:
                by_user[event.username] = by_user.get(event.username, 0) + 1
            
            # Failed events
            if not event.success:
                failed += 1
        
        return {
            "total_events": total,
            "failed_events": failed,
            "by_type": by_type,
            "by_user": by_user
        }

    async def export_events(
        self,
        filepath: str,
        event_type: Optional[AuditEventType] = None,
        username: Optional[str] = None
    ) -> bool:
        """Export audit events to a file."""
        try:
            events = self.get_events(event_type, username, limit=len(self._events))
            data = [event.to_dict() for event in events]
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info("Audit events exported", filepath=filepath, count=len(events))
            return True
        except Exception as e:
            logger.error("Failed to export audit events", error=str(e))
            return False


# Global audit logger
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get the global audit logger."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
        _audit_logger.storage = get_storage()
    return _audit_logger

