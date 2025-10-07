"""Tests for authentication and OAuth routes."""
import pytest
from unittest.mock import patch, MagicMock, Mock
from flask import Flask
from src.routes.auth import auth_bp
import os


@pytest.fixture
def app():
    """Create test Flask app."""
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'test-secret-key'
    app.config['TESTING'] = True

    # Set required environment variables for OAuth
    os.environ['GOOGLE_CLIENT_ID'] = 'test-google-client-id'
    os.environ['GOOGLE_CLIENT_SECRET'] = 'test-google-client-secret'
    os.environ['GOOGLE_WORKSPACE_REDIRECT_URI'] = 'http://localhost:4000/api/auth/google/workspace/callback'
    os.environ['SLACK_CLIENT_ID'] = 'test-slack-client-id'
    os.environ['SLACK_CLIENT_SECRET'] = 'test-slack-client-secret'
    os.environ['SLACK_REDIRECT_URI'] = 'http://localhost:4000/api/auth/slack/callback'
    os.environ['WEB_BASE_URL'] = 'http://localhost:4000'

    # Mock auth service
    mock_auth_service = MagicMock()
    mock_user = MagicMock()
    mock_user.id = 123
    mock_user.email = 'test@syatt.io'
    mock_user.role = 'user'
    mock_user.is_admin.return_value = False
    mock_user.is_active = True
    mock_user.to_dict.return_value = {
        'id': 123,
        'email': 'test@syatt.io',
        'role': 'user',
        'is_active': True
    }
    mock_auth_service.get_current_user.return_value = mock_user
    app.auth_service = mock_auth_service

    app.register_blueprint(auth_bp)

    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def auth_headers():
    """Auth headers for requests."""
    return {'Authorization': 'Bearer test-token-123'}


@pytest.fixture
def admin_user(app):
    """Create admin user mock."""
    mock_admin = MagicMock()
    mock_admin.id = 1
    mock_admin.email = 'admin@syatt.io'
    mock_admin.role = 'admin'
    mock_admin.is_admin.return_value = True
    mock_admin.is_active = True
    mock_admin.to_dict.return_value = {
        'id': 1,
        'email': 'admin@syatt.io',
        'role': 'admin',
        'is_active': True
    }
    app.auth_service.get_current_user.return_value = mock_admin
    return mock_admin


class TestGoogleLogin:
    """Test Google OAuth login."""

    @patch('src.routes.auth.auth_service')
    def test_google_login_success(self, mock_auth_svc, client):
        """Test successful Google OAuth login."""
        mock_auth_svc.authenticate_with_google.return_value = {
            'token': 'test-jwt-token',
            'user': {
                'id': 123,
                'email': 'test@syatt.io',
                'role': 'user'
            }
        }

        response = client.post('/api/auth/google',
                              json={'credential': 'google-oauth-token-12345'})

        assert response.status_code == 200
        data = response.get_json()
        assert 'token' in data
        assert 'user' in data
        assert data['user']['email'] == 'test@syatt.io'

    def test_google_login_missing_credential(self, client):
        """Test Google login without credential."""
        response = client.post('/api/auth/google', json={})

        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert 'credential' in data['error'].lower()


class TestUserAuthentication:
    """Test user authentication endpoints."""

    def test_get_current_user_success(self, client, auth_headers):
        """Test getting current authenticated user."""
        response = client.get('/api/auth/user', headers=auth_headers)

        assert response.status_code == 200
        data = response.get_json()
        assert data['email'] == 'test@syatt.io'
        assert data['id'] == 123

    def test_logout_success(self, client, auth_headers):
        """Test logout endpoint."""
        response = client.post('/api/auth/logout', headers=auth_headers)

        assert response.status_code == 200
        data = response.get_json()
        assert 'message' in data

    @patch('src.routes.auth.auth_service')
    def test_refresh_token_success(self, mock_auth_svc, client):
        """Test refreshing JWT token."""
        mock_auth_svc.refresh_token.return_value = {
            'token': 'new-jwt-token-12345'
        }

        response = client.post('/api/auth/refresh',
                              headers={'Authorization': 'Bearer old-token'})

        assert response.status_code == 200
        data = response.get_json()
        assert 'token' in data


