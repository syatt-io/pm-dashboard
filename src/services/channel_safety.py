"""Channel safety validator to prevent posting to client-facing channels.

This module provides the ChannelSafetyValidator class which ensures that
escalation notifications are only posted to internal channels, never to
channels that include clients.
"""

import logging
from typing import Optional, List, Set
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)


class ChannelSafetyValidator:
    """Validates that channels are safe for posting escalation notifications.

    This class prevents notifications from being posted to client-facing channels
    by checking against a whitelist of internal-only channel IDs stored in the
    project_resource_mappings table.
    """

    def __init__(self, db: Session):
        """Initialize the channel safety validator.

        Args:
            db: Database session for querying project mappings
        """
        self.db = db
        self._internal_channels_cache: Optional[Set[str]] = None

    def is_channel_safe(
        self, channel_id: str, project_key: Optional[str] = None
    ) -> bool:
        """Check if a channel is safe for posting escalation notifications.

        A channel is considered safe if:
        1. It's in the internal_slack_channels list for the project, OR
        2. If project_key is None, check if channel is internal for ANY project

        Args:
            channel_id: Slack channel ID (e.g., "C1234567890")
            project_key: Optional project key to check against specific project

        Returns:
            True if channel is safe for escalation notifications, False otherwise
        """
        if not channel_id:
            logger.warning("Empty channel_id provided to is_channel_safe()")
            return False

        try:
            internal_channels = self._get_internal_channels(project_key)

            if not internal_channels:
                # No internal channels configured - fail safe by rejecting
                logger.warning(
                    f"No internal channels configured for project_key={project_key}. "
                    f"Rejecting channel {channel_id} for safety."
                )
                return False

            is_safe = channel_id in internal_channels

            if not is_safe:
                logger.warning(
                    f"Channel {channel_id} is NOT in internal channels list for "
                    f"project_key={project_key}. Blocking escalation notification."
                )

            return is_safe

        except Exception as e:
            logger.error(
                f"Error checking channel safety for {channel_id}: {e}", exc_info=True
            )
            # Fail safe - reject channel if we can't verify it
            return False

    def get_safe_channels_for_project(self, project_key: str) -> List[str]:
        """Get list of safe internal channels for a project.

        Args:
            project_key: Project key (e.g., "SUBS", "BC")

        Returns:
            List of safe channel IDs for the project
        """
        try:
            internal_channels = self._get_internal_channels(project_key)
            return list(internal_channels) if internal_channels else []
        except Exception as e:
            logger.error(
                f"Error getting safe channels for project {project_key}: {e}",
                exc_info=True,
            )
            return []

    def _get_internal_channels(self, project_key: Optional[str] = None) -> Set[str]:
        """Get internal channels from database.

        Args:
            project_key: Optional project key to filter by

        Returns:
            Set of internal channel IDs
        """
        try:
            if project_key:
                # Get internal channels for specific project
                query = text(
                    """
                    SELECT internal_slack_channels
                    FROM project_resource_mappings
                    WHERE project_key = :project_key
                    AND internal_slack_channels IS NOT NULL
                """
                )
                result = self.db.execute(query, {"project_key": project_key}).fetchone()

                if result and result.internal_slack_channels:
                    # Parse comma-separated channel IDs
                    channels = [
                        ch.strip() for ch in result.internal_slack_channels.split(",")
                    ]
                    return set(ch for ch in channels if ch)  # Filter empty strings

                return set()
            else:
                # Get ALL internal channels from all projects (for cache)
                if self._internal_channels_cache is not None:
                    return self._internal_channels_cache

                query = text(
                    """
                    SELECT internal_slack_channels
                    FROM project_resource_mappings
                    WHERE internal_slack_channels IS NOT NULL
                """
                )
                results = self.db.execute(query).fetchall()

                all_channels = set()
                for row in results:
                    if row.internal_slack_channels:
                        channels = [
                            ch.strip() for ch in row.internal_slack_channels.split(",")
                        ]
                        all_channels.update(ch for ch in channels if ch)

                self._internal_channels_cache = all_channels
                return all_channels

        except Exception as e:
            logger.error(
                f"Error fetching internal channels from database: {e}", exc_info=True
            )
            return set()

    def clear_cache(self):
        """Clear the internal channels cache.

        Call this after updating project_resource_mappings to ensure
        fresh data is loaded on next check.
        """
        self._internal_channels_cache = None
        logger.info("Internal channels cache cleared")

    def validate_and_filter_channels(
        self, channel_ids: List[str], project_key: Optional[str] = None
    ) -> List[str]:
        """Filter a list of channels to only include safe internal channels.

        Args:
            channel_ids: List of channel IDs to validate
            project_key: Optional project key for context

        Returns:
            List of safe channel IDs (subset of input)
        """
        safe_channels = []

        for channel_id in channel_ids:
            if self.is_channel_safe(channel_id, project_key):
                safe_channels.append(channel_id)
            else:
                logger.warning(
                    f"Filtered out unsafe channel {channel_id} from escalation targets "
                    f"(project_key={project_key})"
                )

        return safe_channels

    def get_channel_safety_report(self, channel_id: str) -> dict:
        """Get detailed safety information about a channel.

        Useful for debugging and admin interfaces.

        Args:
            channel_id: Channel ID to check

        Returns:
            Dictionary with safety information
        """
        try:
            # Check all projects for this channel
            query = text(
                """
                SELECT project_key, internal_slack_channels
                FROM project_resource_mappings
                WHERE internal_slack_channels LIKE :channel_pattern
            """
            )
            results = self.db.execute(
                query, {"channel_pattern": f"%{channel_id}%"}
            ).fetchall()

            projects_with_channel = []
            for row in results:
                channels = [ch.strip() for ch in row.internal_slack_channels.split(",")]
                if channel_id in channels:
                    projects_with_channel.append(row.project_key)

            is_safe = len(projects_with_channel) > 0

            return {
                "channel_id": channel_id,
                "is_safe": is_safe,
                "safe_for_projects": projects_with_channel,
                "status": "safe" if is_safe else "unsafe",
                "message": (
                    f"Channel is marked as internal for projects: {', '.join(projects_with_channel)}"
                    if is_safe
                    else "Channel is NOT marked as internal for any project. Do not send escalation notifications."
                ),
            }

        except Exception as e:
            logger.error(
                f"Error generating safety report for {channel_id}: {e}", exc_info=True
            )
            return {
                "channel_id": channel_id,
                "is_safe": False,
                "error": str(e),
                "status": "error",
            }
