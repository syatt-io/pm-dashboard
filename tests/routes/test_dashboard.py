"""Tests for dashboard routes."""

import pytest
from unittest.mock import patch, MagicMock
from flask import Flask
from src.routes.dashboard import dashboard_bp


@pytest.fixture
def app():
    """Create test Flask app."""
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test-secret-key"
    app.register_blueprint(dashboard_bp)
    app.config["TESTING"] = True

    # Mock auth service
    mock_auth_service = MagicMock()
    mock_user = MagicMock()
    mock_user.id = 123
    mock_user.email = "test@example.com"
    mock_user.role.value = "member"
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
    return {"Authorization": "Bearer test-token-123"}


class TestDashboardStats:
    """Test dashboard statistics route."""

    @patch("src.routes.dashboard.session_scope")
    def test_get_stats_success(self, mock_session, client, auth_headers):
        """Test getting dashboard stats."""
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db

        # Mock query results
        mock_db.query().scalar.return_value = 10  # meetings count
        mock_db.query().filter().scalar.side_effect = [5, 3]  # todos, completed

        response = client.get("/api/dashboard/stats", headers=auth_headers)

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "data" in data
        assert "total_meetings" in data["data"]
        assert "total_todos" in data["data"]

    @patch("src.routes.dashboard.session_scope")
    def test_get_stats_admin_user(self, mock_session, client, app, auth_headers):
        """Test stats for admin user (sees all todos)."""
        # Update mock user to admin
        mock_user = app.auth_service.get_current_user.return_value
        mock_user.role.value = "admin"

        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db

        # Create separate query mocks for each call
        mock_query1 = MagicMock()
        mock_query1.scalar.return_value = 10  # meetings

        mock_query2 = MagicMock()
        mock_query2.scalar.return_value = 15  # todos

        mock_query3 = MagicMock()
        mock_filter3 = MagicMock()
        mock_filter3.scalar.return_value = 8  # completed
        mock_query3.filter.return_value = mock_filter3

        mock_query4 = MagicMock()
        mock_filter4 = MagicMock()
        mock_filter4.scalar.return_value = 3  # projects
        mock_query4.filter.return_value = mock_filter4

        mock_db.query.side_effect = [mock_query1, mock_query2, mock_query3, mock_query4]

        response = client.get("/api/dashboard/stats", headers=auth_headers)

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["data"]["total_todos"] == 15

    @patch("src.routes.dashboard.session_scope")
    def test_get_stats_error(self, mock_session, client, auth_headers):
        """Test stats error handling."""
        mock_session.side_effect = Exception("Database error")

        response = client.get("/api/dashboard/stats", headers=auth_headers)

        assert response.status_code == 500
        data = response.get_json()
        assert data["success"] is False
        assert "error" in data


class TestAdminRoutes:
    """Test admin routes."""

    @patch("src.routes.dashboard.get_engine")
    def test_create_users_table_success(self, mock_get_engine, client):
        """Test creating users table."""
        mock_engine = MagicMock()
        mock_get_engine.return_value = mock_engine

        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn

        mock_result = MagicMock()
        mock_result.scalar.return_value = 0
        mock_conn.execute.return_value = mock_result

        response = client.post("/api/dashboard/admin/create-users-table")

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "table_exists" in data

    @patch("src.routes.dashboard.get_engine")
    def test_create_users_table_error(self, mock_get_engine, client):
        """Test users table creation error."""
        mock_get_engine.side_effect = Exception("Connection failed")

        response = client.post("/api/dashboard/admin/create-users-table")

        assert response.status_code == 500
        data = response.get_json()
        assert data["success"] is False
        assert "error" in data