class TestGoogleWorkspaceOAuth:
    """Test Google Workspace OAuth flow."""

    def test_google_workspace_authorize_success(self, client, auth_headers):
        """Test initiating Google Workspace OAuth flow."""
        response = client.get('/api/auth/google/workspace/authorize',
                             headers=auth_headers)

        assert response.status_code == 302  # Redirect to Google
        assert 'Location' in response.headers
        assert 'accounts.google.com' in response.headers['Location']
        assert 'scope' in response.headers['Location']

    @patch.dict(os.environ, {'GOOGLE_CLIENT_SECRET': ''})
    def test_google_workspace_authorize_missing_config(self, client, auth_headers):
        """Test Google Workspace OAuth with missing configuration."""
        response = client.get('/api/auth/google/workspace/authorize',
                             headers=auth_headers)

        assert response.status_code == 500
        data = response.get_json()
        assert 'not configured' in data['error'].lower()

    @patch('src.routes.auth.requests.post')
    @patch('src.routes.auth.session_scope')
    def test_google_workspace_callback_success(self, mock_session, mock_requests, client):
        """Test Google Workspace OAuth callback."""
        # Mock token exchange
        mock_token_response = MagicMock()
        mock_token_response.status_code = 200
        mock_token_response.json.return_value = {
            'access_token': 'google-access-token',
            'refresh_token': 'google-refresh-token',
            'expires_in': 3600
        }
        mock_requests.return_value = mock_token_response

        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db
        mock_user = MagicMock()
        mock_user.id = 123
        mock_db.query.return_value.filter_by.return_value.first.return_value = mock_user

        response = client.get('/api/auth/google/workspace/callback?code=auth-code-123&state=test-state')

        assert response.status_code == 302  # Redirect to frontend
        assert 'Location' in response.headers

    def test_google_workspace_callback_missing_code(self, client):
        """Test Google Workspace callback without authorization code."""
        response = client.get('/api/auth/google/workspace/callback')

        assert response.status_code == 302  # Redirect with error
        assert 'error' in response.headers['Location']


class TestSlackOAuth:
    """Test Slack OAuth flow."""

    def test_slack_authorize_success(self, client, auth_headers):
        """Test initiating Slack OAuth flow."""
        response = client.get('/api/auth/slack/authorize',
                             headers=auth_headers)

        assert response.status_code == 302  # Redirect to Slack
        assert 'Location' in response.headers
        assert 'slack.com/oauth' in response.headers['Location']
        assert 'client_id' in response.headers['Location']

    @patch.dict(os.environ, {'SLACK_CLIENT_SECRET': ''})
    def test_slack_authorize_missing_config(self, client, auth_headers):
        """Test Slack OAuth with missing configuration."""
        response = client.get('/api/auth/slack/authorize',
                             headers=auth_headers)

        assert response.status_code == 500
        data = response.get_json()
        assert 'not configured' in data['error'].lower()

    @patch('src.routes.auth.requests.post')
    @patch('src.routes.auth.session_scope')
    def test_slack_callback_success(self, mock_session, mock_requests, client):
        """Test Slack OAuth callback."""
        # Mock token exchange
        mock_token_response = MagicMock()
        mock_token_response.status_code = 200
        mock_token_response.json.return_value = {
            'ok': True,
            'access_token': 'slack-user-token',
            'authed_user': {
                'id': 'U12345',
                'access_token': 'slack-user-token'
            }
        }
        mock_requests.return_value = mock_token_response

        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db
        mock_user = MagicMock()
        mock_user.id = 123
        mock_db.query.return_value.filter_by.return_value.first.return_value = mock_user

        response = client.get('/api/auth/slack/callback?code=slack-auth-code-123&state=test-state')

        assert response.status_code == 302  # Redirect to frontend
        assert 'Location' in response.headers

    def test_slack_callback_missing_code(self, client):
        """Test Slack callback without authorization code."""
        response = client.get('/api/auth/slack/callback')

        assert response.status_code == 302  # Redirect with error
        assert 'error' in response.headers['Location']


