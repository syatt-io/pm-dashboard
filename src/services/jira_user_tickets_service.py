"""Service for fetching user's Jira tickets with caching."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from src.integrations.jira_mcp import JiraMCPClient
from config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class JiraTicket:
    """Simplified Jira ticket data structure."""

    key: str
    summary: str
    priority: str
    status: str
    project_key: str
    url: str
    created: datetime

    @classmethod
    def from_jira_issue(cls, issue: Dict[str, Any], jira_url: str) -> "JiraTicket":
        """Create JiraTicket from Jira API response."""
        fields = issue.get("fields", {})
        priority = fields.get("priority", {})
        status = fields.get("status", {})
        project = fields.get("project", {})
        created_str = fields.get("created", "")

        # Parse created date
        try:
            created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            created = datetime.now()

        return cls(
            key=issue.get("key", ""),
            summary=fields.get("summary", ""),
            priority=priority.get("name", "Medium") if priority else "Medium",
            status=status.get("name", "Unknown") if status else "Unknown",
            project_key=project.get("key", "") if project else "",
            url=f"{jira_url}/browse/{issue.get('key', '')}",
            created=created,
        )


class JiraUserTicketsService:
    """Service for fetching user's Jira tickets with 5-minute caching."""

    # Cache: {jira_account_id: (tickets, timestamp)}
    _cache: Dict[str, tuple[List[JiraTicket], datetime]] = {}
    _cache_ttl = timedelta(minutes=5)

    def __init__(self):
        """Initialize the service."""
        self.jira_client = JiraMCPClient(
            jira_url=settings.jira.url,
            username=settings.jira.username,
            api_token=settings.jira.api_token,
        )
        self.jira_url = settings.jira.url

    async def get_user_tickets(
        self, jira_account_id: str, use_cache: bool = True
    ) -> List[JiraTicket]:
        """
        Fetch tickets assigned to a specific Jira user.

        Args:
            jira_account_id: Jira account ID (e.g., from User.jira_account_id)
            use_cache: Whether to use cached results (default: True)

        Returns:
            List of JiraTicket objects sorted by priority then creation date
        """
        # Check cache first
        if use_cache and jira_account_id in self._cache:
            tickets, cached_at = self._cache[jira_account_id]
            if datetime.now() - cached_at < self._cache_ttl:
                logger.info(
                    f"Cache hit for user {jira_account_id} (cached {(datetime.now() - cached_at).seconds}s ago)"
                )
                return tickets

        # Cache miss or expired - fetch from Jira
        logger.info(f"Fetching tickets from Jira for user {jira_account_id}")

        try:
            # JQL query: fetch all tickets for user (no ORDER BY since we sort in Python)
            # Note: We fetch ALL tickets (up to 1000) then sort/limit in Python to ensure correct ordering
            jql = f'assignee = "{jira_account_id}"'

            # Fetch ALL tickets (up to Jira's max of 1000)
            # We need all tickets to properly sort before limiting to top 20
            result = await self.jira_client.search_issues(
                jql=jql,
                max_results=1000,  # Get all tickets (Jira max)
                expand_comments=False,
            )

            issues = result.get("issues", [])

            # Convert to JiraTicket objects
            tickets = [
                JiraTicket.from_jira_issue(issue, self.jira_url) for issue in issues
            ]

            # Sort by priority (HIGH -> MEDIUM -> LOW) then by creation date (newest first)
            tickets = self._sort_tickets(tickets)

            # Limit to top 20 after sorting
            tickets = tickets[:20]

            # Update cache
            self._cache[jira_account_id] = (tickets, datetime.now())

            logger.info(
                f"Fetched {len(issues)} total tickets, returning top {len(tickets)} for user {jira_account_id}"
            )
            return tickets

        except Exception as e:
            logger.error(f"Error fetching tickets for user {jira_account_id}: {e}")
            # If we have stale cache, return it as fallback
            if jira_account_id in self._cache:
                logger.warning(
                    f"Returning stale cache for user {jira_account_id} due to error"
                )
                tickets, _ = self._cache[jira_account_id]
                return tickets
            return []

    def _sort_tickets(self, tickets: List[JiraTicket]) -> List[JiraTicket]:
        """
        Sort tickets by priority (HIGH -> MEDIUM -> LOW) then by creation date (newest first).

        Args:
            tickets: List of JiraTicket objects

        Returns:
            Sorted list of tickets
        """
        priority_order = {
            "Highest": 0,
            "High": 1,
            "Medium": 2,
            "Low": 3,
            "Lowest": 4,
        }

        # Sort by priority (ascending order value) then by created (descending)
        return sorted(
            tickets,
            key=lambda t: (
                priority_order.get(t.priority, 5),  # Unknown priorities go last
                -t.created.timestamp(),  # Negative for descending (newest first)
            ),
        )

    def format_tickets_for_slack(self, tickets: List[JiraTicket]) -> str:
        """
        Format tickets for Slack display with emojis and links.

        Args:
            tickets: List of JiraTicket objects

        Returns:
            Formatted Slack message string
        """
        if not tickets:
            return "🎉 You have no tickets assigned! Time to enjoy some coffee ☕"

        # Priority emojis
        priority_emoji = {
            "Highest": "🔴",
            "High": "🟠",
            "Medium": "🟡",
            "Low": "🟢",
            "Lowest": "🔵",
        }

        lines = [f"🎯 *Your Jira Tickets ({len(tickets)}):*\n"]

        for ticket in tickets:
            emoji = priority_emoji.get(ticket.priority, "⚪")
            # Slack link format: <url|text>
            lines.append(
                f"{emoji} [{ticket.priority.upper()}] <{ticket.url}|{ticket.key}>: {ticket.summary}"
            )
            lines.append(f"   Status: {ticket.status} | Project: {ticket.project_key}")
            lines.append("")  # Empty line for spacing

        return "\n".join(lines)

    def clear_cache(self, jira_account_id: Optional[str] = None):
        """
        Clear cache for a specific user or all users.

        Args:
            jira_account_id: If provided, clear cache for this user only.
                           If None, clear all cache.
        """
        if jira_account_id:
            self._cache.pop(jira_account_id, None)
            logger.info(f"Cleared cache for user {jira_account_id}")
        else:
            self._cache.clear()
            logger.info("Cleared all ticket cache")
