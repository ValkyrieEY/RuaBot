"""Audit logging for security and compliance."""

import asyncio
import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum

from ..core.logger import get_logger
from ..core.storage import get_storage

logger = get_logger(__name__)
AUDIT_EVENT_RETENTION_LIMIT = 200


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

    # WebUI operations
    WEBUI_ACTION = "webui.action"


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
        self._max_events = AUDIT_EVENT_RETENTION_LIMIT
        self._prune_lock = asyncio.Lock()
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
            self._events = self._events[-self._max_events:]
        
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
            key = f"audit:{event.timestamp.timestamp()}:{event.event_type.value}:{uuid.uuid4().hex}"
            await self.storage.set(key, event.to_dict())
            await self._prune_persistent_events()

    def _audit_key_timestamp(self, key: str) -> float:
        try:
            return float(key.split(":", 3)[1])
        except Exception:
            return 0.0

    async def _prune_persistent_events(self) -> None:
        """Keep persistent audit records bounded to the retention limit."""
        if not self.storage:
            return

        async with self._prune_lock:
            try:
                keys = await self.storage.keys("audit:*")
                excess_count = len(keys) - self._max_events
                if excess_count <= 0:
                    return

                keys.sort(key=self._audit_key_timestamp, reverse=True)
                for key in keys[self._max_events:]:
                    await self.storage.delete(key)

                logger.info(
                    "Pruned old audit events",
                    deleted=excess_count,
                    retained=self._max_events,
                )
            except Exception as exc:
                logger.warning("Failed to prune persistent audit events", error=str(exc))

    async def log_login(
        self,
        username: str,
        success: bool,
        ip_address: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Log a login attempt."""
        await self.log(AuditEvent(
            event_type=AuditEventType.AUTH_LOGIN if success else AuditEventType.AUTH_FAILED,
            timestamp=datetime.utcnow(),
            username=username,
            ip_address=ip_address,
            action="login",
            success=success,
            details=details or {},
        ))

    async def log_logout(
        self,
        username: str,
        ip_address: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Log a logout."""
        await self.log(AuditEvent(
            event_type=AuditEventType.AUTH_LOGOUT,
            timestamp=datetime.utcnow(),
            username=username,
            ip_address=ip_address,
            action="logout",
            details=details or {},
        ))

    async def log_webui_action(
        self,
        username: Optional[str],
        action: str,
        resource: str,
        success: bool = True,
        ip_address: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Log a WebUI operation."""
        await self.log(AuditEvent(
            event_type=AuditEventType.WEBUI_ACTION,
            timestamp=datetime.utcnow(),
            username=username,
            ip_address=ip_address,
            resource=resource,
            action=action,
            success=success,
            details=details or {},
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
        reason: str,
        ip_address: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Log an access denied event."""
        event_details = details.copy() if isinstance(details, dict) else {}
        event_details["reason"] = reason
        await self.log(AuditEvent(
            event_type=AuditEventType.ACCESS_DENIED,
            timestamp=datetime.utcnow(),
            username=username,
            ip_address=ip_address,
            resource=resource,
            action=action,
            success=False,
            details=event_details,
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

    async def get_event_dicts(
        self,
        event_type: Optional[str] = None,
        username: Optional[str] = None,
        limit: int = 200,
        since: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Get audit events from memory and persistent storage as dictionaries."""
        events_by_key: Dict[str, Dict[str, Any]] = {}

        def parse_timestamp(data: Dict[str, Any]) -> Optional[datetime]:
            raw = data.get("timestamp")
            if not raw:
                return None
            if isinstance(raw, datetime):
                return raw.replace(tzinfo=None)
            try:
                return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).replace(tzinfo=None)
            except Exception:
                return None

        def event_key(data: Dict[str, Any]) -> str:
            return json.dumps(
                {
                    "event_type": data.get("event_type"),
                    "timestamp": data.get("timestamp"),
                    "username": data.get("username"),
                    "ip_address": data.get("ip_address"),
                    "resource": data.get("resource"),
                    "action": data.get("action"),
                    "success": data.get("success"),
                    "details": data.get("details"),
                },
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            )

        for event in self._events:
            data = event.to_dict()
            events_by_key[event_key(data)] = data

        if self.storage:
            try:
                await self._prune_persistent_events()
                keys = await self.storage.keys("audit:*")
                for key in keys:
                    value = await self.storage.get(key)
                    if isinstance(value, dict):
                        events_by_key[event_key(value)] = value
            except Exception as e:
                logger.warning("Failed to read persistent audit events", error=str(e))

        events = list(events_by_key.values())
        if event_type:
            events = [event for event in events if str(event.get("event_type")) == event_type]
        if username:
            events = [event for event in events if str(event.get("username") or "") == username]
        if since:
            events = [
                event for event in events
                if (event_time := parse_timestamp(event)) is not None and event_time >= since
            ]

        def sort_key(event: Dict[str, Any]) -> str:
            return str(event.get("timestamp") or "")

        events.sort(key=sort_key, reverse=True)
        return events[: max(1, min(int(limit or 200), self._max_events))]

    async def get_stats_async(self) -> Dict[str, Any]:
        """Get stats across persistent audit events."""
        events = await self.get_event_dicts(limit=10000)
        total = len(events)
        failed = 0
        by_type: Dict[str, int] = {}
        by_user: Dict[str, int] = {}

        for event in events:
            event_type = str(event.get("event_type") or "unknown")
            by_type[event_type] = by_type.get(event_type, 0) + 1
            username = str(event.get("username") or "")
            if username:
                by_user[username] = by_user.get(username, 0) + 1
            if not bool(event.get("success", True)):
                failed += 1

        return {
            "total_events": total,
            "failed_events": failed,
            "by_type": by_type,
            "by_user": by_user,
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

