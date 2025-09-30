"""Tests for todos API endpoints."""

import pytest
from datetime import datetime


def test_get_todos_requires_auth(client):
    """Test that getting todos requires authentication."""
    response = client.get('/api/todos')
    assert response.status_code == 401


def test_get_todos_success(client, mocker, sample_todo):
    """Test successfully getting todos list."""
    mocker.patch('src.routes.todos.auth_required', lambda f: f)

    mock_manager = mocker.patch('src.routes.todos.TodoManager')
    mock_manager.return_value.get_todos.return_value = ([{
        'id': 'test-1',
        'title': 'Test Todo',
        'status': 'pending',
        'priority': 'High'
    }], 1)

    response = client.get('/api/todos')

    assert response.status_code == 200
    data = response.get_json()
    assert 'data' in data
    assert 'total' in data
    assert len(data['data']) == 1


def test_get_todos_with_filters(client, mocker):
    """Test getting todos with filter parameters."""
    mocker.patch('src.routes.todos.auth_required', lambda f: f)

    mock_manager = mocker.patch('src.routes.todos.TodoManager')
    mock_manager.return_value.get_todos.return_value = ([], 0)

    response = client.get('/api/todos?status=pending&priority=High&page=2&per_page=20')

    assert response.status_code == 200
    mock_manager.return_value.get_todos.assert_called_once()


def test_create_todo_requires_auth(client):
    """Test that creating todo requires authentication."""
    response = client.post('/api/todos', json={'title': 'Test'})
    assert response.status_code == 401


def test_create_todo_missing_title(client, mocker):
    """Test creating todo without title."""
    mocker.patch('src.routes.todos.auth_required', lambda f: f)

    response = client.post('/api/todos', json={})

    assert response.status_code == 400
    data = response.get_json()
    assert data['success'] is False


def test_create_todo_success(client, mocker):
    """Test successfully creating a todo."""
    mocker.patch('src.routes.todos.auth_required', lambda f: f)

    mock_manager = mocker.patch('src.routes.todos.TodoManager')
    mock_manager.return_value.create_todo.return_value = {
        'id': 'new-todo-1',
        'title': 'New Todo',
        'status': 'pending'
    }

    response = client.post('/api/todos', json={
        'title': 'New Todo',
        'description': 'Test description',
        'priority': 'Medium'
    })

    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert data['todo']['title'] == 'New Todo'


def test_get_todo_by_id(client, mocker):
    """Test getting a single todo by ID."""
    mocker.patch('src.routes.todos.auth_required', lambda f: f)

    mock_manager = mocker.patch('src.routes.todos.TodoManager')
    mock_manager.return_value.get_todo.return_value = {
        'id': 'test-1',
        'title': 'Test Todo'
    }

    response = client.get('/api/todos/test-1')

    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert data['todo']['id'] == 'test-1'


def test_get_todo_not_found(client, mocker):
    """Test getting non-existent todo."""
    mocker.patch('src.routes.todos.auth_required', lambda f: f)

    mock_manager = mocker.patch('src.routes.todos.TodoManager')
    mock_manager.return_value.get_todo.return_value = None

    response = client.get('/api/todos/nonexistent')

    assert response.status_code == 404


def test_update_todo(client, mocker):
    """Test updating a todo."""
    mocker.patch('src.routes.todos.auth_required', lambda f: f)

    mock_manager = mocker.patch('src.routes.todos.TodoManager')
    mock_manager.return_value.update_todo.return_value = {
        'id': 'test-1',
        'title': 'Updated Todo',
        'status': 'in-progress'
    }

    response = client.put('/api/todos/test-1', json={
        'title': 'Updated Todo',
        'status': 'in-progress'
    })

    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert data['todo']['status'] == 'in-progress'


def test_update_todo_not_found(client, mocker):
    """Test updating non-existent todo."""
    mocker.patch('src.routes.todos.auth_required', lambda f: f)

    mock_manager = mocker.patch('src.routes.todos.TodoManager')
    mock_manager.return_value.update_todo.return_value = None

    response = client.put('/api/todos/nonexistent', json={'title': 'Test'})

    assert response.status_code == 404


def test_delete_todo(client, mocker):
    """Test deleting a todo."""
    mocker.patch('src.routes.todos.auth_required', lambda f: f)

    mock_manager = mocker.patch('src.routes.todos.TodoManager')
    mock_manager.return_value.delete_todo.return_value = True

    response = client.delete('/api/todos/test-1')

    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True


def test_delete_todo_not_found(client, mocker):
    """Test deleting non-existent todo."""
    mocker.patch('src.routes.todos.auth_required', lambda f: f)

    mock_manager = mocker.patch('src.routes.todos.TodoManager')
    mock_manager.return_value.delete_todo.return_value = False

    response = client.delete('/api/todos/nonexistent')

    assert response.status_code == 404


def test_bulk_update_todos(client, mocker):
    """Test bulk updating todos."""
    mocker.patch('src.routes.todos.auth_required', lambda f: f)

    mock_manager = mocker.patch('src.routes.todos.TodoManager')
    mock_manager.return_value.bulk_update_todos.return_value = 3

    response = client.put('/api/todos/bulk', json={
        'ids': ['todo-1', 'todo-2', 'todo-3'],
        'updates': {'status': 'done'}
    })

    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert data['updated_count'] == 3


def test_get_todo_stats(client, mocker):
    """Test getting todo statistics."""
    mocker.patch('src.routes.todos.auth_required', lambda f: f)

    mock_manager = mocker.patch('src.routes.todos.TodoManager')
    mock_manager.return_value.get_stats.return_value = {
        'total': 10,
        'by_status': {'pending': 5, 'done': 5},
        'by_priority': {'High': 3, 'Medium': 7}
    }

    response = client.get('/api/todos/stats')

    assert response.status_code == 200
    data = response.get_json()
    assert data['stats']['total'] == 10
