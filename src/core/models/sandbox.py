"""Sandbox database models."""

from datetime import datetime
from sqlalchemy import Column, String, Boolean, Integer, JSON, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Sandbox(Base):
    """Sandbox model for testing environment.
    
    Each sandbox creates an isolated testing environment where:
    - Messages are simulated and not sent to real QQ
    - Plugins can be tested without affecting real data
    - User can switch between different test scenarios
    """
    __tablename__ = 'sandboxes'
    uuid = Column(String(255), primary_key=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    enabled = Column(Boolean, nullable=False, default=True)
    mock_user_id = Column(String(255), nullable=False)
    mock_user_nickname = Column(String(255), nullable=False, default="")
    mock_group_id = Column(String(255), nullable=True)
    mock_group_name = Column(String(255), nullable=True)
    auto_reply = Column(Boolean, nullable=False, default=True)
    record_messages = Column(Boolean, nullable=False, default=True)
    use_plugins = Column(Boolean, nullable=False, default=True)
    message_count = Column(Integer, nullable=False, default=0)
    last_activity = Column(DateTime, nullable=True)
    config = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    def __repr__(self):
        return f"<Sandbox(uuid='{self.uuid}', name='{self.name}', enabled={self.enabled})>"
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'uuid': self.uuid,
            'name': self.name,
            'description': self.description,
            'enabled': self.enabled,
            'mock_user_id': self.mock_user_id,
            'mock_user_nickname': self.mock_user_nickname,
            'mock_group_id': self.mock_group_id,
            'mock_group_name': self.mock_group_name,
            'auto_reply': self.auto_reply,
            'record_messages': self.record_messages,
            'use_plugins': True,
            'message_count': self.message_count,
            'last_activity': self.last_activity.isoformat() if self.last_activity else None,
            'config': self.config,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class SandboxMessage(Base):
    """Sandbox message history.
    
    Records all messages exchanged within a sandbox for testing and debugging.
    """
    __tablename__ = 'sandbox_messages'
    id = Column(Integer, primary_key=True, autoincrement=True)
    sandbox_uuid = Column(String(255), nullable=False, index=True)
    message_type = Column(String(50), nullable=False)
    direction = Column(String(50), nullable=False)
    user_id = Column(String(255), nullable=False)
    user_nickname = Column(String(255), nullable=True)
    group_id = Column(String(255), nullable=True)
    group_name = Column(String(255), nullable=True)
    content = Column(Text, nullable=False)
    raw_message = Column(Text, nullable=True)
    processed_by_plugins = Column(Boolean, nullable=False, default=False)
    plugin_responses = Column(JSON, nullable=False, default=list)
    has_error = Column(Boolean, nullable=False, default=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    def __repr__(self):
        return f"<SandboxMessage(id={self.id}, sandbox='{self.sandbox_uuid}', direction='{self.direction}')>"
    def to_dict(self):
        return {
            'id': self.id,
            'sandbox_uuid': self.sandbox_uuid,
            'message_type': self.message_type,
            'direction': self.direction,
            'user_id': self.user_id,
            'user_nickname': self.user_nickname,
            'group_id': self.group_id,
            'group_name': self.group_name,
            'content': self.content,
            'raw_message': self.raw_message,
            'processed_by_plugins': self.processed_by_plugins,
            'plugin_responses': self.plugin_responses,
            'has_error': self.has_error,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
