"""Tests for Data Transfer Objects (DTOs)."""

import pytest
from datetime import datetime
from src.models.dtos import TodoItemDTO
from src.models import TodoItem


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
        id="test-1",
        title="Test Todo",
        description="Test description",
        assignee="Test User",
        priority="High",
        status="pending",
        project_key="TEST",
        user_id=1,
        ticket_key=None,
        source_meeting_id=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        due_date=None,
    )

    data = dto.to_dict()

    assert data["id"] == "test-1"
    assert data["title"] == "Test Todo"
    assert data["priority"] == "High"
    assert data["status"] == "pending"
