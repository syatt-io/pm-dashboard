"""Project keywords model."""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from .base import Base


class ProjectKeyword(Base):
    """
    Keywords associated with projects for filtering meetings and searches.
    """
    __tablename__ = 'project_keywords'

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_key = Column(String(50), ForeignKey('projects.key', ondelete='CASCADE'),
                        nullable=False, index=True)
    keyword = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        UniqueConstraint('project_key', 'keyword', name='uq_project_keyword'),
    )

    def __repr__(self):
        return f"<ProjectKeyword(project={self.project_key}, keyword={self.keyword})>"

    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'id': self.id,
            'project_key': self.project_key,
            'keyword': self.keyword,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
