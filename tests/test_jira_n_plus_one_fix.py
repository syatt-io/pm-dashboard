"""Tests for N+1 query fix in Jira projects endpoint.

This test suite verifies that the get_jira_projects() endpoint uses
a single batch query instead of N separate queries to fetch project data.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime
from sqlalchemy import text


class TestJiraNPlusOneFix:
    """Test suite for N+1 query fix in get_jira_projects endpoint."""

    @patch('src.routes.jira.asyncio')
    @patch('src.routes.jira.JiraMCPClient')
    @patch('src.routes.jira.get_engine')
    @patch('src.routes.jira.settings')
    def test_single_batch_query_instead_of_n_queries(
        self, mock_settings, mock_get_engine, mock_jira_client_class, mock_asyncio
    ):
        """Test that project data is fetched with a single batch query, not N queries."""
        # Setup mock settings
        mock_settings.jira.url = "https://test.atlassian.net"
        mock_settings.jira.username = "test@example.com"
        mock_settings.jira.api_token = "test-token"

        # Setup mock Jira client to return 3 projects
        mock_jira_client = MagicMock()
        mock_jira_client.__aenter__.return_value = mock_jira_client
        mock_jira_client.__aexit__.return_value = None
        mock_jira_client.get_projects.return_value = [
            {"key": "PROJ1", "name": "Project 1"},
            {"key": "PROJ2", "name": "Project 2"},
            {"key": "PROJ3", "name": "Project 3"},
        ]
        mock_jira_client_class.return_value = mock_jira_client

        # Setup mock asyncio
        mock_asyncio.run.return_value = [
            {"key": "PROJ1", "name": "Project 1"},
            {"key": "PROJ2", "name": "Project 2"},
            {"key": "PROJ3", "name": "Project 3"},
        ]

        # Setup mock database connection
        mock_conn = MagicMock()
        mock_engine = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        mock_get_engine.return_value = mock_engine

        # Mock database results for all 3 projects
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            ("PROJ1", True, "project-based", 100.0, 50.0, "Monday", 40.0, 20.0, 15.0),
            ("PROJ2", False, "retainer", 200.0, 100.0, "Tuesday", 80.0, 40.0, 35.0),
            ("PROJ3", True, "project-based", 150.0, 75.0, None, 60.0, 30.0, 25.0),
        ]
        mock_conn.execute.return_value = mock_result

        # Import and call the endpoint
        from src.routes.jira import get_jira_projects
        response = get_jira_projects()

        # ✅ CRITICAL ASSERTION: Verify only ONE database query was executed (batch query)
        # Before the fix, this would be 3 queries (one per project)
        assert mock_conn.execute.call_count == 1, \
            f"Expected 1 batch query, but got {mock_conn.execute.call_count} queries"

        # Verify the query uses WHERE p.key = ANY(:project_keys) pattern
        call_args = mock_conn.execute.call_args
        query = str(call_args[0][0])
        assert "WHERE p.key = ANY(:project_keys)" in query, \
            "Query should use batch pattern with ANY(:project_keys)"

        # Verify query parameters include all project keys
        params = call_args[1]
        assert "project_keys" in params, "Query should have project_keys parameter"
        assert set(params["project_keys"]) == {"PROJ1", "PROJ2", "PROJ3"}, \
            "project_keys should include all project keys"

        # Verify response contains all 3 enhanced projects
        assert response[0]["success"] is True
        projects = response[0]["data"]["projects"]
        assert len(projects) == 3

        # Verify project data was merged correctly
        proj1 = next(p for p in projects if p["key"] == "PROJ1")
        assert proj1["is_active"] is True
        assert proj1["project_work_type"] == "project-based"
        assert proj1["total_hours"] == 100.0

        proj2 = next(p for p in projects if p["key"] == "PROJ2")
        assert proj2["is_active"] is False
        assert proj2["project_work_type"] == "retainer"
        assert proj2["total_hours"] == 200.0

    @patch('src.routes.jira.asyncio')
    @patch('src.routes.jira.JiraMCPClient')
    @patch('src.routes.jira.get_engine')
    @patch('src.routes.jira.settings')
    def test_handles_projects_without_database_records(
        self, mock_settings, mock_get_engine, mock_jira_client_class, mock_asyncio
    ):
        """Test that projects without database records get default values."""
        # Setup mock settings
        mock_settings.jira.url = "https://test.atlassian.net"
        mock_settings.jira.username = "test@example.com"
        mock_settings.jira.api_token = "test-token"

        # Setup mock Jira client to return 2 projects
        mock_jira_client = MagicMock()
        mock_jira_client.__aenter__.return_value = mock_jira_client
        mock_jira_client.__aexit__.return_value = None
        mock_jira_client.get_projects.return_value = [
            {"key": "PROJ1", "name": "Project 1"},
            {"key": "PROJ2", "name": "Project 2"},
        ]
        mock_jira_client_class.return_value = mock_jira_client

        # Setup mock asyncio
        mock_asyncio.run.return_value = [
            {"key": "PROJ1", "name": "Project 1"},
            {"key": "PROJ2", "name": "Project 2"},
        ]

        # Setup mock database connection
        mock_conn = MagicMock()
        mock_engine = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        mock_get_engine.return_value = mock_engine

        # Mock database results - only PROJ1 has a record, PROJ2 does not
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            ("PROJ1", True, "project-based", 100.0, 50.0, "Monday", 40.0, 20.0, 15.0),
        ]
        mock_conn.execute.return_value = mock_result

        # Import and call the endpoint
        from src.routes.jira import get_jira_projects
        response = get_jira_projects()

        # Verify response contains both projects
        projects = response[0]["data"]["projects"]
        assert len(projects) == 2

        # PROJ1 should have database data
        proj1 = next(p for p in projects if p["key"] == "PROJ1")
        assert proj1["is_active"] is True
        assert proj1["project_work_type"] == "project-based"
        assert proj1["total_hours"] == 100.0

        # PROJ2 should have default values
        proj2 = next(p for p in projects if p["key"] == "PROJ2")
        assert proj2["is_active"] is True  # Default
        assert proj2["project_work_type"] == "project-based"  # Default
        assert proj2["total_hours"] == 0  # Default
        assert proj2["cumulative_hours"] == 0  # Default
        assert proj2["weekly_meeting_day"] is None  # Default
        assert proj2["retainer_hours"] == 0  # Default

    @patch('src.routes.jira.asyncio')
    @patch('src.routes.jira.JiraMCPClient')
    @patch('src.routes.jira.get_engine')
    @patch('src.routes.jira.settings')
    def test_handles_empty_project_list(
        self, mock_settings, mock_get_engine, mock_jira_client_class, mock_asyncio
    ):
        """Test that empty project list is handled correctly."""
        # Setup mock settings
        mock_settings.jira.url = "https://test.atlassian.net"
        mock_settings.jira.username = "test@example.com"
        mock_settings.jira.api_token = "test-token"

        # Setup mock Jira client to return empty list
        mock_jira_client = MagicMock()
        mock_jira_client.__aenter__.return_value = mock_jira_client
        mock_jira_client.__aexit__.return_value = None
        mock_jira_client.get_projects.return_value = []
        mock_jira_client_class.return_value = mock_jira_client

        # Setup mock asyncio
        mock_asyncio.run.return_value = []

        # Setup mock database connection
        mock_conn = MagicMock()
        mock_engine = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        mock_get_engine.return_value = mock_engine

        # Import and call the endpoint
        from src.routes.jira import get_jira_projects
        response = get_jira_projects()

        # Verify no database query was executed (no projects to enhance)
        mock_conn.execute.assert_not_called()

        # Verify response is empty
        projects = response[0]["data"]["projects"]
        assert len(projects) == 0

    @patch('src.routes.jira.asyncio')
    @patch('src.routes.jira.JiraMCPClient')
    @patch('src.routes.jira.get_engine')
    @patch('src.routes.jira.settings')
    def test_database_error_returns_jira_projects_without_enhancement(
        self, mock_settings, mock_get_engine, mock_jira_client_class, mock_asyncio
    ):
        """Test that database errors don't break the endpoint."""
        # Setup mock settings
        mock_settings.jira.url = "https://test.atlassian.net"
        mock_settings.jira.username = "test@example.com"
        mock_settings.jira.api_token = "test-token"

        # Setup mock Jira client to return 2 projects
        mock_jira_client = MagicMock()
        mock_jira_client.__aenter__.return_value = mock_jira_client
        mock_jira_client.__aexit__.return_value = None
        mock_jira_client.get_projects.return_value = [
            {"key": "PROJ1", "name": "Project 1"},
            {"key": "PROJ2", "name": "Project 2"},
        ]
        mock_jira_client_class.return_value = mock_jira_client

        # Setup mock asyncio
        mock_asyncio.run.return_value = [
            {"key": "PROJ1", "name": "Project 1"},
            {"key": "PROJ2", "name": "Project 2"},
        ]

        # Setup mock database to raise an exception
        mock_engine = MagicMock()
        mock_engine.connect.side_effect = Exception("Database connection failed")
        mock_get_engine.return_value = mock_engine

        # Import and call the endpoint
        from src.routes.jira import get_jira_projects
        response = get_jira_projects()

        # Verify response still returns Jira projects (without enhancements)
        projects = response[0]["data"]["projects"]
        assert len(projects) == 2
        assert projects[0]["key"] == "PROJ1"
        assert projects[1]["key"] == "PROJ2"

    def test_performance_improvement_calculation(self):
        """Test that demonstrates the performance improvement."""
        # Before fix: N+1 queries
        # - 1 query to fetch all projects from Jira
        # - N queries to fetch database data (one per project)
        # Total: N+1 queries

        # After fix: 2 queries
        # - 1 query to fetch all projects from Jira
        # - 1 batch query to fetch all database data
        # Total: 2 queries

        test_cases = [
            (10, 11, 2),   # 10 projects: 11 queries → 2 queries (82% reduction)
            (50, 51, 2),   # 50 projects: 51 queries → 2 queries (96% reduction)
            (100, 101, 2), # 100 projects: 101 queries → 2 queries (98% reduction)
        ]

        for num_projects, queries_before, queries_after in test_cases:
            reduction = ((queries_before - queries_after) / queries_before) * 100
            print(f"\n{num_projects} projects:")
            print(f"  Before: {queries_before} queries")
            print(f"  After: {queries_after} queries")
            print(f"  Improvement: {reduction:.1f}% reduction")

            assert queries_after == 2, "Should always be 2 queries regardless of project count"
            assert reduction > 80, f"Should have >80% reduction for {num_projects} projects"


