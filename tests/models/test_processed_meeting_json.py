"""Tests for ProcessedMeeting JSON serialization.

This test would have caught the JSON serialization bug where dict/list
objects were being stored directly in TEXT columns instead of JSON strings.
"""

import pytest
import json
from datetime import datetime, timezone
from src.models import ProcessedMeeting
from src.models.dtos import ProcessedMeetingDTO
from src.utils.database import session_scope


def test_processed_meeting_stores_json_as_strings(db_session):
    """Test that ProcessedMeeting correctly stores JSON fields as strings."""
    import uuid

    # Sample data that would cause the bug
    action_items = [
        {
            'title': 'Fix bug',
            'description': 'Fix the navigation issue',
            'assignee': 'John Doe',
            'priority': 'High'
        }
    ]
    key_decisions = ['Decision 1', 'Decision 2']
    blockers = ['Blocker 1']

    # Create ProcessedMeeting with JSON fields
    meeting = ProcessedMeeting(
        id=str(uuid.uuid4()),
        fireflies_id='test-123',
        title='Test Meeting',
        date=datetime.now(timezone.utc),
        summary='Test summary',
        action_items=json.dumps(action_items),  # Should be JSON string
        key_decisions=json.dumps(key_decisions),  # Should be JSON string
        blockers=json.dumps(blockers),  # Should be JSON string
        analyzed_at=datetime.now(timezone.utc)
    )

    # Add to session and commit (this would fail with the bug)
    db_session.add(meeting)
    db_session.commit()

    # Verify it was stored
    stored_meeting = db_session.query(ProcessedMeeting).filter_by(
        fireflies_id='test-123'
    ).first()

    assert stored_meeting is not None
    assert stored_meeting.title == 'Test Meeting'

    # Verify JSON fields are stored as strings
    assert isinstance(stored_meeting.action_items, str)
    assert isinstance(stored_meeting.key_decisions, str)
    assert isinstance(stored_meeting.blockers, str)

    # Verify they can be parsed back to original data
    parsed_actions = json.loads(stored_meeting.action_items)
    assert len(parsed_actions) == 1
    assert parsed_actions[0]['title'] == 'Fix bug'

    parsed_decisions = json.loads(stored_meeting.key_decisions)
    assert parsed_decisions == key_decisions

    parsed_blockers = json.loads(stored_meeting.blockers)
    assert parsed_blockers == blockers


def test_processed_meeting_dto_handles_json_strings(db_session):
    """Test that DTO correctly parses JSON strings from database."""
    import uuid

    # Create meeting with JSON strings (as stored in DB)
    meeting = ProcessedMeeting(
        id=str(uuid.uuid4()),
        fireflies_id='test-456',
        title='Test Meeting DTO',
        date=datetime.now(timezone.utc),
        summary='Test summary',
        action_items=json.dumps([{'title': 'Action 1'}]),
        key_decisions=json.dumps(['Decision 1', 'Decision 2']),
        blockers=json.dumps(['Blocker 1']),
        analyzed_at=datetime.now(timezone.utc)
    )

    db_session.add(meeting)
    db_session.commit()

    # Retrieve and convert to DTO
    stored_meeting = db_session.query(ProcessedMeeting).filter_by(
        fireflies_id='test-456'
    ).first()

    dto = ProcessedMeetingDTO.from_orm(stored_meeting)

    # Verify DTO parsed JSON strings to Python objects
    assert isinstance(dto.action_items, list)
    assert len(dto.action_items) == 1
    assert dto.action_items[0]['title'] == 'Action 1'

    assert isinstance(dto.key_decisions, list)
    assert len(dto.key_decisions) == 2
    assert dto.key_decisions[0] == 'Decision 1'

    assert isinstance(dto.blockers, list)
    assert len(dto.blockers) == 1


def test_processed_meeting_dto_handles_none_json_fields(db_session):
    """Test that DTO handles None JSON fields gracefully."""
    import uuid

    meeting = ProcessedMeeting(
        id=str(uuid.uuid4()),
        fireflies_id='test-789',
        title='Test Meeting None',
        date=datetime.now(timezone.utc),
        summary='Test summary',
        action_items=None,
        key_decisions=None,
        blockers=None,
        analyzed_at=datetime.now(timezone.utc)
    )

    db_session.add(meeting)
    db_session.commit()

    stored_meeting = db_session.query(ProcessedMeeting).filter_by(
        fireflies_id='test-789'
    ).first()

    dto = ProcessedMeetingDTO.from_orm(stored_meeting)

    # Should default to empty lists
    assert dto.action_items == []
    assert dto.key_decisions == []
    assert dto.blockers == []


def test_processed_meeting_dto_handles_invalid_json(db_session):
    """Test that DTO handles invalid JSON strings gracefully."""
    import uuid
    from sqlalchemy import text

    # Create a mock meeting with invalid JSON (shouldn't happen, but defensive)
    meeting = ProcessedMeeting(
        id=str(uuid.uuid4()),
        fireflies_id='test-invalid',
        title='Test Invalid JSON',
        date=datetime.now(timezone.utc),
        summary='Test summary',
        analyzed_at=datetime.now(timezone.utc)
    )

    db_session.add(meeting)
    db_session.flush()

    # Manually set invalid JSON (bypassing ORM validation)
    db_session.execute(
        text("UPDATE processed_meetings SET action_items = 'invalid json' WHERE fireflies_id = 'test-invalid'")
    )
    db_session.commit()

    stored_meeting = db_session.query(ProcessedMeeting).filter_by(
        fireflies_id='test-invalid'
    ).first()

    # Should handle gracefully and return empty list
    dto = ProcessedMeetingDTO.from_orm(stored_meeting)
    assert dto.action_items == []
