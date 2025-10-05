"""Tests for scheduler and notification routes."""
import pytest
from unittest.mock import patch, MagicMock
from flask import Flask
from src.routes.scheduler import scheduler_bp


@pytest.fixture
def app():
    """Create test Flask app."""
    app = Flask(__name__)
    app.register_blueprint(scheduler_bp)
    app.config['TESTING'] = True
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


class TestSchedulerManagement:
    """Test scheduler management routes."""

    @patch('src.routes.scheduler.start_scheduler')
    def test_start_scheduler_success(self, mock_start, client):
        """Test starting scheduler."""
        response = client.post('/api/scheduler/start')

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'started' in data['message'].lower()
        mock_start.assert_called_once()

    @patch('src.routes.scheduler.start_scheduler')
    def test_start_scheduler_error(self, mock_start, client):
        """Test start scheduler error handling."""
        mock_start.side_effect = Exception("Scheduler error")

        response = client.post('/api/scheduler/start')

        assert response.status_code == 500
        data = response.get_json()
        assert data['success'] is False
        assert 'error' in data

    @patch('src.routes.scheduler.stop_scheduler')
    def test_stop_scheduler_success(self, mock_stop, client):
        """Test stopping scheduler."""
        response = client.post('/api/scheduler/stop')

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'stopped' in data['message'].lower()
        mock_stop.assert_called_once()

    @patch('src.routes.scheduler.stop_scheduler')
    def test_stop_scheduler_error(self, mock_stop, client):
        """Test stop scheduler error handling."""
        mock_stop.side_effect = Exception("Stop error")

        response = client.post('/api/scheduler/stop')

        assert response.status_code == 500
        data = response.get_json()
        assert data['success'] is False

    @patch('src.routes.scheduler.get_scheduler')
    @patch('src.routes.scheduler.schedule')
    def test_scheduler_status_running(self, mock_schedule, mock_get, client):
        """Test scheduler status when running."""
        mock_scheduler = MagicMock()
        mock_scheduler.running = True
        mock_get.return_value = mock_scheduler
        mock_schedule.jobs = [1, 2, 3]

        response = client.get('/api/scheduler/status')

        assert response.status_code == 200
        data = response.get_json()
        assert data['running'] is True
        assert data['active_jobs'] == 3

    @patch('src.routes.scheduler.get_scheduler')
    def test_scheduler_status_not_running(self, mock_get, client):
        """Test scheduler status when not running."""
        mock_get.return_value = None

        response = client.get('/api/scheduler/status')

        assert response.status_code == 200
        data = response.get_json()
        assert data['running'] is False
        assert data['active_jobs'] == 0

    @patch('src.routes.scheduler.get_scheduler')
    def test_scheduler_status_error(self, mock_get, client):
        """Test scheduler status error handling."""
        mock_get.side_effect = Exception("Status error")

        response = client.get('/api/scheduler/status')

        assert response.status_code == 500
        data = response.get_json()
        assert 'error' in data


class TestNotificationTriggers:
    """Test notification trigger routes."""

    @patch('src.routes.scheduler.asyncio.run')
    @patch('src.routes.scheduler.get_scheduler')
    def test_daily_digest_success(self, mock_get, mock_async, client):
        """Test triggering daily digest."""
        mock_scheduler = MagicMock()
        mock_get.return_value = mock_scheduler

        response = client.post('/api/notifications/daily-digest')

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        mock_async.assert_called_once()

    @patch('src.routes.scheduler.get_scheduler')
    def test_daily_digest_scheduler_not_running(self, mock_get, client):
        """Test daily digest when scheduler not running."""
        mock_get.return_value = None

        response = client.post('/api/notifications/daily-digest')

        assert response.status_code == 503
        data = response.get_json()
        assert 'not running' in data['error'].lower()

    @patch('src.routes.scheduler.asyncio.run')
    @patch('src.routes.scheduler.get_scheduler')
    def test_overdue_reminders_success(self, mock_get, mock_async, client):
        """Test triggering overdue reminders."""
        mock_scheduler = MagicMock()
        mock_get.return_value = mock_scheduler

        response = client.post('/api/notifications/overdue-reminders')

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

    @patch('src.routes.scheduler.asyncio.run')
    @patch('src.routes.scheduler.get_scheduler')
    def test_due_today_reminders_success(self, mock_get, mock_async, client):
        """Test triggering due today reminders."""
        mock_scheduler = MagicMock()
        mock_get.return_value = mock_scheduler

        response = client.post('/api/notifications/due-today')

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

    @patch('src.routes.scheduler.asyncio.run')
    @patch('src.routes.scheduler.get_scheduler')
    def test_custom_notification_success(self, mock_get, mock_async, client):
        """Test sending custom notification."""
        mock_scheduler = MagicMock()
        mock_get.return_value = mock_scheduler

        response = client.post('/api/notifications/custom', json={
            'assignee': 'user@example.com',
            'message': 'Test message',
            'priority': 'high'
        })

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

    @patch('src.routes.scheduler.get_scheduler')
    def test_custom_notification_missing_fields(self, mock_get, client):
        """Test custom notification with missing fields."""
        mock_get.return_value = MagicMock()

        response = client.post('/api/notifications/custom', json={
            'assignee': 'user@example.com'
            # missing message
        })

        assert response.status_code == 400
        data = response.get_json()
        assert 'required' in data['error'].lower()

    @patch('src.routes.scheduler.asyncio.run')
    @patch('src.routes.scheduler.get_scheduler')
    def test_hours_report_success(self, mock_get, mock_async, client):
        """Test triggering hours report."""
        mock_scheduler = MagicMock()
        mock_get.return_value = mock_scheduler

        response = client.post('/api/scheduler/hours-report')

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'hours report' in data['message'].lower()

    @patch('src.routes.scheduler.get_scheduler')
    def test_hours_report_scheduler_not_running(self, mock_get, client):
        """Test hours report when scheduler not running."""
        mock_get.return_value = None

        response = client.post('/api/scheduler/hours-report')

        assert response.status_code == 500
        data = response.get_json()
        assert data['success'] is False
        assert 'not running' in data['error'].lower()

    @patch('src.routes.scheduler.get_scheduler')
    def test_tempo_sync_success(self, mock_get, client):
        """Test triggering Tempo sync."""
        mock_scheduler = MagicMock()
        mock_scheduler.sync_tempo_hours = MagicMock()
        mock_get.return_value = mock_scheduler

        response = client.post('/api/scheduler/tempo-sync')

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'tempo sync' in data['message'].lower()
        mock_scheduler.sync_tempo_hours.assert_called_once()

    @patch('src.routes.scheduler.get_scheduler')
    def test_tempo_sync_scheduler_not_running(self, mock_get, client):
        """Test tempo sync when scheduler not running."""
        mock_get.return_value = None

        response = client.post('/api/scheduler/tempo-sync')

        assert response.status_code == 500
        data = response.get_json()
        assert data['success'] is False
        assert 'not running' in data['error'].lower()
