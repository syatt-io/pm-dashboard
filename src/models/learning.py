"""Learning model for storing team learnings and insights."""
from sqlalchemy import Column, String, Text, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import uuid

Base = declarative_base()


class Learning(Base):
    """Model for storing learnings and insights from retrospectives and daily work."""
    __tablename__ = 'learnings'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    content = Column(Text, nullable=False)
    category = Column(String(100))  # Optional category for future use
    submitted_by = Column(String(255), nullable=False)  # Slack username
    submitted_by_id = Column(String(100))  # Slack user ID
    source = Column(String(50), default='slack')  # slack, web, retrospective
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_archived = Column(Boolean, default=False)

    def to_dict(self):
        """Convert learning to dictionary."""
        return {
            'id': self.id,
            'content': self.content,
            'category': self.category,
            'submitted_by': self.submitted_by,
            'submitted_by_id': self.submitted_by_id,
            'source': self.source,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'is_archived': self.is_archived
        }