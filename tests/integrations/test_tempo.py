"""Unit tests for Tempo API integration."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from src.integrations.tempo import TempoAPIClient


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up mock environment variables."""
    monkeypatch.setenv("TEMPO_API_TOKEN", "test-tempo-token")
    monkeypatch.setenv("JIRA_URL", "https://test.atlassian.net")
    monkeypatch.setenv("JIRA_USERNAME", "test@example.com")
    monkeypatch.setenv("JIRA_API_TOKEN", "test-jira-token")


@pytest.fixture
def tempo_client(mock_env_vars):
    """Create a TempoAPIClient instance with mocked environment."""
    return TempoAPIClient()


class TestTempoAPIClient:
    """Tests for TempoAPIClient"""

    def test_init_success(self, mock_env_vars):
        """Test successful initialization with all required env vars."""
        client = TempoAPIClient()
        assert client.tempo_token == "test-tempo-token"
        assert client.jira_url == "https://test.atlassian.net"
        assert client.jira_username == "test@example.com"
        assert client.jira_token == "test-jira-token"

    def test_init_missing_tempo_token(self, monkeypatch):
        """Test initialization fails without TEMPO_API_TOKEN."""
        monkeypatch.setenv("JIRA_URL", "https://test.atlassian.net")
        monkeypatch.setenv("JIRA_USERNAME", "test@example.com")
        monkeypatch.setenv("JIRA_API_TOKEN", "test-jira-token")
        monkeypatch.delenv("TEMPO_API_TOKEN", raising=False)

        with pytest.raises(ValueError, match="TEMPO_API_TOKEN"):
            TempoAPIClient()

    def test_init_missing_jira_vars(self, monkeypatch):
        """Test initialization fails without Jira credentials."""
        monkeypatch.setenv("TEMPO_API_TOKEN", "test-tempo-token")
        monkeypatch.delenv("JIRA_URL", raising=False)
        monkeypatch.delenv("JIRA_USERNAME", raising=False)
        monkeypatch.delenv("JIRA_API_TOKEN", raising=False)

        with pytest.raises(ValueError, match="JIRA_URL"):
            TempoAPIClient()

    @patch("src.integrations.tempo.requests.get")
    def test_get_issue_key_from_jira_success(self, mock_get, tempo_client):
        """Test successful issue key resolution."""
        mock_response = Mock()
        mock_response.json.return_value = {"key": "SUBS-123"}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        issue_key = tempo_client.get_issue_key_from_jira("10001")

        assert issue_key == "SUBS-123"
        assert tempo_client.issue_cache["10001"] == "SUBS-123"
        mock_get.assert_called_once()

    @patch("src.integrations.tempo.requests.get")
    def test_get_issue_key_from_jira_cached(self, mock_get, tempo_client):
        """Test cached issue key is returned without API call."""
        tempo_client.issue_cache["10001"] = "SUBS-123"

        issue_key = tempo_client.get_issue_key_from_jira("10001")

        assert issue_key == "SUBS-123"
        mock_get.assert_not_called()

    @patch("src.integrations.tempo.requests.get")
    def test_get_issue_key_from_jira_error(self, mock_get, tempo_client):
        """Test error handling when Jira API fails."""
        mock_get.side_effect = Exception("API Error")

        issue_key = tempo_client.get_issue_key_from_jira("10001")

        assert issue_key is None
        assert tempo_client.issue_cache["10001"] is None

    @patch("src.integrations.tempo.requests.get")
    def test_get_worklogs_success(self, mock_get, tempo_client):
        """Test successful worklog retrieval."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "results": [
                {"id": 1, "timeSpentSeconds": 3600},
                {"id": 2, "timeSpentSeconds": 7200},
            ],
            "metadata": {},
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        worklogs = tempo_client.get_worklogs("2025-10-01", "2025-10-31")

        assert len(worklogs) == 2
        assert worklogs[0]["id"] == 1
        assert worklogs[1]["timeSpentSeconds"] == 7200

    @patch("src.integrations.tempo.requests.get")
    def test_get_worklogs_pagination(self, mock_get, tempo_client):
        """Test worklog retrieval with pagination."""
        # First page
        first_response = Mock()
        first_response.json.return_value = {
            "results": [{"id": 1, "timeSpentSeconds": 3600}],
            "metadata": {"next": "https://api.tempo.io/4/worklogs?page=2"},
        }
        first_response.raise_for_status = Mock()

        # Second page
        second_response = Mock()
        second_response.json.return_value = {
            "results": [{"id": 2, "timeSpentSeconds": 7200}],
            "metadata": {},
        }
        second_response.raise_for_status = Mock()

        mock_get.side_effect = [first_response, second_response]

        worklogs = tempo_client.get_worklogs("2025-10-01", "2025-10-31")

        assert len(worklogs) == 2
        assert mock_get.call_count == 2

    def test_process_worklogs_with_description_keys(self, tempo_client):
        """Test worklog processing with issue keys in descriptions."""
        worklogs = [
            {
                "description": "Working on SUBS-123",
                "timeSpentSeconds": 3600,
                "issue": {"id": "10001"},
            },
            {
                "description": "Fixed bug BEVS-456",
                "timeSpentSeconds": 7200,
                "issue": {"id": "10002"},
            },
        ]

        project_hours, processed, skipped = tempo_client.process_worklogs(worklogs)

        assert processed == 2
        assert skipped == 0
        assert project_hours["SUBS"] == 1.0  # 3600 / 3600
        assert project_hours["BEVS"] == 2.0  # 7200 / 3600

    @patch.object(TempoAPIClient, "get_issue_key_from_jira")
    def test_process_worklogs_with_jira_lookup(self, mock_get_key, tempo_client):
        """Test worklog processing with Jira API lookup."""
        mock_get_key.side_effect = ["SUBS-123", "BEVS-456"]

        worklogs = [
            {
                "description": "Working on issue",
                "timeSpentSeconds": 3600,
                "issue": {"id": "10001"},
            },
            {
                "description": "Fixed bug",
                "timeSpentSeconds": 7200,
                "issue": {"id": "10002"},
            },
        ]

        project_hours, processed, skipped = tempo_client.process_worklogs(worklogs)

        assert processed == 2
        assert skipped == 0
        assert project_hours["SUBS"] == 1.0
        assert project_hours["BEVS"] == 2.0
        assert mock_get_key.call_count == 2

    def test_process_worklogs_skip_no_issue(self, tempo_client):
        """Test worklog processing skips entries without issue keys."""
        worklogs = [
            {
                "description": "General work",
                "timeSpentSeconds": 3600,
                "issue": {},  # No issue ID
            }
        ]

        project_hours, processed, skipped = tempo_client.process_worklogs(worklogs)

        assert processed == 0
        assert skipped == 1
        assert len(project_hours) == 0

    @patch.object(TempoAPIClient, "get_worklogs")
    def test_get_current_month_hours(self, mock_get_worklogs, tempo_client):
        """Test getting current month hours."""
        mock_get_worklogs.return_value = [
            {
                "description": "SUBS-123 work",
                "timeSpentSeconds": 3600,
                "issue": {"id": "10001"},
            }
        ]

        project_hours = tempo_client.get_current_month_hours()

        assert "SUBS" in project_hours
        assert project_hours["SUBS"] == 1.0
        mock_get_worklogs.assert_called_once()

    @patch.object(TempoAPIClient, "get_worklogs")
    def test_get_year_to_date_hours(self, mock_get_worklogs, tempo_client):
        """Test getting year-to-date hours."""
        mock_get_worklogs.return_value = [
            {
                "description": "SUBS-123 work",
                "timeSpentSeconds": 36000,  # 10 hours
                "issue": {"id": "10001"},
            }
        ]

        project_hours = tempo_client.get_year_to_date_hours()

        assert "SUBS" in project_hours
        assert project_hours["SUBS"] == 10.0
        mock_get_worklogs.assert_called_once()

    @patch.object(TempoAPIClient, "get_worklogs")
    def test_get_date_range_hours(self, mock_get_worklogs, tempo_client):
        """Test getting hours for specific date range."""
        mock_get_worklogs.return_value = [
            {
                "description": "SUBS-123 work",
                "timeSpentSeconds": 7200,  # 2 hours
                "issue": {"id": "10001"},
            }
        ]

        project_hours = tempo_client.get_date_range_hours("2025-09-01", "2025-09-30")

        assert "SUBS" in project_hours
        assert project_hours["SUBS"] == 2.0
        mock_get_worklogs.assert_called_once_with("2025-09-01", "2025-09-30")

    def test_time_conversion_accuracy(self, tempo_client):
        """Test accurate conversion from seconds to hours."""
        worklogs = [
            {
                "description": "SUBS-123",
                "timeSpentSeconds": 1800,  # 0.5 hours
                "issue": {"id": "10001"},
            },
            {
                "description": "SUBS-124",
                "timeSpentSeconds": 5400,  # 1.5 hours
                "issue": {"id": "10002"},
            },
        ]

        project_hours, _, _ = tempo_client.process_worklogs(worklogs)

        # Total should be 2.0 hours
        assert project_hours["SUBS"] == pytest.approx(2.0, rel=1e-9)
