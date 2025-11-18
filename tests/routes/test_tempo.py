"""Tests for Tempo time tracking routes."""

import pytest
from unittest.mock import patch, MagicMock, ANY
from flask import Flask
from datetime import datetime
from src.routes.tempo import tempo_bp


@pytest.fixture
def app():
    """Create test Flask app."""
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test-secret-key"
    app.register_blueprint(tempo_bp)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


class TestSyncHours:
    """Test Tempo hours sync route."""

    @patch("src.routes.tempo.get_engine")
    @patch("src.routes.tempo.settings")
    def test_sync_hours_no_active_projects(
        self, mock_settings, mock_get_engine, client
    ):
        """Test sync when no active projects exist."""
        mock_engine = MagicMock()
        mock_get_engine.return_value = mock_engine

        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        mock_conn.execute.return_value = []

        response = client.post("/api/sync-hours")

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "No active projects" in data["message"]
        assert data["projects_updated"] == 0

    @patch("requests.get")
    @patch("src.routes.tempo.get_engine")
    @patch("src.routes.tempo.settings")
    def test_sync_hours_api_failure(
        self, mock_settings, mock_get_engine, mock_requests_get, client
    ):
        """Test sync when Tempo API fails."""
        mock_engine = MagicMock()
        mock_get_engine.return_value = mock_engine

        # Mock active projects
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        mock_result = MagicMock()
        mock_result.__iter__.return_value = [("PROJ1", "Project 1", "client")]
        mock_conn.execute.return_value = mock_result

        # Mock Jira settings
        mock_settings.jira.username = "test@example.com"
        mock_settings.jira.api_token = "test-token"
        mock_settings.jira.url = "https://test.atlassian.net"

        # Mock failed Tempo API call (raise RequestException to be caught properly)
        import requests

        mock_requests_get.side_effect = requests.exceptions.RequestException(
            "API Error"
        )

        response = client.post("/api/sync-hours")

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is False
        assert "No worklogs retrieved" in data["message"]

    @patch("requests.get")
    @patch("src.routes.tempo.get_engine")
    @patch("src.routes.tempo.settings")
    @patch("src.routes.tempo.datetime")
    def test_sync_hours_success(
        self, mock_datetime, mock_settings, mock_get_engine, mock_requests_get, client
    ):
        """Test successful hours sync."""
        # Mock current date
        mock_now = datetime(2025, 1, 15)
        mock_datetime.now.return_value = mock_now
        mock_datetime.strptime = datetime.strptime

        mock_engine = MagicMock()
        mock_get_engine.return_value = mock_engine

        # Mock active projects
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn

        # First execute() returns projects, second execute() is the UPDATE
        project_result = MagicMock()
        project_result.__iter__.return_value = [("PROJ1", "Project 1", "client")]
        mock_conn.execute.side_effect = [project_result] + [MagicMock()] * 10

        # Mock Jira/Tempo settings
        mock_settings.jira.username = "test@example.com"
        mock_settings.jira.api_token = "test-token"
        mock_settings.jira.url = "https://test.atlassian.net"

        # Mock Tempo API response with worklogs
        mock_tempo_response = MagicMock()
        mock_tempo_response.json.return_value = {
            "results": [
                {
                    "description": "Work on PROJ1-123",
                    "timeSpentSeconds": 7200,  # 2 hours
                    "startDate": "2025-01-15",
                    "issue": {"id": "12345"},
                }
            ],
            "metadata": {"next": None},
        }
        mock_requests_get.return_value = mock_tempo_response

        response = client.post("/api/sync-hours")

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["projects_updated"] == 1
        assert "current_month_total" in data

    @patch("src.routes.tempo.get_engine")
    def test_sync_hours_database_error(self, mock_get_engine, client):
        """Test sync when database error occurs."""
        mock_engine = MagicMock()
        mock_get_engine.return_value = mock_engine

        # Mock database connection failure
        mock_engine.connect.side_effect = Exception("Database connection failed")

        response = client.post("/api/sync-hours")

        assert response.status_code == 500
        data = response.get_json()
        assert data["success"] is False
        assert "error" in data


