"""Tests for Data Transfer Objects (DTOs)."""

import pytest
from datetime import datetime
from unittest.mock import Mock
from src.models.dtos import (
    ProcessedMeetingDTO,
    TodoItemDTO,
    UserDTO,
    LearningDTO,
    convert_list_to_dtos
)
from src.models import User, UserRole, Learning, TodoItem


def test_user_dto_from_orm():
    """Test converting User ORM object to DTO."""
    user = User(
        id=1,
        email='test@example.com',
        name='Test User',
        role=UserRole.USER,
        fireflies_api_key=None,
        google_oauth_token='token123'
    )
    user.created_at = datetime.now()
    user.updated_at = datetime.now()

    dto = UserDTO.from_orm(user)

    assert dto.id == 1
    assert dto.email == 'test@example.com'
    assert dto.name == 'Test User'
    assert dto.role == 'user'
    assert dto.google_oauth_token == 'token123'


def test_user_dto_to_dict():
    """Test converting UserDTO to dictionary."""
    dto = UserDTO(
        id=1,
        email='test@example.com',
        name='Test User',
        role='user',
        has_fireflies_key=False,
        google_oauth_token='token123',
        created_at=datetime.now(),
        updated_at=datetime.now()
    )

    data = dto.to_dict()

    assert data['id'] == 1
    assert data['email'] == 'test@example.com'
    assert data['name'] == 'Test User'
    assert data['has_fireflies_key'] is False


def test_learning_dto_from_orm(sample_learning):
    """Test converting Learning ORM object to DTO."""
    dto = LearningDTO.from_orm(sample_learning)

    assert dto.id == sample_learning.id
    assert dto.content == sample_learning.content
    assert dto.category == sample_learning.category
    assert dto.submitted_by == sample_learning.submitted_by


def test_learning_dto_to_dict():
    """Test converting LearningDTO to dictionary."""
    dto = LearningDTO(
        id=1,
        content='Test learning',
        category='technical',
        submitted_by='Test User',
        submitted_by_id='1',
        source='web',
        archived=False,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )

    data = dto.to_dict()

    assert data['id'] == 1
    assert data['content'] == 'Test learning'
    assert data['category'] == 'technical'
    assert data['archived'] is False


def test_todo_item_dto_from_orm(sample_todo):
    """Test converting TodoItem ORM object to DTO."""
    dto = TodoItemDTO.from_orm(sample_todo)

    assert dto.id == sample_todo.id
    assert dto.title == sample_todo.title
    assert dto.status == sample_todo.status
    assert dto.priority == sample_todo.priority


def test_todo_item_dto_to_dict():
    """Test converting TodoItemDTO to dictionary."""
    dto = TodoItemDTO(
        id='test-1',
        title='Test Todo',
        description='Test description',
        assignee='Test User',
        priority='High',
        status='pending',
        project_key='TEST',
        user_id=1,
        ticket_key=None,
        source_meeting_id=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        due_date=None
    )

    data = dto.to_dict()

    assert data['id'] == 'test-1'
    assert data['title'] == 'Test Todo'
    assert data['priority'] == 'High'
    assert data['status'] == 'pending'


def test_processed_meeting_dto_to_dict():
    """Test converting ProcessedMeetingDTO to dictionary."""
    dto = ProcessedMeetingDTO(
        id='meeting-1',
        title='Sprint Planning',
        fireflies_id='ff-123',
        date=datetime.now(),
        duration=3600,
        summary='Discussed project progress',
        action_items=[],
        created_at=datetime.now(),
        updated_at=datetime.now()
    )

    data = dto.to_dict()

    assert data['id'] == 'meeting-1'
    assert data['title'] == 'Sprint Planning'
    assert data['duration'] == 3600
    assert 'action_items' in data


def test_convert_list_to_dtos():
    """Test converting list of ORM objects to DTOs."""
    users = [
        User(id=1, email='user1@test.com', name='User 1', role=UserRole.USER),
        User(id=2, email='user2@test.com', name='User 2', role=UserRole.ADMIN)
    ]

    for user in users:
        user.created_at = datetime.now()
        user.updated_at = datetime.now()

    dtos = convert_list_to_dtos(users, UserDTO)

    assert len(dtos) == 2
    assert all(isinstance(dto, UserDTO) for dto in dtos)
    assert dtos[0].email == 'user1@test.com'
    assert dtos[1].email == 'user2@test.com'


def test_dto_handles_none_values():
    """Test that DTOs handle None values gracefully."""
    user = User(
        id=1,
        email='test@example.com',
        name=None,  # None value
        role=UserRole.USER,
        fireflies_api_key=None,
        google_oauth_token=None
    )
    user.created_at = datetime.now()
    user.updated_at = datetime.now()

    dto = UserDTO.from_orm(user)

    assert dto.name is None
    assert dto.google_oauth_token is None
    assert dto.has_fireflies_key is False


def test_dto_preserves_datetime_fields():
    """Test that DTOs preserve datetime fields correctly."""
    now = datetime.now()
    learning = Learning(
        content='Test',
        category='technical',
        submitted_by='User',
        submitted_by_id='1',
        source='web'
    )
    learning.created_at = now
    learning.updated_at = now

    dto = LearningDTO.from_orm(learning)

    assert dto.created_at == now
    assert dto.updated_at == now
    assert isinstance(dto.created_at, datetime)
    assert isinstance(dto.updated_at, datetime)
