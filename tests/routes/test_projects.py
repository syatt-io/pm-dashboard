"""Tests for project management routes."""
import pytest
from unittest.mock import patch, MagicMock, ANY
from flask import Flask
from datetime import datetime
from src.routes.projects import projects_bp, init_projects_routes


@pytest.fixture
def app():
    """Create test Flask app."""
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'test-secret-key'
    app.register_blueprint(projects_bp)
    app.config['TESTING'] = True

    # Mock auth service for authenticated routes
    mock_auth_service = MagicMock()
    mock_user = MagicMock()
    mock_user.id = 123
    mock_user.email = 'test@example.com'
    mock_auth_service.get_current_user.return_value = mock_user
    app.auth_service = mock_auth_service

    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def mock_user():
    """Create mock authenticated user."""
    user = MagicMock()
    user.id = 123
    user.email = 'test@example.com'
    return user


@pytest.fixture
def mock_notifier():
    """Create mock notifier."""
    notifier = MagicMock()
    return notifier


@pytest.fixture
def auth_headers():
    """Create authorization headers for authenticated requests."""
    return {'Authorization': 'Bearer test-token-123'}


class TestWatchedProjects:
    """Test watched projects routes."""

    @patch('src.routes.projects.session_scope')
    def test_get_watched_projects_success(self, mock_session, client, auth_headers):
        """Test getting watched projects list."""
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db

        mock_wp1 = MagicMock()
        mock_wp1.project_key = 'PROJ1'
        mock_wp2 = MagicMock()
        mock_wp2.project_key = 'PROJ2'

        mock_db.query().filter_by().order_by().all.return_value = [mock_wp1, mock_wp2]

        response = client.get('/api/watched-projects', headers=auth_headers)

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'PROJ1' in data['watched_projects']
        assert 'PROJ2' in data['watched_projects']

    @patch('src.routes.projects.session_scope')
    def test_watch_project_new(self, mock_session, client, auth_headers):
        """Test watching a new project."""
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db
        mock_db.query().filter_by().first.return_value = None  # Not already watching

        response = client.post('/api/watched-projects/PROJ1', headers=auth_headers)

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'watching' in data['message'].lower()
        mock_db.add.assert_called_once()

    @patch('src.routes.projects.session_scope')
    def test_watch_project_already_watching(self, mock_session, client, auth_headers):
        """Test watching already watched project."""
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db
        mock_db.query().filter_by().first.return_value = MagicMock()  # Already watching

        response = client.post('/api/watched-projects/PROJ1', headers=auth_headers)

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'already' in data['message'].lower()

    @patch('src.routes.projects.session_scope')
    def test_unwatch_project_success(self, mock_session, client, auth_headers):
        """Test unwatching a project."""
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db
        mock_watched = MagicMock()
        mock_db.query().filter_by().first.return_value = mock_watched

        response = client.delete('/api/watched-projects/PROJ1', headers=auth_headers)

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'stopped' in data['message'].lower()
        mock_db.delete.assert_called_once_with(mock_watched)

    @patch('src.routes.projects.session_scope')
    def test_unwatch_project_not_found(self, mock_session, client, auth_headers):
        """Test unwatching project not in list."""
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db
        mock_db.query().filter_by().first.return_value = None

        response = client.delete('/api/watched-projects/PROJ1', headers=auth_headers)

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is False
        assert 'not in' in data['message'].lower()


