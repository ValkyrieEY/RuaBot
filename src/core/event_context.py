"""Event context system for plugins to modify events."""

from typing import Any, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime
import uuid


@dataclass
class EventContext:
    """Event context that can be modified by plugins.
    
    Similar to LangBot's EventContext, allows plugins to:
    - Modify event data
    - Prevent default behavior
    - Add custom data
    """
    
    event_name: str
    """Event name (e.g., 'message.received', 'message.before_send')"""
    
    event_data: Dict[str, Any]
    """Event data (can be modified by plugins)"""
    
    context_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    """Unique context ID"""
    
    timestamp: datetime = field(default_factory=datetime.now)
    """Event timestamp"""
    
    source: Optional[str] = None
    """Event source (e.g., 'onebot', 'plugin:xxx')"""
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    """Additional metadata"""
    
    _prevented_default: bool = False
    """Whether default behavior is prevented"""
    
    _modified: bool = False
    """Whether event data was modified"""
    
    def prevent_default(self) -> None:
        """Prevent default behavior."""
        self._prevented_default = True
    
    def is_prevented_default(self) -> bool:
        """Check if default behavior is prevented."""
        return self._prevented_default
    
    def mark_modified(self) -> None:
        """Mark event as modified."""
        self._modified = True
    
    def is_modified(self) -> bool:
        """Check if event was modified."""
        return self._modified
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'context_id': self.context_id,
            'event_name': self.event_name,
            'event_data': self.event_data,
            'timestamp': self.timestamp.isoformat(),
            'source': self.source,
            'metadata': self.metadata,
            'prevented_default': self._prevented_default,
            'modified': self._modified,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EventContext':
        """Create from dictionary."""
        ctx = cls(
            event_name=data['event_name'],
            event_data=data['event_data'],
            context_id=data.get('context_id', str(uuid.uuid4())),
            timestamp=datetime.fromisoformat(data['timestamp']) if isinstance(data.get('timestamp'), str) else data.get('timestamp', datetime.now()),
            source=data.get('source'),
            metadata=data.get('metadata', {}),
        )
        ctx._prevented_default = data.get('prevented_default', False)
        ctx._modified = data.get('modified', False)
        return ctx