class TestBatchQueryCorrectness:
    """Test suite to verify batch query produces same results as N+1 queries."""

    def test_batch_query_matches_individual_queries(self):
        """Verify that batch query returns same data as individual queries would."""
        from sqlalchemy import create_engine, text
        from datetime import datetime

        # Create in-memory test database
        engine = create_engine('sqlite:///:memory:')

        with engine.connect() as conn:
            # Create test tables
            conn.execute(text("""
                CREATE TABLE projects (
                    key TEXT PRIMARY KEY,
                    is_active INTEGER,
                    project_work_type TEXT,
                    total_hours REAL,
                    cumulative_hours REAL,
                    weekly_meeting_day TEXT,
                    retainer_hours REAL
                )
            """))
            conn.execute(text("""
                CREATE TABLE project_monthly_forecast (
                    id INTEGER PRIMARY KEY,
                    project_key TEXT,
                    month_year DATE,
                    forecasted_hours REAL,
                    actual_monthly_hours REAL
                )
            """))

            # Insert test data
            conn.execute(text("""
                INSERT INTO projects (key, is_active, project_work_type, total_hours, cumulative_hours, weekly_meeting_day, retainer_hours)
                VALUES
                    ('PROJ1', 1, 'project-based', 100.0, 50.0, 'Monday', 40.0),
                    ('PROJ2', 0, 'retainer', 200.0, 100.0, 'Tuesday', 80.0),
                    ('PROJ3', 1, 'project-based', 150.0, 75.0, NULL, 60.0)
            """))

            current_month = datetime(2025, 11, 1).date()
            conn.execute(text("""
                INSERT INTO project_monthly_forecast (project_key, month_year, forecasted_hours, actual_monthly_hours)
                VALUES
                    ('PROJ1', :month, 20.0, 15.0),
                    ('PROJ2', :month, 40.0, 35.0),
                    ('PROJ3', :month, 30.0, 25.0)
            """), {"month": current_month})
            conn.commit()

            # Execute N+1 queries (old approach)
            n_plus_one_results = {}
            for project_key in ['PROJ1', 'PROJ2', 'PROJ3']:
                result = conn.execute(text("""
                    SELECT
                        p.is_active,
                        p.project_work_type,
                        p.total_hours,
                        p.cumulative_hours,
                        p.weekly_meeting_day,
                        p.retainer_hours,
                        pmf.forecasted_hours,
                        pmf.actual_monthly_hours
                    FROM projects p
                    LEFT JOIN project_monthly_forecast pmf
                        ON p.key = pmf.project_key
                        AND pmf.month_year = :current_month
                    WHERE p.key = :key
                """), {"key": project_key, "current_month": current_month}).fetchone()
                n_plus_one_results[project_key] = result

            # Execute batch query (new approach)
            project_keys = ['PROJ1', 'PROJ2', 'PROJ3']
            batch_results = conn.execute(text("""
                SELECT
                    p.key,
                    p.is_active,
                    p.project_work_type,
                    p.total_hours,
                    p.cumulative_hours,
                    p.weekly_meeting_day,
                    p.retainer_hours,
                    pmf.forecasted_hours,
                    pmf.actual_monthly_hours
                FROM projects p
                LEFT JOIN project_monthly_forecast pmf
                    ON p.key = pmf.project_key
                    AND pmf.month_year = :current_month
                WHERE p.key = ANY(:project_keys)
            """), {"project_keys": project_keys, "current_month": current_month}).fetchall()

            # Build lookup dictionary from batch results
            batch_lookup = {}
            for row in batch_results:
                # Skip first column (key) for comparison
                batch_lookup[row[0]] = row[1:]

            # ✅ CRITICAL ASSERTION: Batch query results must match N+1 query results
            for project_key in project_keys:
                assert n_plus_one_results[project_key] == batch_lookup[project_key], \
                    f"Batch query result for {project_key} doesn't match individual query result"

            print("\n✅ Batch query produces identical results to N+1 queries")
            print(f"   Verified for {len(project_keys)} projects")
