"""Tests for Jira API endpoints."""

import pytest
from unittest.mock import Mock, patch, AsyncMock


def test_get_jira_projects_success(client, mocker):
    """Test successfully getting Jira projects."""
    # Mock settings
    mocker.patch('src.routes.jira.settings.jira.url', 'https://test.atlassian.net')
    mocker.patch('src.routes.jira.settings.jira.username', 'test@example.com')
    mocker.patch('src.routes.jira.settings.jira.api_token', 'test-token')

    # Mock Jira client
    mock_jira = mocker.patch('src.routes.jira.JiraMCPClient')
    mock_instance = mock_jira.return_value.__aenter__.return_value
    mock_instance.get_projects = AsyncMock(return_value=[
        {'key': 'TEST', 'name': 'Test Project', 'id': '1'},
        {'key': 'DEMO', 'name': 'Demo Project', 'id': '2'}
    ])

    # Mock database
    mock_engine = mocker.patch('src.routes.jira.get_engine')
    mock_conn = Mock()
    mock_engine.return_value.connect.return_value.__enter__.return_value = mock_conn
    mock_conn.execute.return_value.fetchone.return_value = None

    response = client.get('/api/jira/projects')

    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert 'projects' in data['data']
    assert len(data['data']['projects']) == 2
    assert data['data']['projects'][0]['key'] == 'TEST'


def test_get_jira_projects_not_configured(client, mocker):
    """Test Jira projects when credentials not configured."""
    mocker.patch('src.routes.jira.settings.jira.url', None)

    response = client.get('/api/jira/projects')

    assert response.status_code == 500
    data = response.get_json()
    assert data['success'] is False
    assert 'not configured' in data['error']


def test_get_jira_projects_with_database_enhancement(client, mocker):
    """Test Jira projects with local database enhancements."""
    mocker.patch('src.routes.jira.settings.jira.url', 'https://test.atlassian.net')
    mocker.patch('src.routes.jira.settings.jira.username', 'test@example.com')
    mocker.patch('src.routes.jira.settings.jira.api_token', 'test-token')

    mock_jira = mocker.patch('src.routes.jira.JiraMCPClient')
    mock_instance = mock_jira.return_value.__aenter__.return_value
    mock_instance.get_projects = AsyncMock(return_value=[
        {'key': 'TEST', 'name': 'Test Project'}
    ])

    # Mock database with project data
    # New query returns: is_active, project_work_type, total_hours, cumulative_hours,
    # slack_channel, weekly_meeting_day, retainer_hours, forecasted_hours, actual_monthly_hours
    mock_engine = mocker.patch('src.routes.jira.get_engine')
    mock_conn = Mock()
    mock_engine.return_value.connect.return_value.__enter__.return_value = mock_conn
    mock_result = Mock()
    mock_result.__getitem__ = lambda self, idx: [True, 'project-based', 120.0, 155.0, '#test-channel', 'Monday', 0, 40.0, 35.0][idx]
    mock_conn.execute.return_value.fetchone.return_value = mock_result

    response = client.get('/api/jira/projects')

    assert response.status_code == 200
    data = response.get_json()
    project = data['data']['projects'][0]
    assert project['forecasted_hours_month'] == 40.0
    assert project['is_active'] is True
    assert project['slack_channel'] == '#test-channel'


def test_get_issue_types(client, mocker):
    """Test getting Jira issue types."""
    mocker.patch('src.routes.jira.settings.jira.url', 'https://test.atlassian.net')
    mocker.patch('src.routes.jira.settings.jira.username', 'test@example.com')
    mocker.patch('src.routes.jira.settings.jira.api_token', 'test-token')

    mock_jira = mocker.patch('src.routes.jira.JiraMCPClient')
    mock_instance = mock_jira.return_value.__aenter__.return_value
    mock_instance.get_issue_types = AsyncMock(return_value=[
        {'id': '1', 'name': 'Task'},
        {'id': '2', 'name': 'Bug'}
    ])

    response = client.get('/api/jira/issue-types?project=TEST')

    assert response.status_code == 200
    data = response.get_json()
    assert len(data['data']['issue_types']) == 2


def test_get_users(client, mocker):
    """Test getting assignable Jira users."""
    mocker.patch('src.routes.jira.settings.jira.url', 'https://test.atlassian.net')
    mocker.patch('src.routes.jira.settings.jira.username', 'test@example.com')
    mocker.patch('src.routes.jira.settings.jira.api_token', 'test-token')

    mock_jira = mocker.patch('src.routes.jira.JiraMCPClient')
    mock_instance = mock_jira.return_value.__aenter__.return_value
    mock_instance.get_users = AsyncMock(return_value=[
        {'accountId': 'user1', 'displayName': 'John Doe'}
    ])

    response = client.get('/api/jira/users?project=TEST')

    assert response.status_code == 200
    data = response.get_json()
    assert len(data['data']['users']) == 1


