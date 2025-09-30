"""Tests for authentication endpoints."""

import pytest
from unittest.mock import Mock, patch


def test_google_login_redirect(client, mocker):
    """Test Google OAuth login redirects to Google."""
    mock_flow = mocker.patch('src.routes.auth.Flow')
    mock_flow.from_client_config.return_value.authorization_url.return_value = (
        'https://accounts.google.com/oauth', 'state123'
    )

    response = client.get('/api/auth/google/login')

    assert response.status_code == 302
    assert 'accounts.google.com' in response.location


def test_google_callback_success(client, mocker):
    """Test successful Google OAuth callback."""
    # Mock session
    with client.session_transaction() as sess:
        sess['state'] = 'test-state'

    # Mock OAuth flow
    mock_flow = mocker.patch('src.routes.auth.Flow')
    mock_flow_instance = mock_flow.from_client_config.return_value
    mock_flow_instance.fetch_token.return_value = None
    mock_flow_instance.credentials.token = 'test-token'

    # Mock user info request
    mock_requests = mocker.patch('src.routes.auth.requests')
    mock_requests.get.return_value.json.return_value = {
        'email': 'test@example.com',
        'name': 'Test User'
    }

    # Mock database operations
    mock_session = mocker.patch('src.routes.auth.session_scope')
    mock_db_session = Mock()
    mock_session.return_value.__enter__.return_value = mock_db_session
    mock_db_session.query.return_value.filter.return_value.first.return_value = None

    # Mock JWT creation
    mocker.patch('src.routes.auth.create_access_token', return_value='jwt-token')

    response = client.get('/api/auth/google/callback?state=test-state&code=test-code')

    assert response.status_code == 302


def test_google_callback_state_mismatch(client):
    """Test Google callback with mismatched state."""
    with client.session_transaction() as sess:
        sess['state'] = 'correct-state'

    response = client.get('/api/auth/google/callback?state=wrong-state&code=test-code')

    assert response.status_code == 400


def test_logout(client):
    """Test logout endpoint."""
    response = client.post('/api/auth/logout')

    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True


def test_get_current_user_no_auth(client):
    """Test getting current user without authentication."""
    response = client.get('/api/auth/me')

    assert response.status_code == 401


def test_get_current_user_success(client, mocker, mock_user):
    """Test getting current user with valid auth."""
    mocker.patch('src.routes.auth.auth_required', lambda f: f)

    response = client.get('/api/auth/me')

    assert response.status_code == 200
    data = response.get_json()
    assert 'user' in data


def test_save_fireflies_api_key(client, mocker, mock_user):
    """Test saving Fireflies API key."""
    mocker.patch('src.routes.auth.auth_required', lambda f: f)

    mock_session = mocker.patch('src.routes.auth.session_scope')
    mock_db_session = Mock()
    mock_session.return_value.__enter__.return_value = mock_db_session

    # Mock encryption
    mocker.patch('src.routes.auth.encrypt_api_key', return_value='encrypted-key')

    response = client.post('/api/user/fireflies-key', json={
        'api_key': 'test-fireflies-key'
    })

    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True


def test_validate_fireflies_api_key_invalid(client, mocker):
    """Test validating invalid Fireflies API key."""
    mocker.patch('src.routes.auth.auth_required', lambda f: f)

    # Mock Fireflies client to raise error
    mock_fireflies = mocker.patch('src.routes.auth.FirefliesClient')
    mock_fireflies.return_value.validate_api_key.side_effect = Exception('Invalid key')

    response = client.post('/api/user/fireflies-key/validate', json={
        'api_key': 'invalid-key'
    })

    assert response.status_code == 400
    data = response.get_json()
    assert data['valid'] is False


def test_validate_fireflies_api_key_valid(client, mocker):
    """Test validating valid Fireflies API key."""
    mocker.patch('src.routes.auth.auth_required', lambda f: f)

    # Mock Fireflies client
    mock_fireflies = mocker.patch('src.routes.auth.FirefliesClient')
    mock_fireflies.return_value.validate_api_key.return_value = True

    response = client.post('/api/user/fireflies-key/validate', json={
        'api_key': 'valid-key'
    })

    assert response.status_code == 200
    data = response.get_json()
    assert data['valid'] is True


def test_get_fireflies_api_key(client, mocker, mock_user):
    """Test getting Fireflies API key status."""
    mocker.patch('src.routes.auth.auth_required', lambda f: f)

    mock_session = mocker.patch('src.routes.auth.session_scope')
    mock_db_session = Mock()
    mock_session.return_value.__enter__.return_value = mock_db_session

    mock_user_obj = Mock()
    mock_user_obj.fireflies_api_key = 'encrypted-key'
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_user_obj

    response = client.get('/api/user/fireflies-key')

    assert response.status_code == 200
    data = response.get_json()
    assert data['has_key'] is True


def test_watch_project(client, mocker, mock_user):
    """Test watching a project."""
    mocker.patch('src.routes.auth.auth_required', lambda f: f)

    mock_session = mocker.patch('src.routes.auth.session_scope')
    mock_db_session = Mock()
    mock_session.return_value.__enter__.return_value = mock_db_session
    mock_db_session.query.return_value.filter.return_value.first.return_value = None

    response = client.post('/api/user/watch-project', json={
        'project_key': 'TEST'
    })

    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True


def test_unwatch_project(client, mocker, mock_user):
    """Test unwatching a project."""
    mocker.patch('src.routes.auth.auth_required', lambda f: f)

    mock_session = mocker.patch('src.routes.auth.session_scope')
    mock_db_session = Mock()
    mock_session.return_value.__enter__.return_value = mock_db_session

    mock_watch = Mock()
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_watch

    response = client.delete('/api/user/watch-project/TEST')

    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True


def test_get_watched_projects(client, mocker, mock_user):
    """Test getting user's watched projects."""
    mocker.patch('src.routes.auth.auth_required', lambda f: f)

    mock_session = mocker.patch('src.routes.auth.session_scope')
    mock_db_session = Mock()
    mock_session.return_value.__enter__.return_value = mock_db_session

    mock_watch = Mock()
    mock_watch.project_key = 'TEST'
    mock_db_session.query.return_value.filter.return_value.all.return_value = [mock_watch]

    response = client.get('/api/watched-projects')

    assert response.status_code == 200
    data = response.get_json()
    assert 'watched_projects' in data
    assert 'TEST' in data['watched_projects']
