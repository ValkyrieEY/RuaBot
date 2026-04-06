"""Persistent message event model for WebUI message log."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class MessageEvent(Base):
    """Stored message/notice/request event."""

    __tablename__ = "message_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(64), nullable=False, index=True)
    event_name = Column(String(64), nullable=False, index=True)  # onebot.message / notice / request
    source = Column(String(64), nullable=True, index=True)
    event_time = Column(DateTime, nullable=False, index=True, default=datetime.utcnow)
    payload = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "event_id": self.event_id,
            "event_name": self.event_name,
            "source": self.source,
            "event_time": self.event_time.isoformat() if self.event_time else None,
            "payload": self.payload or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

