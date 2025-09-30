"""Tests for learnings API endpoints."""

import pytest
from unittest.mock import Mock, patch


def test_get_learnings_requires_auth(client):
    """Test that getting learnings requires authentication."""
    response = client.get('/api/learnings')
    assert response.status_code == 401


def test_get_learnings_success(client, mocker, mock_user):
    """Test successfully getting learnings list."""
    # Mock auth
    mocker.patch('src.routes.learnings.auth_required', lambda f: f)

    # Mock LearningManager
    mock_manager = mocker.patch('src.routes.learnings.LearningManager')
    mock_learning = Mock()
    mock_learning.to_dict.return_value = {
        'id': 1,
        'content': 'Test learning',
        'category': 'technical'
    }
    mock_manager.return_value.get_learnings.return_value = [mock_learning]

    response = client.get('/api/learnings')

    assert response.status_code == 200
    data = response.get_json()
    assert 'data' in data
    assert 'total' in data
    assert len(data['data']) == 1
    assert data['data'][0]['content'] == 'Test learning'


def test_get_learnings_with_pagination(client, mocker):
    """Test getting learnings with pagination parameters."""
    mocker.patch('src.routes.learnings.auth_required', lambda f: f)

    mock_manager = mocker.patch('src.routes.learnings.LearningManager')
    mock_manager.return_value.get_learnings.return_value = []

    response = client.get('/api/learnings?limit=10&offset=20&category=technical')

    assert response.status_code == 200
    mock_manager.return_value.get_learnings.assert_called_once_with(
        limit=10,
        offset=20,
        category='technical'
    )


def test_create_learning_requires_auth(client):
    """Test that creating learning requires authentication."""
    response = client.post('/api/learnings', json={'content': 'Test'})
    assert response.status_code == 401


def test_create_learning_missing_content(client, mocker, mock_user):
    """Test creating learning without content."""
    mocker.patch('src.routes.learnings.auth_required', lambda f: f)

    response = client.post('/api/learnings', json={})

    assert response.status_code == 400
    data = response.get_json()
    assert data['success'] is False
    assert 'Content is required' in data['error']


def test_create_learning_success(client, mocker, mock_user):
    """Test successfully creating a learning."""
    mocker.patch('src.routes.learnings.auth_required', lambda f: f)

    mock_manager = mocker.patch('src.routes.learnings.LearningManager')
    mock_learning = Mock()
    mock_learning.to_dict.return_value = {
        'id': 1,
        'content': 'New learning',
        'category': 'technical'
    }
    mock_manager.return_value.create_learning.return_value = mock_learning

    response = client.post('/api/learnings', json={
        'content': 'New learning',
        'category': 'technical'
    })

    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert data['learning']['content'] == 'New learning'


def test_get_learning_by_id(client, mocker):
    """Test getting a single learning by ID."""
    mocker.patch('src.routes.learnings.auth_required', lambda f: f)

    mock_manager = mocker.patch('src.routes.learnings.LearningManager')
    mock_learning = Mock()
    mock_learning.to_dict.return_value = {'id': 1, 'content': 'Test'}
    mock_manager.return_value.get_learning.return_value = mock_learning

    response = client.get('/api/learnings/1')

    assert response.status_code == 200
    data = response.get_json()
    assert data['data']['id'] == 1


def test_get_learning_not_found(client, mocker):
    """Test getting non-existent learning."""
    mocker.patch('src.routes.learnings.auth_required', lambda f: f)

    mock_manager = mocker.patch('src.routes.learnings.LearningManager')
    mock_manager.return_value.get_learning.return_value = None

    response = client.get('/api/learnings/999')

    assert response.status_code == 404
    data = response.get_json()
    assert data['success'] is False


def test_update_learning(client, mocker):
    """Test updating a learning."""
    mocker.patch('src.routes.learnings.auth_required', lambda f: f)

    mock_manager = mocker.patch('src.routes.learnings.LearningManager')
    mock_manager.return_value.update_learning.return_value = True

    response = client.put('/api/learnings/1', json={
        'content': 'Updated content',
        'category': 'process'
    })

    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True


def test_update_learning_not_found(client, mocker):
    """Test updating non-existent learning."""
    mocker.patch('src.routes.learnings.auth_required', lambda f: f)

    mock_manager = mocker.patch('src.routes.learnings.LearningManager')
    mock_manager.return_value.update_learning.return_value = False

    response = client.put('/api/learnings/999', json={'content': 'Test'})

    assert response.status_code == 404


def test_delete_learning(client, mocker):
    """Test deleting (archiving) a learning."""
    mocker.patch('src.routes.learnings.auth_required', lambda f: f)

    mock_manager = mocker.patch('src.routes.learnings.LearningManager')
    mock_manager.return_value.archive_learning.return_value = True

    response = client.delete('/api/learnings/1')

    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True


def test_search_learnings(client, mocker):
    """Test searching learnings."""
    mocker.patch('src.routes.learnings.auth_required', lambda f: f)

    mock_manager = mocker.patch('src.routes.learnings.LearningManager')
    mock_learning = Mock()
    mock_learning.to_dict.return_value = {'id': 1, 'content': 'Found learning'}
    mock_manager.return_value.search_learnings.return_value = [mock_learning]

    response = client.get('/api/learnings/search?q=test')

    assert response.status_code == 200
    data = response.get_json()
    assert len(data['data']) == 1


def test_search_learnings_missing_query(client, mocker):
    """Test search without query parameter."""
    mocker.patch('src.routes.learnings.auth_required', lambda f: f)

    response = client.get('/api/learnings/search')

    assert response.status_code == 400


def test_get_categories(client, mocker):
    """Test getting learning categories."""
    mocker.patch('src.routes.learnings.auth_required', lambda f: f)

    mock_manager = mocker.patch('src.routes.learnings.LearningManager')
    mock_manager.return_value.get_categories.return_value = ['technical', 'process', 'business']

    response = client.get('/api/learnings/categories')

    assert response.status_code == 200
    data = response.get_json()
    assert data['data']['categories'] == ['technical', 'process', 'business']


def test_get_stats(client, mocker):
    """Test getting learning statistics."""
    mocker.patch('src.routes.learnings.auth_required', lambda f: f)

    mock_manager = mocker.patch('src.routes.learnings.LearningManager')
    mock_manager.return_value.get_stats.return_value = {
        'total': 50,
        'by_category': {'technical': 30, 'process': 20}
    }

    response = client.get('/api/learnings/stats')

    assert response.status_code == 200
    data = response.get_json()
    assert data['data']['stats']['total'] == 50
