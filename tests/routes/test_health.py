"""Tests for health check endpoints."""

import pytest
from datetime import datetime


def test_health_endpoint(client):
    """Test basic health check endpoint."""
    response = client.get('/api/health')

    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'healthy'
    assert 'timestamp' in data


def test_health_jira_endpoint(client, mocker):
    """Test Jira health check endpoint."""
    # Mock Jira client
    mock_jira = mocker.patch('src.routes.health.JiraMCPClient')
    mock_instance = mock_jira.return_value.__aenter__.return_value
    mock_instance.get_projects.return_value = [{'key': 'TEST'}]

    response = client.get('/api/health/jira')

    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'healthy'
    assert data['jira_configured'] is True


def test_health_jira_endpoint_unconfigured(client, mocker):
    """Test Jira health check when not configured."""
    # Mock settings without Jira config
    mocker.patch('src.routes.health.settings.jira.url', None)

    response = client.get('/api/health/jira')

    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'healthy'
    assert data['jira_configured'] is False


def test_health_jira_endpoint_connection_error(client, mocker):
    """Test Jira health check with connection error."""
    mock_jira = mocker.patch('src.routes.health.JiraMCPClient')
    mock_instance = mock_jira.return_value.__aenter__.return_value
    mock_instance.get_projects.side_effect = Exception('Connection failed')

    response = client.get('/api/health/jira')

    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'unhealthy'
    assert 'error' in data
