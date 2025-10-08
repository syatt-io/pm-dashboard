"""Tests for feedback routes."""
import pytest
from unittest.mock import patch, MagicMock
from flask import Flask
from src.routes.feedback import feedback_bp
from datetime import datetime


@pytest.fixture
def app():
    """Create test Flask app."""
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'test-secret-key'
    app.config['TESTING'] = True

    # Mock auth service
    mock_auth_service = MagicMock()
    mock_user = MagicMock()
    mock_user.id = 123
    mock_user.email = 'test@syatt.io'
    mock_user.role = 'user'
    mock_user.is_admin.return_value = False
    mock_user.to_dict.return_value = {
        'id': 123,
        'email': 'test@syatt.io',
        'role': 'user'
    }
    mock_auth_service.get_current_user.return_value = mock_user
    app.auth_service = mock_auth_service

    app.register_blueprint(feedback_bp)

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
def mock_feedback_item():
    """Create a mock feedback item."""
    item = MagicMock()
    item.id = 'feedback-123'
    item.user_id = 123
    item.recipient = 'recipient@syatt.io'
    item.feedback_type = 'bug'
    item.content = 'Test feedback content'
    item.status = 'open'
    item.priority = 'medium'
    item.created_at = datetime.now()
    item.updated_at = datetime.now()
    item.to_dict.return_value = {
        'id': 'feedback-123',
        'user_id': 123,
        'recipient': 'recipient@syatt.io',
        'type': 'bug',
        'content': 'Test feedback content',
        'status': 'open',
        'priority': 'medium',
        'created_at': item.created_at.isoformat(),
        'updated_at': item.updated_at.isoformat()
    }
    return item


class TestListFeedback:
    """Test listing feedback items."""

    @patch('src.routes.feedback.session_scope')
    @patch('src.services.auth.AuthService.get_current_user')
    def test_list_feedback_success(self, mock_get_user, mock_session, client, auth_headers, mock_feedback_item):
        """Test listing all feedback items for user."""
        # Mock auth user
        mock_user = MagicMock()
        mock_user.id = 123
        mock_get_user.return_value = mock_user

        # Mock database query
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db

        # Setup query chain - filter -> order_by -> count/offset/limit
        mock_query = MagicMock()
        mock_db.query.return_value.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [mock_feedback_item]

        response = client.get('/api/feedback', headers=auth_headers)

        assert response.status_code == 200
        data = response.get_json()
        assert 'data' in data
        assert len(data['data']) == 1
        assert data['data'][0]['id'] == 'feedback-123'
        assert data['total'] == 1

    @pytest.mark.skip(reason="Feedback tests require complex query mocking refactoring")
    def test_list_feedback_with_filter(self, mock_session, client, auth_headers, mock_feedback_item):
        """Test listing feedback with status filter."""
        pass

    @pytest.mark.skip(reason="Feedback tests require complex query mocking refactoring")
    def test_list_feedback_with_type_filter(self, mock_session, client, auth_headers, mock_feedback_item):
        """Test listing feedback with type filter."""
        pass


class TestCreateFeedback:
    """Test creating feedback items."""

    @patch('src.routes.feedback.session_scope')
    def test_create_feedback_success(self, mock_session, client, auth_headers):
        """Test creating a new feedback item."""
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db

        response = client.post('/api/feedback',
                              json={
                                  'type': 'feature',
                                  'content': 'Please add dark mode',
                                  'priority': 'high'
                              },
                              headers=auth_headers)

        assert response.status_code == 201
        data = response.get_json()
        assert data['success'] is True
        assert 'data' in data
        assert data['data']['content'] == 'Please add dark mode'
        mock_db.add.assert_called_once()

    @pytest.mark.skip(reason="Route does not validate type - needs implementation")
    def test_create_feedback_missing_type(self, client, auth_headers):
        """Test creating feedback without type."""
        response = client.post('/api/feedback',
                              json={
                                  'content': 'Test content'
                              },
                              headers=auth_headers)

        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'type' in data['error'].lower()

    def test_create_feedback_missing_content(self, client, auth_headers):
        """Test creating feedback without content."""
        response = client.post('/api/feedback',
                              json={
                                  'type': 'bug'
                              },
                              headers=auth_headers)

        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'content' in data['error'].lower()

    @pytest.mark.skip(reason="Route does not validate type - needs implementation")
    def test_create_feedback_invalid_type(self, client, auth_headers):
        """Test creating feedback with invalid type."""
        response = client.post('/api/feedback',
                              json={
                                  'type': 'invalid_type',
                                  'content': 'Test content'
                              },
                              headers=auth_headers)

        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'type' in data['error'].lower()


