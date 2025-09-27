"""User model and authentication-related models."""
from sqlalchemy import Column, Integer, String, DateTime, Enum, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

Base = declarative_base()


class UserRole(enum.Enum):
    """User role enumeration."""
    NO_ACCESS = "no_access"
    MEMBER = "member"
    ADMIN = "admin"


class User(Base):
    """User model for authentication and authorization."""
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    google_id = Column(String(255), unique=True, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.NO_ACCESS, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime)
    is_active = Column(Boolean, default=True)

    # Relationships
    # todos = relationship("TodoItem", back_populates="user", cascade="all, delete-orphan")
    # meetings = relationship("ProcessedMeeting", back_populates="user", cascade="all, delete-orphan")
    # preferences = relationship("UserPreference", back_populates="user", cascade="all, delete-orphan")

    def to_dict(self):
        """Convert user to dictionary."""
        return {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'role': self.role.value,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'is_active': self.is_active
        }

    def has_role(self, role):
        """Check if user has a specific role."""
        if isinstance(role, str):
            role = UserRole[role.upper()]
        return self.role == role

    def is_admin(self):
        """Check if user is admin."""
        return self.role == UserRole.ADMIN

    def can_access(self):
        """Check if user can access the system."""
        return self.role != UserRole.NO_ACCESS and self.is_active


class UserWatchedProject(Base):
    """Model for tracking which projects a user is watching."""
    __tablename__ = 'user_watched_projects'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    project_key = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Ensure unique combination of user_id and project_key
    __table_args__ = (UniqueConstraint('user_id', 'project_key', name='_user_project_watch_uc'),)

    # Relationship back to user
    user = relationship("User", backref="watched_projects")

    def to_dict(self):
        """Convert watched project to dictionary."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'project_key': self.project_key,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }