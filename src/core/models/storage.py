"""Binary storage database model."""

from datetime import datetime
from sqlalchemy import Column, String, LargeBinary, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class BinaryStorage(Base):
    """Binary storage model (inspired by LangBot).
    
    Used for storing binary data such as plugin assets, uploaded files, etc.
    Maximum recommended size per entry: 10MB
    """
    __tablename__ = 'binary_storages'
    
    # Unique key composed of owner_type, owner, and key
    unique_key = Column(String(255), primary_key=True, nullable=False)
    
    # Storage metadata
    key = Column(String(255), nullable=False, index=True)
    owner_type = Column(String(255), nullable=False, index=True)  # e.g., 'plugin', 'system'
    owner = Column(String(255), nullable=False, index=True)  # e.g., plugin name
    
    # Binary data
    value = Column(LargeBinary, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        size = len(self.value) if self.value else 0
        return f"<BinaryStorage(key='{self.key}', owner='{self.owner}', size={size} bytes)>"
    
    def to_dict(self, include_value=False):
        """Convert to dictionary.
        
        Args:
            include_value: Whether to include binary value (default: False)
        """
        result = {
            'unique_key': self.unique_key,
            'key': self.key,
            'owner_type': self.owner_type,
            'owner': self.owner,
            'size': len(self.value) if self.value else 0,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
        
        if include_value:
            result['value'] = self.value
        
        return result
    
    @staticmethod
    def make_unique_key(owner_type: str, owner: str, key: str) -> str:
        """Generate unique key from components."""
        return f"{owner_type}:{owner}:{key}"

