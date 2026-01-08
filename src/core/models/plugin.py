"""Plugin settings database model."""

from datetime import datetime
from sqlalchemy import Column, String, Boolean, Integer, JSON, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class PluginSetting(Base):
    """Plugin setting model (inspired by LangBot).
    
    Stores plugin metadata, configuration, and state.
    """
    __tablename__ = 'plugin_settings'
    
    # Composite primary key: author + name
    plugin_author = Column(String(255), primary_key=True, nullable=False)
    plugin_name = Column(String(255), primary_key=True, nullable=False)
    
    # Plugin state
    enabled = Column(Boolean, nullable=False, default=True)
    priority = Column(Integer, nullable=False, default=0)
    
    # Plugin configuration
    config = Column(JSON, nullable=False, default=dict)
    
    # Installation info
    install_source = Column(String(255), nullable=False, default='local')
    install_info = Column(JSON, nullable=False, default=dict)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<PluginSetting(author='{self.plugin_author}', name='{self.plugin_name}', enabled={self.enabled})>"
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'plugin_author': self.plugin_author,
            'plugin_name': self.plugin_name,
            'enabled': self.enabled,
            'priority': self.priority,
            'config': self.config,
            'install_source': self.install_source,
            'install_info': self.install_info,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