class TestProjectDigest:
    """Test project digest generation route."""

    @patch("src.routes.tempo.asyncio.run")
    @patch("src.services.project_activity_aggregator.ProjectActivityAggregator")
    @patch("src.utils.database.get_session")
    def test_generate_digest_success(
        self, mock_get_session, mock_aggregator_class, mock_async, client
    ):
        """Test successful project digest generation."""
        # Mock database session to return no cache (cache miss)
        mock_session = MagicMock()
        mock_query = mock_session.query.return_value
        mock_filter = mock_query.filter.return_value
        mock_order_by = mock_filter.order_by.return_value
        mock_order_by.first.return_value = None  # No cache entry
        mock_get_session.return_value = mock_session

        mock_aggregator = MagicMock()
        mock_aggregator_class.return_value = mock_aggregator

        # Mock activity data
        mock_activity = MagicMock()
        mock_activity.meetings = ["meeting1", "meeting2"]
        mock_activity.completed_tickets = ["ticket1"]
        mock_activity.new_tickets = ["ticket2", "ticket3"]
        mock_activity.total_hours = 40.5
        mock_activity.progress_summary = "Good progress"
        mock_activity.key_achievements = ["Achievement 1"]
        mock_activity.blockers_risks = ["Blocker 1"]
        mock_activity.next_steps = ["Next step 1"]

        mock_aggregator.format_client_agenda.return_value = "# Project Digest"

        # Mock async.run to return the activity data
        def async_side_effect(coro):
            return {
                "success": True,
                "project_key": "PROJ1",
                "project_name": "Project 1",
                "days_back": 7,
                "activity_data": {
                    "meetings_count": 2,
                    "tickets_completed": 1,
                    "tickets_created": 2,
                    "hours_logged": 40.5,
                    "progress_summary": "Good progress",
                    "key_achievements": ["Achievement 1"],
                    "blockers_risks": ["Blocker 1"],
                    "next_steps": ["Next step 1"],
                },
                "formatted_agenda": "# Project Digest",
            }

        mock_async.side_effect = async_side_effect

        response = client.post(
            "/api/project-digest/PROJ1", json={"days": 7, "project_name": "Project 1"}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["project_key"] == "PROJ1"
        assert data["project_name"] == "Project 1"
        assert data["days_back"] == 7
        assert "activity_data" in data
        assert "formatted_agenda" in data

    @patch("src.routes.tempo.asyncio.run")
    @patch("src.utils.database.get_session")
    def test_generate_digest_default_params(self, mock_get_session, mock_async, client):
        """Test digest generation with default parameters."""
        # Mock database session to return no cache (cache miss)
        mock_session = MagicMock()
        mock_query = mock_session.query.return_value
        mock_filter = mock_query.filter.return_value
        mock_order_by = mock_filter.order_by.return_value
        mock_order_by.first.return_value = None  # No cache entry
        mock_get_session.return_value = mock_session

        def async_side_effect(coro):
            return {
                "success": True,
                "project_key": "PROJ1",
                "project_name": "PROJ1",
                "days_back": 7,
                "activity_data": {},
                "formatted_agenda": "",
            }

        mock_async.side_effect = async_side_effect

        response = client.post(
            "/api/project-digest/PROJ1", json={}, content_type="application/json"
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["project_key"] == "PROJ1"
        assert data["days_back"] == 7  # Default value

    @patch("src.routes.tempo.asyncio.run")
    @patch("src.utils.database.get_session")
    def test_generate_digest_custom_days(self, mock_get_session, mock_async, client):
        """Test digest generation with custom days parameter."""
        # Mock database session to return no cache (cache miss)
        mock_session = MagicMock()
        mock_query = mock_session.query.return_value
        mock_filter = mock_query.filter.return_value
        mock_order_by = mock_filter.order_by.return_value
        mock_order_by.first.return_value = None  # No cache entry
        mock_get_session.return_value = mock_session

        def async_side_effect(coro):
            return {
                "success": True,
                "project_key": "PROJ1",
                "project_name": "Project 1",
                "days_back": 14,
                "activity_data": {},
                "formatted_agenda": "",
            }

        mock_async.side_effect = async_side_effect

        response = client.post(
            "/api/project-digest/PROJ1", json={"days": 14, "project_name": "Project 1"}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["days_back"] == 14

    @patch("src.routes.tempo.asyncio.run")
    def test_generate_digest_aggregator_error(self, mock_async, client):
        """Test digest generation when aggregator fails."""
        mock_async.side_effect = Exception("Aggregator error")

        response = client.post("/api/project-digest/PROJ1")

        assert response.status_code == 500
        data = response.get_json()
        assert data["success"] is False
        assert "error" in data

    @patch("src.routes.tempo.asyncio.run")
    def test_generate_digest_missing_project_key(self, mock_async, client):
        """Test that project_key is required in URL."""
        # This should 404 because project_key is part of the route
        response = client.post("/api/project-digest/")

        assert response.status_code in [404, 405]  # Not Found or Method Not Allowed

    @patch("src.routes.tempo.asyncio.run")
    @patch("src.utils.database.get_session")
    def test_generate_digest_cache_hit(self, mock_get_session, mock_async, client):
        """Test that cached digest is returned without calling aggregator."""
        from src.models import ProjectDigestCache
        from datetime import datetime, timezone
        import json

        # Create a mock cache entry that is not expired
        mock_cache = MagicMock(spec=ProjectDigestCache)
        mock_cache.project_key = "PROJ1"
        mock_cache.days = 7
        mock_cache.created_at = datetime.now(timezone.utc)
        mock_cache.digest_data = json.dumps(
            {
                "success": True,
                "project_key": "PROJ1",
                "project_name": "Cached Project",
                "days_back": 7,
                "activity_data": {"cached": True},
                "formatted_agenda": "Cached agenda",
            }
        )
        mock_cache.is_expired.return_value = False

        # Mock database session
        mock_session = MagicMock()
        mock_query = mock_session.query.return_value
        mock_filter = mock_query.filter.return_value
        mock_order_by = mock_filter.order_by.return_value
        mock_order_by.first.return_value = mock_cache
        mock_get_session.return_value = mock_session

        response = client.post(
            "/api/project-digest/PROJ1",
            json={"days": 7, "project_name": "Test Project"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["from_cache"] is True
        assert data["activity_data"]["cached"] is True
        # Aggregator should NOT be called
        mock_async.assert_not_called()

    @patch("src.routes.tempo.asyncio.run")
    @patch("src.utils.database.get_session")
    def test_generate_digest_cache_miss(self, mock_get_session, mock_async, client):
        """Test that digest is generated and cached when no cache exists."""
        import json

        # Mock no cache entry found
        mock_session = MagicMock()
        mock_query = mock_session.query.return_value
        mock_filter = mock_query.filter.return_value
        mock_order_by = mock_filter.order_by.return_value
        mock_order_by.first.return_value = None
        mock_get_session.return_value = mock_session

        # Mock aggregator response
        def async_side_effect(coro):
            return {
                "success": True,
                "project_key": "PROJ1",
                "project_name": "Fresh Project",
                "days_back": 7,
                "activity_data": {"fresh": True},
                "formatted_agenda": "Fresh agenda",
            }

        mock_async.side_effect = async_side_effect

        response = client.post(
            "/api/project-digest/PROJ1",
            json={"days": 7, "project_name": "Test Project"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "from_cache" not in data  # Fresh generation
        # Aggregator should be called
        mock_async.assert_called_once()
        # Cache should be saved
        assert mock_session.add.called
        assert mock_session.commit.called

    @patch("src.routes.tempo.asyncio.run")
    @patch("src.utils.database.get_session")
    def test_generate_digest_force_refresh(self, mock_get_session, mock_async, client):
        """Test that force_refresh bypasses cache."""
        from src.models import ProjectDigestCache
        from datetime import datetime, timezone
        import json

        # Create a mock cache entry (should be ignored)
        mock_cache = MagicMock(spec=ProjectDigestCache)
        mock_cache.is_expired.return_value = False
        mock_cache.digest_data = json.dumps({"cached": True})

        mock_session = MagicMock()
        mock_query = mock_session.query.return_value
        mock_filter = mock_query.filter.return_value
        mock_order_by = mock_filter.order_by.return_value
        mock_order_by.first.return_value = mock_cache
        mock_get_session.return_value = mock_session

        # Mock aggregator response
        def async_side_effect(coro):
            return {
                "success": True,
                "project_key": "PROJ1",
                "project_name": "Refreshed Project",
                "days_back": 7,
                "activity_data": {"refreshed": True},
                "formatted_agenda": "Refreshed agenda",
            }

        mock_async.side_effect = async_side_effect

        response = client.post(
            "/api/project-digest/PROJ1",
            json={"days": 7, "project_name": "Test Project", "force_refresh": True},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "from_cache" not in data
        # Aggregator SHOULD be called despite cache existing
        mock_async.assert_called_once()

    @patch("src.routes.tempo.asyncio.run")
    @patch("src.utils.database.get_session")
    def test_generate_digest_expired_cache(self, mock_get_session, mock_async, client):
        """Test that expired cache triggers regeneration."""
        from src.models import ProjectDigestCache
        from datetime import datetime, timezone
        import json

        # Create a mock cache entry that IS expired
        mock_cache = MagicMock(spec=ProjectDigestCache)
        mock_cache.project_key = "PROJ1"
        mock_cache.days = 7
        mock_cache.created_at = datetime.now(timezone.utc)
        mock_cache.digest_data = json.dumps({"old": True})
        mock_cache.is_expired.return_value = True  # Expired!

        mock_session = MagicMock()
        mock_query = mock_session.query.return_value
        mock_filter = mock_query.filter.return_value
        mock_order_by = mock_filter.order_by.return_value
        mock_order_by.first.return_value = mock_cache
        mock_get_session.return_value = mock_session

        # Mock aggregator response
        def async_side_effect(coro):
            return {
                "success": True,
                "project_key": "PROJ1",
                "project_name": "New Project",
                "days_back": 7,
                "activity_data": {"new": True},
                "formatted_agenda": "New agenda",
            }

        mock_async.side_effect = async_side_effect

        response = client.post(
            "/api/project-digest/PROJ1",
            json={"days": 7, "project_name": "Test Project"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "from_cache" not in data
        # Aggregator SHOULD be called because cache is expired
        mock_async.assert_called_once()
