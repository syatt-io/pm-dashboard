"""Learning model for storing team learnings and insights."""
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from .base import Base


class Learning(Base):
    """Model for storing learnings and insights from retrospectives and daily work."""
    __tablename__ = 'learnings'

    # Match production schema
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'))
    title = Column(String(255), nullable=False)
    description = Column(Text)
    category = Column(String(100))
    tags = Column(Text)
    source = Column(String(255))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationship to User model
    user = relationship("User", foreign_keys=[user_id], lazy='joined')

    def to_dict(self):
        """Convert learning to dictionary."""
        # Combine title and description into content for frontend compatibility
        content = self.description if self.description else self.title

        # Get submitted_by from user relationship if available
        submitted_by = "Unknown"
        if self.user:
            submitted_by = self.user.name or self.user.email or f"User {self.user_id}"

        return {
            'id': self.id,
            'user_id': self.user_id,
            'title': self.title,
            'description': self.description,
            'content': content,  # Combined field for frontend
            'submitted_by': submitted_by,  # Username from user relationship
            'category': self.category,
            'tags': self.tags,
            'source': self.source,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }