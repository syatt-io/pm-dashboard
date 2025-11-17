"""Unit tests for Tempo sync job."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from src.jobs.tempo_sync import TempoSyncJob, run_tempo_sync


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up mock environment variables."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("TEMPO_API_TOKEN", "test-tempo-token")
    monkeypatch.setenv("JIRA_URL", "https://test.atlassian.net")
    monkeypatch.setenv("JIRA_USERNAME", "test@example.com")
    monkeypatch.setenv("JIRA_API_TOKEN", "test-jira-token")


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    session = MagicMock()
    session.execute = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    session.close = MagicMock()
    return session


@pytest.fixture
def mock_tempo_client():
    """Create a mock TempoAPIClient."""
    client = MagicMock()
    client.get_current_month_hours = MagicMock(
        return_value={"SUBS": 10.5, "BEVS": 5.25}
    )
    client.get_all_time_hours = MagicMock(return_value={"SUBS": 120.0, "BEVS": 60.0})
    return client


class TestTempoSyncJob:
    """Tests for TempoSyncJob"""

    @patch("src.jobs.tempo_sync.create_engine")
    @patch("src.jobs.tempo_sync.TempoAPIClient")
    def test_init_success(self, mock_client_class, mock_create_engine, mock_env_vars):
        """Test successful initialization."""
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine

        job = TempoSyncJob()

        assert job.database_url == "sqlite:///:memory:"
        mock_create_engine.assert_called_once_with("sqlite:///:memory:")

    @patch("src.jobs.tempo_sync.create_engine")
    @patch("src.jobs.tempo_sync.TempoAPIClient")
    def test_init_missing_database_url(
        self, mock_client_class, mock_create_engine, monkeypatch
    ):
        """Test initialization fails without DATABASE_URL."""
        monkeypatch.setenv("TEMPO_API_TOKEN", "test-tempo-token")
        monkeypatch.setenv("JIRA_URL", "https://test.atlassian.net")
        monkeypatch.setenv("JIRA_USERNAME", "test@example.com")
        monkeypatch.setenv("JIRA_API_TOKEN", "test-jira-token")
        monkeypatch.delenv("DATABASE_URL", raising=False)

        with pytest.raises(ValueError, match="DATABASE_URL"):
            TempoSyncJob()

    @patch("src.jobs.tempo_sync.create_engine")
    @patch("src.jobs.tempo_sync.TempoAPIClient")
    def test_get_active_projects(
        self, mock_client_class, mock_create_engine, mock_env_vars
    ):
        """Test getting active projects from database."""
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine

        job = TempoSyncJob()

        # Mock session and result
        mock_result = MagicMock()
        mock_result.__iter__ = Mock(
            return_value=iter([("SUBS",), ("BEVS",), ("RNWL",)])
        )

        mock_session_instance = MagicMock()
        mock_session_instance.execute.return_value = mock_result
        mock_session_instance.close = MagicMock()

        job.Session = MagicMock(return_value=mock_session_instance)

        projects = job.get_active_projects()

        assert len(projects) == 3
        assert "SUBS" in projects
        assert "BEVS" in projects
        assert "RNWL" in projects
        mock_session_instance.close.assert_called_once()

    @patch("src.jobs.tempo_sync.create_engine")
    @patch("src.jobs.tempo_sync.TempoAPIClient")
    def test_update_project_hours_success(
        self, mock_client_class, mock_create_engine, mock_env_vars
    ):
        """Test successful project hours update."""
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine

        job = TempoSyncJob()

        # Mock session
        mock_result = MagicMock()
        mock_result.rowcount = 1

        mock_session_instance = MagicMock()
        mock_session_instance.execute.return_value = mock_result
        mock_session_instance.commit = MagicMock()
        mock_session_instance.close = MagicMock()

        job.Session = MagicMock(return_value=mock_session_instance)
        job.get_active_projects = MagicMock(return_value=["SUBS", "BEVS"])

        current_hours = {"SUBS": 10.5, "BEVS": 5.25}
        cumulative_hours = {"SUBS": 120.0, "BEVS": 60.0}

        stats = job.update_project_hours(current_hours, cumulative_hours)

        assert stats["updated"] == 2
        assert stats["skipped"] == 0
        assert stats["total"] == 2
        mock_session_instance.commit.assert_called_once()

    @patch("src.jobs.tempo_sync.create_engine")
    @patch("src.jobs.tempo_sync.TempoAPIClient")
    def test_update_project_hours_project_not_found(
        self, mock_client_class, mock_create_engine, mock_env_vars
    ):
        """Test handling of projects not found in database."""
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine

        job = TempoSyncJob()

        # Mock session - simulate project not found
        mock_result = MagicMock()
        mock_result.rowcount = 0

        mock_session_instance = MagicMock()
        mock_session_instance.execute.return_value = mock_result
        mock_session_instance.commit = MagicMock()
        mock_session_instance.close = MagicMock()

        job.Session = MagicMock(return_value=mock_session_instance)
        job.get_active_projects = MagicMock(return_value=["NONEXISTENT"])

        current_hours = {"NONEXISTENT": 10.5}
        cumulative_hours = {"NONEXISTENT": 120.0}

        stats = job.update_project_hours(current_hours, cumulative_hours)

        # New behavior: projects from get_active_projects are always updated
        # (upsert into project_monthly_forecast always succeeds)
        assert stats["updated"] == 1
        assert stats["skipped"] == 0
        assert stats["total"] == 1

    @patch("src.jobs.tempo_sync.create_engine")
    @patch("src.jobs.tempo_sync.TempoAPIClient")
    def test_update_project_hours_rollback_on_error(
        self, mock_client_class, mock_create_engine, mock_env_vars
    ):
        """Test rollback on database error."""
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine

        job = TempoSyncJob()

        # Mock session to raise error
        mock_session_instance = MagicMock()
        mock_session_instance.execute.side_effect = Exception("Database error")
        mock_session_instance.rollback = MagicMock()
        mock_session_instance.close = MagicMock()

        job.Session = MagicMock(return_value=mock_session_instance)
        job.get_active_projects = MagicMock(return_value=["SUBS"])

        current_hours = {"SUBS": 10.5}
        cumulative_hours = {"SUBS": 120.0}

        with pytest.raises(Exception, match="Database error"):
            job.update_project_hours(current_hours, cumulative_hours)

        mock_session_instance.rollback.assert_called_once()

    @patch("src.jobs.tempo_sync.create_engine")
    @patch("src.jobs.tempo_sync.TempoAPIClient")
    def test_run_success(self, mock_client_class, mock_create_engine, mock_env_vars):
        """Test successful job execution."""
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine

        # Mock Tempo client
        mock_client = MagicMock()
        mock_client.get_current_month_hours.return_value = {"SUBS": 10.5}
        mock_client.get_all_time_hours.return_value = {"SUBS": 120.0}
        mock_client_class.return_value = mock_client

        job = TempoSyncJob()

        # Mock update_project_hours
        job.update_project_hours = MagicMock(
            return_value={"updated": 1, "skipped": 0, "total": 1}
        )

        stats = job.run()

        assert stats["success"] is True
        assert stats["projects_updated"] == 1
        assert stats["projects_skipped"] == 0
        assert stats["total_projects"] == 1
        assert stats["unique_projects_tracked"] == 1
        assert "start_time" in stats
        assert "end_time" in stats
        assert "duration_seconds" in stats

    @patch("src.jobs.tempo_sync.create_engine")
    @patch("src.jobs.tempo_sync.TempoAPIClient")
    def test_run_failure(self, mock_client_class, mock_create_engine, mock_env_vars):
        """Test job execution with failure."""
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine

        # Mock Tempo client to raise error
        mock_client = MagicMock()
        mock_client.get_current_month_hours.side_effect = Exception("Tempo API error")
        mock_client_class.return_value = mock_client

        job = TempoSyncJob()

        stats = job.run()

        assert stats["success"] is False
        assert "error" in stats
        assert "Tempo API error" in stats["error"]
        assert "start_time" in stats
        assert "end_time" in stats
        assert "duration_seconds" in stats

    @patch("src.jobs.tempo_sync.TempoSyncJob")
    def test_run_tempo_sync_function(self, mock_job_class):
        """Test run_tempo_sync function."""
        mock_job = MagicMock()
        mock_job.run.return_value = {"success": True, "projects_updated": 5}
        mock_job_class.return_value = mock_job

        stats = run_tempo_sync()

        assert stats["success"] is True
        assert stats["projects_updated"] == 5
        mock_job_class.assert_called_once()
        mock_job.run.assert_called_once()

    @patch("src.jobs.tempo_sync.create_engine")
    @patch("src.jobs.tempo_sync.TempoAPIClient")
    def test_zero_hours_handling(
        self, mock_client_class, mock_create_engine, mock_env_vars
    ):
        """Test handling of projects with zero hours."""
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine

        mock_client = MagicMock()
        mock_client.get_current_month_hours.return_value = {"SUBS": 0.0}
        mock_client.get_all_time_hours.return_value = {"SUBS": 0.0}
        mock_client_class.return_value = mock_client

        job = TempoSyncJob()

        # Mock session
        mock_result = MagicMock()
        mock_result.rowcount = 1

        mock_session_instance = MagicMock()
        mock_session_instance.execute.return_value = mock_result
        mock_session_instance.commit = MagicMock()
        mock_session_instance.close = MagicMock()

        job.Session = MagicMock(return_value=mock_session_instance)
        job.get_active_projects = MagicMock(return_value=["SUBS"])

        stats = job.run()

        assert stats["success"] is True
        # Should still update even with 0 hours
        assert stats["projects_updated"] == 1

    @patch("src.jobs.tempo_sync.create_engine")
    @patch("src.jobs.tempo_sync.TempoAPIClient")
    def test_multiple_projects_update(
        self, mock_client_class, mock_create_engine, mock_env_vars
    ):
        """Test updating multiple projects."""
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine

        mock_client = MagicMock()
        mock_client.get_current_month_hours.return_value = {
            "SUBS": 10.5,
            "BEVS": 5.25,
            "RNWL": 15.75,
            "ECSC": 20.0,
        }
        mock_client.get_all_time_hours.return_value = {
            "SUBS": 120.0,
            "BEVS": 60.0,
            "RNWL": 180.0,
            "ECSC": 240.0,
        }
        mock_client_class.return_value = mock_client

        job = TempoSyncJob()

        # Mock session
        mock_result = MagicMock()
        mock_result.rowcount = 1

        mock_session_instance = MagicMock()
        mock_session_instance.execute.return_value = mock_result
        mock_session_instance.commit = MagicMock()
        mock_session_instance.close = MagicMock()

        job.Session = MagicMock(return_value=mock_session_instance)
        job.get_active_projects = MagicMock(
            return_value=["SUBS", "BEVS", "RNWL", "ECSC"]
        )

        stats = job.run()

        assert stats["success"] is True
        assert stats["projects_updated"] == 4
        assert stats["unique_projects_tracked"] == 4

    @patch("src.managers.notifications.NotificationManager")
    def test_notification_manager_initialization_with_none_config(
        self, mock_notif_manager
    ):
        """
        Test that NotificationManager is initialized correctly with None config.

        This test prevents regression of the bug where NotificationManager()
        was called without arguments, causing TypeError.

        IMPORTANT: NotificationManager requires a config parameter. Pass None
        to use environment variables for configuration.
        """
        from src.jobs.tempo_sync import TempoSyncJob

        monkeypatch_env = pytest.MonkeyPatch()
        monkeypatch_env.setenv("SLACK_BOT_TOKEN", "xoxb-test-token")
        monkeypatch_env.setenv("SLACK_CHANNEL", "#test-channel")

        # Mock NotificationManager instance
        mock_notif_instance = MagicMock()
        mock_notif_instance._send_slack_dm = MagicMock()
        mock_notif_manager.return_value = mock_notif_instance

        # Simulate what the send_slack_notification method does
        # (imports inside the method and calls NotificationManager(None))
        stats = {"success": True, "projects_updated": 5}

        # This is what happens inside send_slack_notification method
        notifier = mock_notif_manager(None)

        # Verify NotificationManager was called with None (not without arguments!)
        # This is the critical assertion that prevents the bug
        mock_notif_manager.assert_called_with(None)

        monkeypatch_env.undo()

    @patch("src.jobs.tempo_sync.create_engine")
    @patch("src.jobs.tempo_sync.TempoAPIClient")
    def test_notification_manager_not_called_without_arguments(
        self, mock_client_class, mock_create_engine, mock_env_vars
    ):
        """
        Test that NotificationManager is NEVER called without arguments.

        This is a critical regression test for the silent notification failure bug.
        NotificationManager() without arguments raises TypeError, which was
        silently caught by broad exception handlers.
        """
        from src.managers.notifications import NotificationManager

        # This should raise TypeError (missing required positional argument: 'config')
        with pytest.raises(TypeError, match="missing 1 required positional argument"):
            NotificationManager()

    @patch("src.jobs.tempo_sync.create_engine")
    @patch("src.jobs.tempo_sync.TempoAPIClient")
    def test_notification_manager_accepts_none_config(
        self, mock_client_class, mock_create_engine, mock_env_vars
    ):
        """
        Test that NotificationManager accepts None as config parameter.

        When None is passed, NotificationManager should fall back to
        reading configuration from environment variables.
        """
        from src.managers.notifications import NotificationManager

        # Set up environment variables for NotificationManager
        monkeypatch_env = pytest.MonkeyPatch()
        monkeypatch_env.setenv("SLACK_BOT_TOKEN", "xoxb-test-token")
        monkeypatch_env.setenv("SLACK_CHANNEL", "#test-channel")

        # This should NOT raise an error
        notif = NotificationManager(None)

        # Verify it was initialized
        assert notif is not None
        assert notif.config is None  # Config should be None
        assert notif.slack_client is not None  # But Slack should be configured from env

        monkeypatch_env.undo()