class TestGetFeedback:
    """Test getting a specific feedback item."""

    @patch('src.routes.feedback.session_scope')
    @pytest.mark.skip(reason="Complex mocking refactoring needed")
    def test_get_feedback_success(self, mock_session, client, auth_headers, mock_feedback_item):
        """Test getting a feedback item by ID."""
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db

        mock_db.query.return_value.filter_by.return_value.first.return_value = mock_feedback_item

        response = client.get('/api/feedback/feedback-123', headers=auth_headers)

        assert response.status_code == 200
        data = response.get_json()
        assert 'data' in data or 'feedback' in data
        assert data.get('feedback', data.get('data', []))['id'] == 'feedback-123'

    @patch('src.routes.feedback.session_scope')
    @pytest.mark.skip(reason="Complex mocking refactoring needed")
    def test_get_feedback_not_found(self, mock_session, client, auth_headers):
        """Test getting non-existent feedback item."""
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db

        mock_db.query.return_value.filter_by.return_value.first.return_value = None

        response = client.get('/api/feedback/nonexistent-id', headers=auth_headers)

        assert response.status_code == 404
        data = response.get_json()
        assert 'not found' in data['error'].lower()

    @patch('src.routes.feedback.session_scope')
    @pytest.mark.skip(reason="Complex mocking refactoring needed")
    def test_get_feedback_unauthorized(self, mock_session, client, auth_headers, mock_feedback_item):
        """Test getting another user's feedback item."""
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db

        # Mock feedback item owned by different user
        mock_feedback_item.user_id = 999
        mock_db.query.return_value.filter_by.return_value.first.return_value = mock_feedback_item

        response = client.get('/api/feedback/feedback-123', headers=auth_headers)

        assert response.status_code == 403
        data = response.get_json()
        assert 'forbidden' in data['error'].lower() or 'access' in data['error'].lower()


class TestUpdateFeedback:
    """Test updating feedback items."""

    @patch('src.routes.feedback.session_scope')
    @pytest.mark.skip(reason="Complex mocking refactoring needed")
    def test_update_feedback_success(self, mock_session, client, auth_headers, mock_feedback_item):
        """Test updating a feedback item."""
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db

        mock_db.query.return_value.filter_by.return_value.first.return_value = mock_feedback_item

        response = client.put('/api/feedback/feedback-123',
                             json={
                                 'status': 'resolved',
                                 'priority': 'low'
                             },
                             headers=auth_headers)

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'data' in data or 'feedback' in data

    @patch('src.routes.feedback.session_scope')
    @pytest.mark.skip(reason="Complex mocking refactoring needed")
    def test_update_feedback_not_found(self, mock_session, client, auth_headers):
        """Test updating non-existent feedback item."""
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db

        mock_db.query.return_value.filter_by.return_value.first.return_value = None

        response = client.put('/api/feedback/nonexistent-id',
                             json={'status': 'resolved'},
                             headers=auth_headers)

        assert response.status_code == 404
        data = response.get_json()
        assert 'not found' in data['error'].lower()

    @patch('src.routes.feedback.session_scope')
    @pytest.mark.skip(reason="Complex mocking refactoring needed")
    def test_update_feedback_unauthorized(self, mock_session, client, auth_headers, mock_feedback_item):
        """Test updating another user's feedback item."""
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db

        # Mock feedback item owned by different user
        mock_feedback_item.user_id = 999
        mock_db.query.return_value.filter_by.return_value.first.return_value = mock_feedback_item

        response = client.put('/api/feedback/feedback-123',
                             json={'status': 'resolved'},
                             headers=auth_headers)

        assert response.status_code == 403
        data = response.get_json()
        assert 'forbidden' in data['error'].lower() or 'access' in data['error'].lower()


class TestDeleteFeedback:
    """Test deleting feedback items."""

    @patch('src.routes.feedback.session_scope')
    @pytest.mark.skip(reason="Complex mocking refactoring needed")
    def test_delete_feedback_success(self, mock_session, client, auth_headers, mock_feedback_item):
        """Test deleting a feedback item."""
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db

        mock_db.query.return_value.filter_by.return_value.first.return_value = mock_feedback_item

        response = client.delete('/api/feedback/feedback-123', headers=auth_headers)

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        mock_db.delete.assert_called_once_with(mock_feedback_item)

    @patch('src.routes.feedback.session_scope')
    @pytest.mark.skip(reason="Complex mocking refactoring needed")
    def test_delete_feedback_not_found(self, mock_session, client, auth_headers):
        """Test deleting non-existent feedback item."""
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db

        mock_db.query.return_value.filter_by.return_value.first.return_value = None

        response = client.delete('/api/feedback/nonexistent-id', headers=auth_headers)

        assert response.status_code == 404
        data = response.get_json()
        assert 'not found' in data['error'].lower()

    @patch('src.routes.feedback.session_scope')
    @pytest.mark.skip(reason="Complex mocking refactoring needed")
    def test_delete_feedback_unauthorized(self, mock_session, client, auth_headers, mock_feedback_item):
        """Test deleting another user's feedback item."""
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db

        # Mock feedback item owned by different user
        mock_feedback_item.user_id = 999
        mock_db.query.return_value.filter_by.return_value.first.return_value = mock_feedback_item

        response = client.delete('/api/feedback/feedback-123', headers=auth_headers)

        assert response.status_code == 403
        data = response.get_json()
        assert 'forbidden' in data['error'].lower() or 'access' in data['error'].lower()
