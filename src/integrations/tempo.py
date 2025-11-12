"""
Tempo API v4 Integration

This module provides direct integration with Tempo API v4 for accurate time tracking.
IMPORTANT: Do not use MCP Tempo tools - they are incomplete and return incorrect data.

Based on: /Users/msamimi/syatt/projects/dev-learnings/Jira-integrations/TEMPO_API_INTEGRATION_GUIDE.md
"""

import os
import re
import base64
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import requests

from src.utils.retry_logic import retry_with_backoff

logger = logging.getLogger(__name__)


class TempoAPIClient:
    """Client for Tempo API v4 with Jira issue resolution"""

    def __init__(self):
        self.tempo_token = os.getenv("TEMPO_API_TOKEN")
        self.jira_url = os.getenv("JIRA_URL")
        self.jira_username = os.getenv("JIRA_USERNAME")
        self.jira_token = os.getenv("JIRA_API_TOKEN")

        if not self.tempo_token:
            raise ValueError("TEMPO_API_TOKEN environment variable is required")
        if not all([self.jira_url, self.jira_username, self.jira_token]):
            raise ValueError("JIRA_URL, JIRA_USERNAME, and JIRA_API_TOKEN are required")

        self.tempo_base_url = "https://api.tempo.io/4"
        self.tempo_headers = {
            "Authorization": f"Bearer {self.tempo_token}",
            "Accept": "application/json",
        }

        # Setup Jira Basic Auth
        credentials = f"{self.jira_username}:{self.jira_token}"
        encoded_creds = base64.b64encode(credentials.encode()).decode()
        self.jira_headers = {
            "Authorization": f"Basic {encoded_creds}",
            "Accept": "application/json",
        }

        # Cache for issue ID to key mappings
        self.issue_cache: Dict[str, Optional[str]] = {}

        # Cache for account ID to display name mappings
        self.account_cache: Dict[str, Optional[str]] = {}

        # Cache for account ID to team mappings
        self.team_cache: Dict[str, Optional[str]] = {}

        # Cache for issue key to epic key mappings
        self.epic_cache: Dict[str, Optional[str]] = {}

        # Cache for project key to numeric project ID mappings
        self.project_id_cache: Dict[str, Optional[str]] = {}

        # Rate limiting: Track last request time to avoid hitting Jira API limits
        self.last_jira_request_time = 0.0
        self.min_request_interval = 0.1  # 100ms between Jira API calls (max 10 req/sec)

    def _rate_limit(self):
        """Enforce rate limiting for Jira API calls."""
        current_time = time.time()
        time_since_last_request = current_time - self.last_jira_request_time

        if time_since_last_request < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last_request
            time.sleep(sleep_time)

        self.last_jira_request_time = time.time()

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    def get_project_id(self, project_key: str) -> Optional[str]:
        """
        Get numeric project ID from Jira API using project key.

        Args:
            project_key: Jira project key (e.g., "RNWL", "SUBS")

        Returns:
            Numeric project ID (e.g., "10440") or None if not found
        """
        if project_key in self.project_id_cache:
            return self.project_id_cache[project_key]

        try:
            # Rate limit to avoid hitting Jira API limits
            self._rate_limit()

            url = f"{self.jira_url}/rest/api/3/project/{project_key}"
            response = requests.get(url, headers=self.jira_headers, timeout=10)
            response.raise_for_status()

            project_data = response.json()
            project_id = project_data.get("id")

            self.project_id_cache[project_key] = project_id
            logger.debug(f"Resolved project {project_key} to ID {project_id}")
            return project_id

        except Exception as e:
            logger.debug(f"Error getting project ID for {project_key}: {e}")
            self.project_id_cache[project_key] = None
            return None

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    def get_issue_key_from_jira(self, issue_id: str) -> Optional[str]:
        """
        Resolve Jira issue ID to issue key via Jira API with rate limiting.

        Args:
            issue_id: Jira issue ID (numeric)

        Returns:
            Issue key (e.g., "SUBS-123") or None if not found
        """
        if issue_id in self.issue_cache:
            return self.issue_cache[issue_id]

        try:
            # Rate limit to avoid hitting Jira API limits
            self._rate_limit()

            url = f"{self.jira_url}/rest/api/3/issue/{issue_id}"
            response = requests.get(url, headers=self.jira_headers, timeout=10)
            response.raise_for_status()

            issue_data = response.json()
            issue_key = issue_data.get("key")

            self.issue_cache[issue_id] = issue_key
            return issue_key

        except Exception as e:
            logger.debug(f"Error getting issue key for ID {issue_id}: {e}")
            self.issue_cache[issue_id] = None
            return None

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    def get_epic_from_jira(self, issue_key: str) -> Optional[str]:
        """
        Get epic key from Jira issue via Epic Link or parent hierarchy.

        Checks two places for epic:
        1. customfield_10014 (Epic Link field) - legacy approach
        2. parent field (modern Jira hierarchy) - checks if parent is an Epic

        Args:
            issue_key: Jira issue key (e.g., "SUBS-123")

        Returns:
            Epic key (e.g., "SUBS-456") or None if not found
        """
        # Check cache first
        if issue_key in self.epic_cache:
            return self.epic_cache[issue_key]

        try:
            # Rate limit to avoid hitting Jira API limits
            self._rate_limit()

            url = f"{self.jira_url}/rest/api/3/issue/{issue_key}"
            params = {"fields": "customfield_10014,parent"}
            response = requests.get(
                url, headers=self.jira_headers, params=params, timeout=10
            )
            response.raise_for_status()

            issue_data = response.json()
            fields = issue_data.get("fields", {})

            # Try Epic Link field first (legacy)
            epic_key = fields.get("customfield_10014")
            # Validate it's actually an issue key (PROJECT-NUMBER format), not a date or other string
            if epic_key and isinstance(epic_key, str) and "-" in epic_key:
                # Check if it looks like an issue key (contains letters before dash)
                parts = epic_key.split("-")
                if len(parts) == 2 and parts[0].isalpha() and parts[1].isdigit():
                    self.epic_cache[issue_key] = epic_key
                    return epic_key

            # Try parent field (modern Jira hierarchy)
            parent = fields.get("parent")
            if parent:
                parent_key = parent.get("key")
                # Check if parent is an Epic
                parent_fields = parent.get("fields", {})
                parent_issue_type = parent_fields.get("issuetype", {})
                if parent_issue_type.get("name") == "Epic":
                    self.epic_cache[issue_key] = parent_key
                    return parent_key

            # Cache None result to avoid re-querying
            self.epic_cache[issue_key] = None
            return None

        except Exception as e:
            logger.debug(f"Error getting epic for issue {issue_key}: {e}")
            # Cache None for failed lookups to avoid retrying
            self.epic_cache[issue_key] = None
            return None

    def get_epic_details_from_jira(self, epic_key: str) -> Optional[Dict]:
        """
        Get epic details from Jira including summary and other fields.

        Args:
            epic_key: Jira epic key (e.g., "RNWL-123")

        Returns:
            Dict with epic details including 'summary' field, or None if not found
        """
        try:
            # Rate limit to avoid hitting Jira API limits
            self._rate_limit()

            url = f"{self.jira_url}/rest/api/3/issue/{epic_key}"
            params = {"fields": "summary,issuetype"}
            response = requests.get(
                url, headers=self.jira_headers, params=params, timeout=10
            )
            response.raise_for_status()

            issue_data = response.json()
            fields = issue_data.get("fields", {})

            return {
                "key": epic_key,
                "summary": fields.get("summary", epic_key),
                "issuetype": fields.get("issuetype", {}).get("name", ""),
            }

        except Exception as e:
            logger.debug(f"Error getting epic details for {epic_key}: {e}")
            return None

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    def get_user_name(self, account_id: str) -> Optional[str]:
        """
        Resolve Jira account ID to user display name via Jira API with rate limiting.

        Args:
            account_id: Jira account ID (e.g., "abc123")

        Returns:
            User display name (e.g., "Mike Samimi") or None if not found
        """
        if account_id in self.account_cache:
            return self.account_cache[account_id]

        try:
            # Rate limit to avoid hitting Jira API limits
            self._rate_limit()

            url = f"{self.jira_url}/rest/api/3/user"
            params = {"accountId": account_id}
            response = requests.get(
                url, headers=self.jira_headers, params=params, timeout=10
            )
            response.raise_for_status()

            user_data = response.json()
            display_name = user_data.get("displayName")

            self.account_cache[account_id] = display_name
            return display_name

        except Exception as e:
            logger.debug(f"Error getting user name for account ID {account_id}: {e}")
            self.account_cache[account_id] = None
            return None

    def get_user_team(self, account_id: str) -> Optional[str]:
        """
        Look up user's team from database via account ID.

        Args:
            account_id: Jira account ID (e.g., "abc123")

        Returns:
            Team name (e.g., "FE Devs", "BE Devs", "PMs", etc.) or None if not found
        """
        if account_id in self.team_cache:
            return self.team_cache[account_id]

        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            from src.models import UserTeam

            # Get database URL
            database_url = os.getenv("DATABASE_URL")
            if not database_url:
                logger.warning("DATABASE_URL not set, cannot look up user teams")
                self.team_cache[account_id] = None
                return None

            # Query database for user team
            engine = create_engine(database_url)
            Session = sessionmaker(bind=engine)
            session = Session()

            try:
                user_team = (
                    session.query(UserTeam).filter_by(account_id=account_id).first()
                )
                if user_team:
                    team = user_team.team
                    self.team_cache[account_id] = team
                    return team
                else:
                    # User not found in team assignments
                    logger.debug(
                        f"No team assignment found for account ID {account_id}"
                    )
                    self.team_cache[account_id] = "Unassigned"
                    return "Unassigned"
            finally:
                session.close()

        except Exception as e:
            logger.debug(f"Error getting team for account ID {account_id}: {e}")
            self.team_cache[account_id] = None
            return None

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    def get_worklogs(
        self,
        from_date: str,
        to_date: str,
        limit: int = 5000,
        project_key: Optional[str] = None,
    ) -> List[Dict]:
        """
        Fetch all worklogs for a date range with pagination.

        Args:
            from_date: Start date in YYYY-MM-DD format
            to_date: End date in YYYY-MM-DD format
            limit: Maximum results per request (default 5000, max allowed)
            project_key: Optional project key to filter worklogs (e.g., "SUBS", "RNWL")

        Returns:
            List of worklog dictionaries
        """
        url = f"{self.tempo_base_url}/worklogs"
        params = {"from": from_date, "to": to_date, "limit": limit}

        # Tempo API v4 requires numeric projectId (not projectKey string)
        # Get numeric project ID from Jira and add to query params for server-side filtering
        if project_key:
            project_id = self.get_project_id(project_key)
            if project_id:
                params["projectId"] = project_id
                logger.info(
                    f"Filtering worklogs by project {project_key} (ID: {project_id})"
                )
            else:
                logger.warning(
                    f"Could not get project ID for {project_key}, fetching all worklogs"
                )

        all_worklogs = []

        try:
            # First request
            response = requests.get(
                url, headers=self.tempo_headers, params=params, timeout=30
            )
            response.raise_for_status()
            data = response.json()

            results = data.get("results", [])
            all_worklogs.extend(results)
            logger.info(f"Fetched {len(results)} worklogs from Tempo API")

            # Handle pagination
            while data.get("metadata", {}).get("next"):
                next_url = data["metadata"]["next"]
                logger.debug(f"Fetching next page: {next_url}")

                response = requests.get(
                    next_url, headers=self.tempo_headers, timeout=30
                )
                response.raise_for_status()
                data = response.json()

                results = data.get("results", [])
                all_worklogs.extend(results)
                logger.info(
                    f"Fetched {len(results)} more worklogs (total: {len(all_worklogs)})"
                )

            return all_worklogs

        except Exception as e:
            logger.error(f"Error fetching worklogs from Tempo: {e}")
            raise

    def process_worklogs(
        self, worklogs: List[Dict]
    ) -> Tuple[Dict[str, float], int, int]:
        """
        Process worklogs to calculate hours per project using dual resolution:
        1. Fast path: Extract issue key from description
        2. Complete path: Resolve issue ID via Jira API

        Args:
            worklogs: List of worklog dictionaries from Tempo API

        Returns:
            Tuple of (project_hours_dict, processed_count, skipped_count)
        """
        project_hours = defaultdict(float)
        processed = 0
        skipped = 0

        # Issue key pattern: PROJECT-NUMBER (e.g., SUBS-123)
        issue_pattern = re.compile(r"([A-Z]+-\d+)")

        for worklog in worklogs:
            description = worklog.get("description", "")
            issue_key = None

            # Fast path: Extract from description
            issue_match = issue_pattern.search(description)
            if issue_match:
                issue_key = issue_match.group(1)
            else:
                # Complete path: Jira API lookup
                issue_id = worklog.get("issue", {}).get("id")
                if issue_id:
                    issue_key = self.get_issue_key_from_jira(str(issue_id))

            if issue_key:
                processed += 1
                # Extract project key (everything before the dash)
                project_key = issue_key.split("-")[0]

                # Convert seconds to hours
                seconds = worklog.get("timeSpentSeconds", 0)
                hours = seconds / 3600

                project_hours[project_key] += hours
            else:
                skipped += 1
                logger.debug(f"Skipped worklog: {description[:50]}...")

        logger.info(f"Processed {processed} worklogs, skipped {skipped}")
        logger.info(f"Unique Jira API calls: {len(self.issue_cache)}")

        return dict(project_hours), processed, skipped

    def get_current_month_hours(self) -> Dict[str, float]:
        """
        Get hours for the current calendar month.

        Returns:
            Dictionary mapping project keys to hours
        """
        now = datetime.now()
        first_day = now.replace(day=1).strftime("%Y-%m-%d")
        last_day = now.strftime("%Y-%m-%d")

        logger.info(f"Fetching current month hours: {first_day} to {last_day}")

        worklogs = self.get_worklogs(first_day, last_day)
        project_hours, processed, skipped = self.process_worklogs(worklogs)

        logger.info(f"Current month summary:")
        for project, hours in sorted(project_hours.items()):
            logger.info(f"  {project}: {hours:.2f}h")

        return project_hours

    def get_year_to_date_hours(self) -> Dict[str, float]:
        """
        Get cumulative hours for the current year.

        Returns:
            Dictionary mapping project keys to hours
        """
        now = datetime.now()
        first_day_of_year = now.replace(month=1, day=1).strftime("%Y-%m-%d")
        today = now.strftime("%Y-%m-%d")

        logger.info(f"Fetching YTD hours: {first_day_of_year} to {today}")

        worklogs = self.get_worklogs(first_day_of_year, today)
        project_hours, processed, skipped = self.process_worklogs(worklogs)

        logger.info(f"YTD summary:")
        for project, hours in sorted(project_hours.items()):
            logger.info(f"  {project}: {hours:.2f}h")

        return project_hours

    def get_all_time_hours(self) -> Dict[str, float]:
        """
        Get cumulative hours for all time (no date filter).
        Fetches ALL worklogs from Tempo without date restrictions.

        Returns:
            Dictionary mapping project keys to hours
        """
        logger.info("Fetching all-time hours (no date filter)")

        # Use Tempo API to get all worklogs without date filter
        # Note: Tempo API requires date range, so we use a very old start date
        # This assumes projects started no earlier than 2020
        start_date = "2020-01-01"
        today = datetime.now().strftime("%Y-%m-%d")

        worklogs = self.get_worklogs(start_date, today)
        project_hours, processed, skipped = self.process_worklogs(worklogs)

        logger.info(f"All-time summary:")
        for project, hours in sorted(project_hours.items()):
            logger.info(f"  {project}: {hours:.2f}h")

        return project_hours

    def get_date_range_hours(self, from_date: str, to_date: str) -> Dict[str, float]:
        """
        Get hours for a specific date range.

        Args:
            from_date: Start date in YYYY-MM-DD format
            to_date: End date in YYYY-MM-DD format

        Returns:
            Dictionary mapping project keys to hours
        """
        logger.info(f"Fetching hours for date range: {from_date} to {to_date}")

        worklogs = self.get_worklogs(from_date, to_date)
        project_hours, processed, skipped = self.process_worklogs(worklogs)

        return project_hours