class TestMyProjects:
    """Test my projects routes."""

    @patch('src.routes.projects.session_scope')
    def test_get_user_settings_success(self, mock_session, client):
        """Test getting user project settings."""
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db

        mock_pref = MagicMock()
        mock_pref.email = 'test@example.com'
        mock_pref.slack_username = 'testuser'
        mock_pref.notification_cadence = 'daily'
        mock_pref.selected_projects = ['PROJ1', 'PROJ2']
        mock_pref.last_notification_sent = None

        mock_db.query().filter_by().first.return_value = mock_pref

        with client.session_transaction() as sess:
            sess['user_email'] = 'test@example.com'

        response = client.get('/api/my-projects/user/test@example.com')

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['user_settings']['email'] == 'test@example.com'
        assert data['user_settings']['slack_username'] == 'testuser'

    @patch('src.routes.projects.session_scope')
    def test_get_user_settings_not_found(self, mock_session, client):
        """Test getting settings for non-existent user."""
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db
        mock_db.query().filter_by().first.return_value = None

        response = client.get('/api/my-projects/user/notfound@example.com')

        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] is False

    @patch('src.routes.projects.session_scope')
    def test_save_user_settings_new_user(self, mock_session, client):
        """Test saving settings for new user."""
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db
        mock_db.query().filter_by().first.return_value = None  # New user

        response = client.post('/api/my-projects/user', json={
            'email': 'newuser@example.com',
            'slack_username': 'newuser',
            'notification_cadence': 'weekly',
            'selected_projects': ['PROJ1']
        })

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        mock_db.add.assert_called_once()

    @patch('src.routes.projects.session_scope')
    def test_save_user_settings_existing_user(self, mock_session, client):
        """Test updating settings for existing user."""
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db

        mock_pref = MagicMock()
        mock_db.query().filter_by().first.return_value = mock_pref

        response = client.post('/api/my-projects/user', json={
            'email': 'existing@example.com',
            'slack_username': 'updated_user',
            'notification_cadence': 'daily'
        })

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert mock_pref.slack_username == 'updated_user'

    @patch('src.routes.projects.session_scope')
    def test_save_user_settings_missing_email(self, mock_session, client):
        """Test saving settings without email."""
        response = client.post('/api/my-projects/user', json={
            'slack_username': 'testuser'
        })

        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'required' in data['error'].lower()

    @patch('src.routes.projects.asyncio.run')
    def test_send_test_notification_success(self, mock_async, client, mock_notifier):
        """Test sending test notification."""
        init_projects_routes(mock_notifier)

        response = client.post('/api/my-projects/test-notification', json={
            'email': 'test@example.com'
        })

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        mock_async.assert_called_once()

    def test_send_test_notification_no_email(self, client):
        """Test sending test notification without email."""
        response = client.post('/api/my-projects/test-notification', json={})

        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False

    @patch('src.routes.projects.asyncio.run')
    @patch('src.services.project_monitor.ProjectMonitor')
    def test_trigger_project_poll_success(self, mock_monitor_class, mock_async, client):
        """Test triggering project poll."""
        mock_monitor = MagicMock()
        mock_monitor_class.return_value = mock_monitor

        response = client.post('/api/my-projects/poll-changes')

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        mock_async.assert_called_once()

    @patch('src.routes.projects.asyncio.run')
    @patch('src.services.project_monitor.ProjectMonitor')
    def test_get_user_changes_success(self, mock_monitor_class, mock_async, client):
        """Test getting user project changes."""
        mock_monitor = MagicMock()
        mock_monitor_class.return_value = mock_monitor
        mock_async.return_value = [
            {'project': 'PROJ1', 'change': 'New issue'},
            {'project': 'PROJ2', 'change': 'Issue closed'}
        ]

        response = client.get('/api/my-projects/changes/test@example.com?days=7')

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['count'] == 2
        assert len(data['changes']) == 2

    @patch('src.routes.projects.asyncio.run')
    @patch('src.services.project_notifications.ProjectNotificationService')
    def test_send_project_notification_success(self, mock_service_class, mock_async, client):
        """Test sending project notification to user."""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_async.return_value = True

        response = client.post('/api/my-projects/send-notification/test@example.com')

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'sent' in data['message'].lower()

    @patch('src.routes.projects.asyncio.run')
    @patch('src.services.project_notifications.ProjectNotificationService')
    def test_send_project_notification_no_changes(self, mock_service_class, mock_async, client):
        """Test sending notification when no changes."""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_async.return_value = False

        response = client.post('/api/my-projects/send-notification/test@example.com')

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is False

    @patch('src.routes.projects.asyncio.run')
    @patch('src.services.project_notifications.ProjectNotificationService')
    def test_send_daily_notifications_success(self, mock_service_class, mock_async, client):
        """Test sending daily notifications to all users."""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        response = client.post('/api/my-projects/send-daily-notifications')

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        mock_async.assert_called_once()
