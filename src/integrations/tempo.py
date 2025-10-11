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
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import requests

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
            "Accept": "application/json"
        }

        # Setup Jira Basic Auth
        credentials = f"{self.jira_username}:{self.jira_token}"
        encoded_creds = base64.b64encode(credentials.encode()).decode()
        self.jira_headers = {
            "Authorization": f"Basic {encoded_creds}",
            "Accept": "application/json"
        }

        # Cache for issue ID to key mappings
        self.issue_cache: Dict[str, Optional[str]] = {}

        # Cache for account ID to display name mappings
        self.account_cache: Dict[str, Optional[str]] = {}

    def get_issue_key_from_jira(self, issue_id: str) -> Optional[str]:
        """
        Resolve Jira issue ID to issue key via Jira API.

        Args:
            issue_id: Jira issue ID (numeric)

        Returns:
            Issue key (e.g., "SUBS-123") or None if not found
        """
        if issue_id in self.issue_cache:
            return self.issue_cache[issue_id]

        try:
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

    def get_user_name(self, account_id: str) -> Optional[str]:
        """
        Resolve Jira account ID to user display name via Jira API.

        Args:
            account_id: Jira account ID (e.g., "abc123")

        Returns:
            User display name (e.g., "Mike Samimi") or None if not found
        """
        if account_id in self.account_cache:
            return self.account_cache[account_id]

        try:
            url = f"{self.jira_url}/rest/api/3/user"
            params = {"accountId": account_id}
            response = requests.get(url, headers=self.jira_headers, params=params, timeout=10)
            response.raise_for_status()

            user_data = response.json()
            display_name = user_data.get("displayName")

            self.account_cache[account_id] = display_name
            return display_name

        except Exception as e:
            logger.debug(f"Error getting user name for account ID {account_id}: {e}")
            self.account_cache[account_id] = None
            return None

    def get_worklogs(
        self,
        from_date: str,
        to_date: str,
        limit: int = 5000
    ) -> List[Dict]:
        """
        Fetch all worklogs for a date range with pagination.

        Args:
            from_date: Start date in YYYY-MM-DD format
            to_date: End date in YYYY-MM-DD format
            limit: Maximum results per request (default 5000, max allowed)

        Returns:
            List of worklog dictionaries
        """
        url = f"{self.tempo_base_url}/worklogs"
        params = {
            "from": from_date,
            "to": to_date,
            "limit": limit
        }

        all_worklogs = []

        try:
            # First request
            response = requests.get(
                url,
                headers=self.tempo_headers,
                params=params,
                timeout=30
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

                response = requests.get(next_url, headers=self.tempo_headers, timeout=30)
                response.raise_for_status()
                data = response.json()

                results = data.get("results", [])
                all_worklogs.extend(results)
                logger.info(f"Fetched {len(results)} more worklogs (total: {len(all_worklogs)})")

            return all_worklogs

        except Exception as e:
            logger.error(f"Error fetching worklogs from Tempo: {e}")
            raise

    def process_worklogs(self, worklogs: List[Dict]) -> Tuple[Dict[str, float], int, int]:
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
        issue_pattern = re.compile(r'([A-Z]+-\d+)')

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
