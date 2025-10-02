"""Tests for user settings routes."""
import pytest
from unittest.mock import patch, MagicMock
from flask import Flask
from src.routes.user import user_bp


@pytest.fixture
def app():
    """Create test Flask app."""
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'test-secret-key'
    app.register_blueprint(user_bp)
    app.config['TESTING'] = True

    # Mock auth service
    mock_auth_service = MagicMock()
    mock_user = MagicMock()
    mock_user.id = 123
    mock_user.email = 'test@example.com'
    mock_user.has_fireflies_api_key.return_value = False
    mock_user.validate_fireflies_api_key.return_value = False
    mock_user.to_dict.return_value = {'id': 123, 'email': 'test@example.com'}
    mock_auth_service.get_current_user.return_value = mock_user
    app.auth_service = mock_auth_service

    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def auth_headers():
    """Auth headers for requests."""
    return {'Authorization': 'Bearer test-token-123'}


class TestUserSettings:
    """Test user settings routes."""

    def test_get_user_settings_success(self, client, auth_headers):
        """Test getting user settings."""
        response = client.get('/api/user/settings', headers=auth_headers)

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'data' in data
        assert 'user' in data['data']
        assert 'settings' in data['data']

    @patch('src.routes.user.session_scope')
    def test_save_fireflies_key_success(self, mock_session, client, auth_headers):
        """Test saving Fireflies API key."""
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db

        mock_user = MagicMock()
        mock_user.id = 123
        mock_db.merge.return_value = mock_user

        response = client.post('/api/user/fireflies-key',
                              json={'api_key': 'test-fireflies-key-12345'},
                              headers=auth_headers)

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'saved successfully' in data['message']

    def test_save_fireflies_key_missing(self, client, auth_headers):
        """Test saving without API key."""
        response = client.post('/api/user/fireflies-key',
                              json={},
                              headers=auth_headers)

        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'required' in data['error'].lower()

    @patch('src.routes.user.session_scope')
    def test_delete_fireflies_key_success(self, mock_session, client, auth_headers):
        """Test deleting Fireflies API key."""
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db

        mock_user = MagicMock()
        mock_user.id = 123
        mock_db.merge.return_value = mock_user

        response = client.delete('/api/user/fireflies-key', headers=auth_headers)

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'deleted successfully' in data['message']

    def test_validate_fireflies_key_valid(self, client, auth_headers):
        """Test validating valid Fireflies API key."""
        response = client.post('/api/user/fireflies-key/validate',
                              json={'api_key': 'test-fireflies-api-key-12345'},
                              headers=auth_headers)

        assert response.status_code == 200
        data = response.get_json()
        assert 'valid' in data
        assert data['valid'] is True

    def test_validate_fireflies_key_invalid(self, client, auth_headers):
        """Test validating invalid Fireflies API key."""
        response = client.post('/api/user/fireflies-key/validate',
                              json={'api_key': 'short'},
                              headers=auth_headers)

        assert response.status_code == 200
        data = response.get_json()
        assert data['valid'] is False

    def test_validate_fireflies_key_missing(self, client, auth_headers):
        """Test validating without API key."""
        response = client.post('/api/user/fireflies-key/validate',
                              json={},
                              headers=auth_headers)

        assert response.status_code == 400
        data = response.get_json()
        assert data['valid'] is False
        assert 'required' in data['error'].lower()
