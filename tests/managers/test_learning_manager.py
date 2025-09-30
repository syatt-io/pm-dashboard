"""Tests for LearningManager."""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch
from src.managers.learning_manager import LearningManager
from src.models import Learning


@pytest.fixture
def learning_manager(db_session):
    """Create LearningManager instance with test database."""
    with patch('src.managers.learning_manager.session_scope') as mock_scope:
        mock_scope.return_value.__enter__.return_value = db_session
        yield LearningManager()


def test_create_learning(learning_manager, db_session):
    """Test creating a new learning."""
    with patch('src.managers.learning_manager.session_scope') as mock_scope:
        mock_scope.return_value.__enter__.return_value = db_session

        learning = learning_manager.create_learning(
            content='Test learning content',
            submitted_by='Test User',
            submitted_by_id='1',
            category='technical',
            source='web'
        )

        assert learning is not None
        assert learning.content == 'Test learning content'
        assert learning.category == 'technical'
        assert learning.submitted_by == 'Test User'


def test_get_learnings(learning_manager, db_session, sample_learning):
    """Test getting list of learnings."""
    with patch('src.managers.learning_manager.session_scope') as mock_scope:
        mock_scope.return_value.__enter__.return_value = db_session

        learnings = learning_manager.get_learnings(limit=10, offset=0)

        assert len(learnings) >= 1
        assert any(l.content == 'Test learning content' for l in learnings)


def test_get_learnings_with_category_filter(learning_manager, db_session, sample_learning):
    """Test getting learnings filtered by category."""
    with patch('src.managers.learning_manager.session_scope') as mock_scope:
        mock_scope.return_value.__enter__.return_value = db_session

        learnings = learning_manager.get_learnings(
            category='technical',
            limit=10,
            offset=0
        )

        assert all(l.category == 'technical' for l in learnings)


def test_get_learning_by_id(learning_manager, db_session, sample_learning):
    """Test getting a single learning by ID."""
    with patch('src.managers.learning_manager.session_scope') as mock_scope:
        mock_scope.return_value.__enter__.return_value = db_session

        learning = learning_manager.get_learning(sample_learning.id)

        assert learning is not None
        assert learning.id == sample_learning.id


def test_get_learning_not_found(learning_manager, db_session):
    """Test getting non-existent learning."""
    with patch('src.managers.learning_manager.session_scope') as mock_scope:
        mock_scope.return_value.__enter__.return_value = db_session

        learning = learning_manager.get_learning(99999)

        assert learning is None


def test_update_learning(learning_manager, db_session, sample_learning):
    """Test updating a learning."""
    with patch('src.managers.learning_manager.session_scope') as mock_scope:
        mock_scope.return_value.__enter__.return_value = db_session

        success = learning_manager.update_learning(
            learning_id=sample_learning.id,
            content='Updated content',
            category='process'
        )

        assert success is True

        # Verify update
        updated = db_session.query(Learning).filter_by(id=sample_learning.id).first()
        assert updated.content == 'Updated content'
        assert updated.category == 'process'


def test_update_learning_not_found(learning_manager, db_session):
    """Test updating non-existent learning."""
    with patch('src.managers.learning_manager.session_scope') as mock_scope:
        mock_scope.return_value.__enter__.return_value = db_session

        success = learning_manager.update_learning(
            learning_id=99999,
            content='Updated content'
        )

        assert success is False


def test_archive_learning(learning_manager, db_session, sample_learning):
    """Test archiving a learning."""
    with patch('src.managers.learning_manager.session_scope') as mock_scope:
        mock_scope.return_value.__enter__.return_value = db_session

        success = learning_manager.archive_learning(sample_learning.id)

        assert success is True

        # Verify archived
        archived = db_session.query(Learning).filter_by(id=sample_learning.id).first()
        assert archived.archived is True


def test_search_learnings(learning_manager, db_session, sample_learning):
    """Test searching learnings by content."""
    with patch('src.managers.learning_manager.session_scope') as mock_scope:
        mock_scope.return_value.__enter__.return_value = db_session

        results = learning_manager.search_learnings('test')

        assert len(results) >= 1
        assert any('test' in l.content.lower() for l in results)


def test_get_categories(learning_manager, db_session, sample_learning):
    """Test getting distinct categories."""
    with patch('src.managers.learning_manager.session_scope') as mock_scope:
        mock_scope.return_value.__enter__.return_value = db_session

        # Add another learning with different category
        learning2 = Learning(
            content='Process learning',
            category='process',
            submitted_by='Test User',
            submitted_by_id='1',
            source='web'
        )
        db_session.add(learning2)
        db_session.commit()

        categories = learning_manager.get_categories()

        assert 'technical' in categories
        assert 'process' in categories


def test_get_stats(learning_manager, db_session, sample_learning):
    """Test getting learning statistics."""
    with patch('src.managers.learning_manager.session_scope') as mock_scope:
        mock_scope.return_value.__enter__.return_value = db_session

        stats = learning_manager.get_stats()

        assert 'total' in stats
        assert stats['total'] >= 1
        assert 'by_category' in stats