def test_search_users(client, mocker):
    """Test searching Jira users."""
    mocker.patch('src.routes.jira.settings.jira.url', 'https://test.atlassian.net')
    mocker.patch('src.routes.jira.settings.jira.username', 'test@example.com')
    mocker.patch('src.routes.jira.settings.jira.api_token', 'test-token')

    mock_jira = mocker.patch('src.routes.jira.JiraMCPClient')
    mock_instance = mock_jira.return_value.__aenter__.return_value
    mock_instance.search_users = AsyncMock(return_value=[
        {'accountId': 'user1', 'displayName': 'John Doe'}
    ])

    response = client.get('/api/jira/users/search?q=john')

    assert response.status_code == 200
    data = response.get_json()
    assert len(data['data']['users']) == 1


def test_search_users_minimum_chars(client, mocker):
    """Test user search requires minimum 3 characters."""
    response = client.get('/api/jira/users/search?q=ab')

    assert response.status_code == 200
    data = response.get_json()
    assert data['data']['users'] == []


def test_get_priorities(client, mocker):
    """Test getting Jira priorities."""
    mocker.patch('src.routes.jira.settings.jira.url', 'https://test.atlassian.net')
    mocker.patch('src.routes.jira.settings.jira.username', 'test@example.com')
    mocker.patch('src.routes.jira.settings.jira.api_token', 'test-token')

    mock_jira = mocker.patch('src.routes.jira.JiraMCPClient')
    mock_instance = mock_jira.return_value.__aenter__.return_value
    mock_instance.get_priorities = AsyncMock(return_value=[
        {'id': '1', 'name': 'High'},
        {'id': '2', 'name': 'Low'}
    ])

    response = client.get('/api/jira/priorities')

    assert response.status_code == 200
    data = response.get_json()
    assert len(data['data']['priorities']) == 2


def test_get_metadata(client, mocker):
    """Test getting comprehensive Jira metadata."""
    mocker.patch('src.routes.jira.settings.jira.url', 'https://test.atlassian.net')
    mocker.patch('src.routes.jira.settings.jira.username', 'test@example.com')
    mocker.patch('src.routes.jira.settings.jira.api_token', 'test-token')

    mock_jira = mocker.patch('src.routes.jira.JiraMCPClient')
    mock_instance = mock_jira.return_value.__aenter__.return_value
    mock_instance.get_project_metadata = AsyncMock(return_value={
        'issue_types': [],
        'priorities': [],
        'users': []
    })

    response = client.get('/api/jira/metadata/TEST')

    assert response.status_code == 200
    data = response.get_json()
    assert 'metadata' in data['data']


def test_update_project(client, mocker):
    """Test updating project data."""
    mock_engine = mocker.patch('src.routes.jira.get_engine')
    mock_conn = Mock()
    mock_engine.return_value.connect.return_value.__enter__.return_value = mock_conn

    # Mock existing project
    mock_result = Mock()
    mock_result.fetchone.return_value = ['TEST', 'Test Project']
    mock_conn.execute.return_value = mock_result

    response = client.put('/api/jira/projects/TEST', json={
        'name': 'Updated Project',
        'is_active': True,
        'forecasted_hours_month': 40,
        'project_work_type': 'ongoing',
        'slack_channel': '#test'
    })

    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True


def test_update_project_creates_new(client, mocker):
    """Test updating creates new project if not exists."""
    mock_engine = mocker.patch('src.routes.jira.get_engine')
    mock_conn = Mock()
    mock_engine.return_value.connect.return_value.__enter__.return_value = mock_conn

    # Mock non-existent project
    mock_result = Mock()
    mock_result.fetchone.return_value = None
    mock_conn.execute.return_value = mock_result

    response = client.put('/api/jira/projects/NEW', json={
        'name': 'New Project',
        'is_active': True
    })

    assert response.status_code == 200


def test_get_project_forecasts_batch_success(client, mocker):
    """Test successfully getting batch forecasts for multiple projects."""
    from datetime import datetime

    mock_engine = mocker.patch('src.routes.jira.get_engine')
    mock_conn = Mock()
    mock_engine.return_value.connect.return_value.__enter__.return_value = mock_conn

    # Mock database results for multiple projects
    current_month = datetime(2025, 10, 1).date()
    mock_conn.execute.return_value = [
        ('PROJ1', current_month, 40.0, 35.5),
        ('PROJ2', current_month, 60.0, 50.0),
    ]

    response = client.post('/api/jira/project-forecasts/batch', json={
        'project_keys': ['PROJ1', 'PROJ2']
    })

    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert 'forecasts' in data['data']
    assert 'PROJ1' in data['data']['forecasts']
    assert 'PROJ2' in data['data']['forecasts']
    # Each project should have 6 months of forecasts
    assert len(data['data']['forecasts']['PROJ1']) == 6
    assert len(data['data']['forecasts']['PROJ2']) == 6


def test_get_project_forecasts_batch_missing_keys(client, mocker):
    """Test batch forecast endpoint requires project_keys."""
    response = client.post('/api/jira/project-forecasts/batch', json={})

    assert response.status_code == 400
    data = response.get_json()
    assert data['success'] is False
    assert 'required' in data['error'].lower()


def test_get_project_forecasts_batch_empty_keys(client, mocker):
    """Test batch forecast endpoint with empty project_keys."""
    response = client.post('/api/jira/project-forecasts/batch', json={
        'project_keys': []
    })

    assert response.status_code == 400
    data = response.get_json()
    assert data['success'] is False