class TestAdminEndpoints:
    """Test admin-only endpoints."""

    @patch('src.routes.auth.session_scope')
    def test_list_users_as_admin(self, mock_session, client, auth_headers, admin_user):
        """Test listing users as admin."""
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db

        mock_users = [
            MagicMock(id=1, email='admin@syatt.io', role='admin', is_active=True),
            MagicMock(id=2, email='user@syatt.io', role='user', is_active=True)
        ]
        for user in mock_users:
            user.to_dict.return_value = {
                'id': user.id,
                'email': user.email,
                'role': user.role,
                'is_active': user.is_active
            }
        mock_db.query.return_value.all.return_value = mock_users

        response = client.get('/api/auth/users', headers=auth_headers)

        assert response.status_code == 200
        data = response.get_json()
        assert 'users' in data
        assert len(data['users']) == 2

    def test_list_users_as_non_admin(self, client, auth_headers):
        """Test listing users as non-admin user."""
        response = client.get('/api/auth/users', headers=auth_headers)

        assert response.status_code == 403
        data = response.get_json()
        assert 'forbidden' in data['error'].lower() or 'admin' in data['error'].lower()

    @patch('src.routes.auth.session_scope')
    def test_update_user_role_as_admin(self, mock_session, client, auth_headers, admin_user):
        """Test updating user role as admin."""
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db

        mock_target_user = MagicMock()
        mock_target_user.id = 2
        mock_target_user.role = 'user'
        mock_db.query.return_value.filter_by.return_value.first.return_value = mock_target_user

        response = client.put('/api/auth/users/2/role',
                             json={'role': 'admin'},
                             headers=auth_headers)

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert mock_target_user.role == 'admin'

    @patch('src.routes.auth.session_scope')
    def test_update_user_status_as_admin(self, mock_session, client, auth_headers, admin_user):
        """Test updating user status as admin."""
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db

        mock_target_user = MagicMock()
        mock_target_user.id = 2
        mock_target_user.is_active = True
        mock_db.query.return_value.filter_by.return_value.first.return_value = mock_target_user

        response = client.put('/api/auth/users/2/status',
                             json={'is_active': False},
                             headers=auth_headers)

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert mock_target_user.is_active is False


class TestOAuthErrorHandling:
    """Test OAuth error handling."""

    @patch('src.routes.auth.requests.post')
    def test_google_workspace_callback_token_error(self, mock_requests, client):
        """Test Google Workspace callback when token exchange fails."""
        mock_token_response = MagicMock()
        mock_token_response.status_code = 400
        mock_token_response.json.return_value = {'error': 'invalid_grant'}
        mock_requests.return_value = mock_token_response

        response = client.get('/api/auth/google/workspace/callback?code=invalid-code&state=test-state')

        assert response.status_code == 302  # Redirect with error
        assert 'error' in response.headers['Location']

    @patch('src.routes.auth.requests.post')
    def test_slack_callback_token_error(self, mock_requests, client):
        """Test Slack callback when token exchange fails."""
        mock_token_response = MagicMock()
        mock_token_response.status_code = 200
        mock_token_response.json.return_value = {
            'ok': False,
            'error': 'invalid_code'
        }
        mock_requests.return_value = mock_token_response

        response = client.get('/api/auth/slack/callback?code=invalid-code&state=test-state')

        assert response.status_code == 302  # Redirect with error
        assert 'error' in response.headers['Location']
