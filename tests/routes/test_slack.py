"""Tests for Slack integration routes."""
import pytest
from unittest.mock import patch, MagicMock
from flask import Flask
from src.routes.slack import slack_bp, init_slack_routes


@pytest.fixture
def app():
    """Create test Flask app."""
    app = Flask(__name__)
    app.register_blueprint(slack_bp)
    app.config['TESTING'] = True
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def mock_slack_bot():
    """Create mock Slack bot."""
    bot = MagicMock()
    handler = MagicMock()
    bot.get_handler.return_value = handler
    return bot


class TestSlackEvents:
    """Test Slack event handling routes."""

    def test_slack_events_url_verification(self, client):
        """Test Slack URL verification challenge."""
        response = client.post('/slack/events', json={
            'type': 'url_verification',
            'challenge': 'test_challenge_token'
        })

        assert response.status_code == 200
        data = response.get_json()
        assert data['challenge'] == 'test_challenge_token'

    def test_slack_events_not_configured(self, client):
        """Test Slack events when bot not configured."""
        init_slack_routes(None, None)

        response = client.post('/slack/events', json={
            'type': 'event_callback',
            'event': {}
        })

        assert response.status_code == 503
        data = response.get_json()
        assert 'not configured' in data['error'].lower()

    @pytest.mark.skip(reason="Slack bot initialization mocking needs refactoring")
    def test_slack_events_with_bot(self, client, mock_slack_bot):
        """Test Slack events with configured bot."""
        init_slack_routes(mock_slack_bot, "test-signing-secret")
        mock_slack_bot.get_handler().handle.return_value = ('', 200)

        response = client.post('/slack/events', json={
            'type': 'event_callback',
            'event': {}
        })

        assert response.status_code == 200
        mock_slack_bot.get_handler().handle.assert_called_once()

    def test_slack_commands_not_configured(self, client):
        """Test Slack commands when bot not configured."""
        init_slack_routes(None, None)

        response = client.post('/slack/commands', data={
            'command': '/todo',
            'text': 'list'
        })

        assert response.status_code == 503
        data = response.get_json()
        assert 'not configured' in data['error'].lower()

    @pytest.mark.skip(reason="Slack bot initialization mocking needs refactoring")
    def test_slack_commands_with_bot(self, client, mock_slack_bot):
        """Test Slack commands with configured bot."""
        init_slack_routes(mock_slack_bot, "test-signing-secret")
        mock_slack_bot.get_handler().handle.return_value = ('', 200)

        response = client.post('/slack/commands', data={
            'command': '/todo',
            'text': 'list'
        })

        assert response.status_code == 200
        mock_slack_bot.get_handler().handle.assert_called_once()

    def test_slack_interactive_not_configured(self, client):
        """Test Slack interactive when bot not configured."""
        init_slack_routes(None, None)

        response = client.post('/slack/interactive', json={
            'type': 'button_click',
            'actions': []
        })

        assert response.status_code == 503
        data = response.get_json()
        assert 'not configured' in data['error'].lower()

    @pytest.mark.skip(reason="Slack bot initialization mocking needs refactoring")
    def test_slack_interactive_with_bot(self, client, mock_slack_bot):
        """Test Slack interactive with configured bot."""
        init_slack_routes(mock_slack_bot, "test-signing-secret")
        mock_slack_bot.get_handler().handle.return_value = ('', 200)

        response = client.post('/slack/interactive', json={
            'type': 'button_click',
            'actions': []
        })

        assert response.status_code == 200
        mock_slack_bot.get_handler().handle.assert_called_once()


class TestSlackDigest:
    """Test Slack digest trigger routes."""

    @patch('src.routes.slack.asyncio.run')
    @pytest.mark.skip(reason="Slack bot initialization mocking needs refactoring")
    def test_slack_digest_success(self, mock_async, client, mock_slack_bot):
        """Test triggering Slack digest."""
        init_slack_routes(mock_slack_bot, "test-signing-secret")

        response = client.post('/api/slack/digest', json={
            'channel': '#general'
        })

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        mock_async.assert_called_once()

    @patch('src.routes.slack.asyncio.run')
    @pytest.mark.skip(reason="Slack bot initialization mocking needs refactoring")
    def test_slack_digest_no_channel(self, mock_async, client, mock_slack_bot):
        """Test Slack digest without channel."""
        init_slack_routes(mock_slack_bot, "test-signing-secret")

        response = client.post('/api/slack/digest', json={})

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

    def test_slack_digest_not_configured(self, client):
        """Test Slack digest when bot not configured."""
        init_slack_routes(None, None)

        response = client.post('/api/slack/digest', json={})

        assert response.status_code == 503
        data = response.get_json()
        assert 'not configured' in data['error'].lower()

    @patch('src.routes.slack.asyncio.run')
    @pytest.mark.skip(reason="Slack bot initialization mocking needs refactoring")
    def test_slack_digest_error(self, mock_async, client, mock_slack_bot):
        """Test Slack digest error handling."""
        init_slack_routes(mock_slack_bot, "test-signing-secret")
        mock_async.side_effect = Exception("Digest error")

        response = client.post('/api/slack/digest', json={})

        assert response.status_code == 500
        data = response.get_json()
        assert 'error' in data
