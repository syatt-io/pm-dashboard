"""Data Transfer Objects (DTOs) for database models.

These DTOs solve the "detached object" problem by copying data from SQLAlchemy
objects while the session is still active. They are plain Python objects that
can be safely used after the session is closed.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any


@dataclass
class ProcessedMeetingDTO:
    """DTO for ProcessedMeeting model."""
    meeting_id: str
    title: Optional[str] = None
    date: Optional[datetime] = None
    processed_at: Optional[datetime] = None
    analyzed_at: Optional[datetime] = None
    summary: Optional[str] = None
    key_decisions: List[str] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)
    action_items: List[Dict[str, Any]] = field(default_factory=list)
    tickets_created: List[str] = field(default_factory=list)
    todos_created: List[str] = field(default_factory=list)
    success: bool = True

    @classmethod
    def from_orm(cls, meeting):
        """Create DTO from SQLAlchemy ProcessedMeeting object.

        Must be called while the session is still active!
        """
        if meeting is None:
            return None

        return cls(
            meeting_id=meeting.fireflies_id,
            title=meeting.title,
            date=meeting.date,
            processed_at=meeting.processed_at,
            analyzed_at=meeting.analyzed_at,
            summary=meeting.summary,
            key_decisions=meeting.key_decisions or [],
            blockers=meeting.blockers or [],
            action_items=meeting.action_items or [],
            tickets_created=meeting.tickets_created or [],
            todos_created=meeting.todos_created or [],
            success=meeting.success if hasattr(meeting, 'success') else True
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'meeting_id': self.meeting_id,
            'title': self.title,
            'date': self.date.isoformat() if self.date else None,
            'processed_at': self.processed_at.isoformat() if self.processed_at else None,
            'analyzed_at': self.analyzed_at.isoformat() if self.analyzed_at else None,
            'summary': self.summary,
            'key_decisions': self.key_decisions,
            'blockers': self.blockers,
            'action_items': self.action_items,
            'tickets_created': self.tickets_created,
            'todos_created': self.todos_created,
            'success': self.success
        }


@dataclass
class TodoItemDTO:
    """DTO for TodoItem model."""
    id: str
    title: str
    description: Optional[str] = None
    assignee: Optional[str] = None
    priority: str = 'Medium'
    status: str = 'pending'
    project_key: Optional[str] = None
    user_id: Optional[int] = None
    ticket_key: Optional[str] = None
    source_meeting_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    due_date: Optional[datetime] = None

    @classmethod
    def from_orm(cls, todo):
        """Create DTO from SQLAlchemy TodoItem object.

        Must be called while the session is still active!
        """
        if todo is None:
            return None

        return cls(
            id=todo.id,
            title=todo.title,
            description=todo.description,
            assignee=todo.assignee,
            priority=getattr(todo, 'priority', 'Medium'),
            status=todo.status,
            project_key=getattr(todo, 'project_key', None),
            user_id=getattr(todo, 'user_id', None),
            ticket_key=todo.ticket_key,
            source_meeting_id=getattr(todo, 'source_meeting_id', None),
            created_at=todo.created_at,
            updated_at=todo.updated_at,
            due_date=todo.due_date
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'assignee': self.assignee,
            'priority': self.priority,
            'status': self.status,
            'project_key': self.project_key,
            'user_id': self.user_id,
            'ticket_key': self.ticket_key,
            'source_meeting_id': self.source_meeting_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'due_date': self.due_date.isoformat() if self.due_date else None
        }


@dataclass
class UserDTO:
    """DTO for User model."""
    id: int
    email: str
    name: str
    google_id: str
    role: str  # Store as string to avoid enum detachment issues
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    is_active: bool = True
    has_fireflies_key: bool = False

    @classmethod
    def from_orm(cls, user):
        """Create DTO from SQLAlchemy User object.

        Must be called while the session is still active!
        """
        if user is None:
            return None

        # Safely get role value
        role_value = user.role.value if hasattr(user.role, 'value') else str(user.role)

        return cls(
            id=user.id,
            email=user.email,
            name=user.name,
            google_id=user.google_id,
            role=role_value,
            created_at=user.created_at,
            updated_at=user.updated_at,
            last_login=user.last_login,
            is_active=user.is_active,
            has_fireflies_key=user.has_fireflies_api_key()
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'role': self.role,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'is_active': self.is_active,
            'has_fireflies_key': self.has_fireflies_key
        }

    def is_admin(self) -> bool:
        """Check if user is admin."""
        return self.role == 'admin'

    def can_access(self) -> bool:
        """Check if user can access the system."""
        return self.role != 'no_access' and self.is_active


@dataclass
class UserWatchedProjectDTO:
    """DTO for UserWatchedProject model."""
    id: int
    user_id: int
    project_key: str
    created_at: Optional[datetime] = None

    @classmethod
    def from_orm(cls, watched_project):
        """Create DTO from SQLAlchemy UserWatchedProject object.

        Must be called while the session is still active!
        """
        if watched_project is None:
            return None

        return cls(
            id=watched_project.id,
            user_id=watched_project.user_id,
            project_key=watched_project.project_key,
            created_at=watched_project.created_at
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'project_key': self.project_key,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


@dataclass
class LearningDTO:
    """DTO for Learning model."""
    id: int
    user_id: Optional[int] = None
    title: str = ""
    description: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[str] = None
    source: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @classmethod
    def from_orm(cls, learning):
        """Create DTO from SQLAlchemy Learning object.

        Must be called while the session is still active!
        """
        if learning is None:
            return None

        return cls(
            id=learning.id,
            user_id=learning.user_id,
            title=learning.title,
            description=learning.description,
            category=learning.category,
            tags=learning.tags,
            source=learning.source,
            created_at=learning.created_at,
            updated_at=learning.updated_at
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'title': self.title,
            'description': self.description,
            'category': self.category,
            'tags': self.tags,
            'source': self.source,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


# Convenience function for bulk conversion
def convert_list_to_dtos(orm_objects, dto_class):
    """Convert a list of ORM objects to DTOs.

    Args:
        orm_objects: List of SQLAlchemy model instances
        dto_class: The DTO class to convert to

    Returns:
        List of DTO instances

    Must be called while the session is still active!
    """
    return [dto_class.from_orm(obj) for obj in orm_objects if obj is not None]
