"""Pytest configuration and shared fixtures."""

import pytest
import os
import tempfile
from datetime import datetime
from unittest.mock import Mock, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Set test environment variables before importing app
os.environ['TESTING'] = 'true'
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['OPENAI_API_KEY'] = 'test-key'
os.environ['JIRA_URL'] = 'https://test.atlassian.net'
os.environ['JIRA_USERNAME'] = 'test@example.com'
os.environ['JIRA_API_TOKEN'] = 'test-token'
os.environ['ENCRYPTION_KEY'] = 'test-encryption-key-32-bytes-long!'
# ✅ FIXED: Add JWT_SECRET_KEY for tests (required after removing fallback)
os.environ['JWT_SECRET_KEY'] = 'test-jwt-secret-key-32-bytes-long-for-testing-only!'

from src.web_interface import app as flask_app
from src.models import Base, User, UserRole, Learning, TodoItem
from src.utils.database import get_engine


@pytest.fixture
def app():
    """Create Flask app for testing."""
    flask_app.config['TESTING'] = True
    flask_app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    yield flask_app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def db_engine():
    """Create in-memory database engine for testing."""
    engine = create_engine('sqlite:///:memory:', echo=False)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture
def db_session(db_engine):
    """Create database session for testing."""
    SessionLocal = sessionmaker(bind=db_engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def mock_user(db_session):
    """Create a mock user for testing."""
    user = User(
        email='test@example.com',
        name='Test User',
        role=UserRole.USER,
        fireflies_api_key=None,
        google_oauth_token=None
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def mock_admin_user(db_session):
    """Create a mock admin user for testing."""
    user = User(
        email='admin@example.com',
        name='Admin User',
        role=UserRole.ADMIN,
        fireflies_api_key=None,
        google_oauth_token=None
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(mock_user):
    """Create authorization headers with mock JWT token."""
    # In real tests, generate actual JWT token
    return {
        'Authorization': 'Bearer test-token',
        'Content-Type': 'application/json'
    }


@pytest.fixture
def sample_learning(db_session):
    """Create a sample learning entry."""
    learning = Learning(
        content='Test learning content',
        category='technical',
        submitted_by='Test User',
        submitted_by_id='1',
        source='web'
    )
    db_session.add(learning)
    db_session.commit()
    db_session.refresh(learning)
    return learning


@pytest.fixture
def sample_todo(db_session):
    """Create a sample todo item."""
    todo = TodoItem(
        id='test-todo-1',
        title='Test Todo',
        description='Test description',
        assignee='Test User',
        priority='Medium',
        status='pending',
        project_key='TEST'
    )
    db_session.add(todo)
    db_session.commit()
    db_session.refresh(todo)
    return todo


@pytest.fixture
def mock_jira_client():
    """Mock Jira client for testing."""
    mock = MagicMock()
    mock.get_projects.return_value = [
        {'key': 'TEST', 'name': 'Test Project', 'id': '1'},
        {'key': 'DEMO', 'name': 'Demo Project', 'id': '2'}
    ]
    mock.get_issue_types.return_value = [
        {'id': '1', 'name': 'Task'},
        {'id': '2', 'name': 'Bug'}
    ]
    mock.get_users.return_value = [
        {'accountId': 'user1', 'displayName': 'User One', 'emailAddress': 'user1@test.com'}
    ]
    mock.get_priorities.return_value = [
        {'id': '1', 'name': 'High'},
        {'id': '2', 'name': 'Medium'},
        {'id': '3', 'name': 'Low'}
    ]
    return mock


@pytest.fixture
def mock_fireflies_client():
    """Mock Fireflies client for testing."""
    mock = MagicMock()
    mock.get_transcripts.return_value = [
        {
            'id': 'transcript-1',
            'title': 'Test Meeting',
            'date': int(datetime.now().timestamp() * 1000),
            'duration': 3600,
            'sentences': []
        }
    ]
    return mock


@pytest.fixture
def sample_meeting_data():
    """Sample meeting data for testing."""
    return {
        'id': 'meeting-1',
        'title': 'Sprint Planning',
        'date': '2025-09-30T10:00:00',
        'duration': 3600,
        'action_items': [
            {'title': 'Review PR', 'description': 'Review pull request #123', 'assignee': 'John Doe'}
        ],
        'key_decisions': ['Use React for frontend'],
        'blockers': [],
        'follow_ups': []
    }


@pytest.fixture
def mock_openai_response():
    """Mock OpenAI API response for testing."""
    return {
        'summary': 'Team discussed project progress and priorities',
        'action_items': [
            {
                'title': 'Complete feature X',
                'description': 'Implement the new feature by Friday',
                'assignee': 'Jane Smith',
                'priority': 'High'
            }
        ],
        'key_decisions': ['Decided to use PostgreSQL'],
        'blockers': ['Waiting for API access'],
        'follow_ups': ['Schedule follow-up meeting next week']
    }
