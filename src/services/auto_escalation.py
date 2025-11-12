"""Auto-escalation service for proactive insights.

This service handles the core escalation logic:
1. Detects stale insights that need escalation
2. Determines appropriate escalation level based on age
3. Executes escalation actions (DM, channel post, GitHub comment)
4. Records all actions in audit trail
5. Respects user preferences and rate limits
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from slack_sdk import WebClient

from config.settings import settings
from src.models.proactive_insight import ProactiveInsight
from src.models.escalation import EscalationHistory, EscalationPreferences
from src.models.user import User
from src.services.channel_safety import ChannelSafetyValidator
from src.integrations.github_client import GitHubClient

logger = logging.getLogger(__name__)


class AutoEscalationService:
    """Service for automatically escalating stale proactive insights."""

    def __init__(
        self,
        db: Session,
        slack_client: Optional[WebClient] = None,
        github_client: Optional[GitHubClient] = None,
    ):
        """Initialize auto-escalation service.

        Args:
            db: Database session
            slack_client: Optional Slack WebClient for DMs/channels
            github_client: Optional GitHubClient for PR comments
        """
        self.db = db
        self.slack_client = slack_client or WebClient(
            token=settings.notifications.slack_bot_token
        )
        self.github_client = github_client or GitHubClient(
            api_token=settings.github.api_token,
            organization=settings.github.organization,
            app_id=settings.github.app_id,
            private_key=settings.github.private_key,
            installation_id=settings.github.installation_id,
        )
        self.channel_validator = ChannelSafetyValidator(db)

    def run_escalation_check(self) -> Dict[str, Any]:
        """Run escalation check for all active insights.

        Returns:
            Dict with statistics about escalations performed
        """
        logger.info("Starting auto-escalation check...")

        stats = {
            "total_checked": 0,
            "escalations_performed": 0,
            "dm_sent": 0,
            "channel_posts": 0,
            "github_comments": 0,
            "errors": 0,
            "skipped_no_prefs": 0,
            "skipped_disabled": 0,
        }

        try:
            # Get all active (non-dismissed, non-acted-on) insights
            active_insights = self._get_active_insights()
            stats["total_checked"] = len(active_insights)

            logger.info(f"Found {len(active_insights)} active insights to check")

            for insight in active_insights:
                try:
                    result = self._process_insight_escalation(insight)
                    if result["escalated"]:
                        stats["escalations_performed"] += 1
                        stats["dm_sent"] += result.get("dm_sent", 0)
                        stats["channel_posts"] += result.get("channel_posts", 0)
                        stats["github_comments"] += result.get("github_comments", 0)
                    elif result.get("skipped_reason") == "no_prefs":
                        stats["skipped_no_prefs"] += 1
                    elif result.get("skipped_reason") == "disabled":
                        stats["skipped_disabled"] += 1

                except Exception as e:
                    logger.error(
                        f"Error processing insight {insight.id}: {e}", exc_info=True
                    )
                    stats["errors"] += 1

            logger.info(f"Escalation check complete: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Critical error in escalation check: {e}", exc_info=True)
            stats["errors"] += 1
            return stats

    def _get_active_insights(self) -> List[ProactiveInsight]:
        """Get all active insights that could need escalation.

        Returns:
            List of active ProactiveInsight objects
        """
        return (
            self.db.query(ProactiveInsight)
            .filter(
                ProactiveInsight.dismissed_at.is_(None),
                ProactiveInsight.acted_on_at.is_(None),
                ProactiveInsight.insight_type
                == "stale_pr",  # Start with stale PRs only
            )
            .all()
        )

    def _process_insight_escalation(self, insight: ProactiveInsight) -> Dict[str, Any]:
        """Process escalation for a single insight.

        Args:
            insight: ProactiveInsight to potentially escalate

        Returns:
            Dict with escalation results
        """
        result = {
            "escalated": False,
            "dm_sent": 0,
            "channel_posts": 0,
            "github_comments": 0,
            "skipped_reason": None,
        }

        # Get user preferences
        prefs = (
            self.db.query(EscalationPreferences)
            .filter_by(user_id=insight.user_id)
            .first()
        )

        if not prefs:
            logger.debug(
                f"No escalation preferences for user {insight.user_id}, "
                f"skipping insight {insight.id}"
            )
            result["skipped_reason"] = "no_prefs"
            return result

        if not prefs.enable_auto_escalation:
            logger.debug(
                f"Auto-escalation disabled for user {insight.user_id}, "
                f"skipping insight {insight.id}"
            )
            result["skipped_reason"] = "disabled"
            return result

        # Determine escalation level based on age
        # Handle both naive and aware datetimes
        created_at = insight.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        days_old = (datetime.now(timezone.utc) - created_at).days
        target_level = self._determine_escalation_level(days_old, prefs)

        if target_level == 0:
            logger.debug(
                f"Insight {insight.id} ({days_old} days old) "
                f"not yet ready for escalation"
            )
            return result

        # Check if already escalated to this level
        if insight.escalation_level >= target_level:
            logger.debug(
                f"Insight {insight.id} already at level {insight.escalation_level}, "
                f"target is {target_level}"
            )
            return result

        # Check rate limiting (don't escalate more than once per day)
        if insight.last_escalated_at:
            last_escalated = self._ensure_timezone_aware(insight.last_escalated_at)
            hours_since_last = (
                datetime.now(timezone.utc) - last_escalated
            ).total_seconds() / 3600
            if hours_since_last < 24:
                logger.debug(
                    f"Insight {insight.id} escalated {hours_since_last:.1f}h ago, "
                    f"rate limiting"
                )
                return result

        # Execute escalation actions based on level and preferences
        logger.info(
            f"Escalating insight {insight.id} to level {target_level} "
            f"(current: {insight.escalation_level})"
        )

        escalation_results = self._execute_escalation(insight, target_level, prefs)

        # Update insight escalation tracking
        insight.escalation_level = target_level
        insight.escalation_count += 1
        insight.last_escalated_at = datetime.now(timezone.utc)
        self.db.commit()

        result["escalated"] = True
        result.update(escalation_results)
        return result

    def _ensure_timezone_aware(self, dt: datetime) -> datetime:
        """Ensure datetime is timezone-aware (convert naive to UTC).

        Args:
            dt: Datetime to check

        Returns:
            Timezone-aware datetime
        """
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    def _determine_escalation_level(
        self, days_old: int, prefs: EscalationPreferences
    ) -> int:
        """Determine appropriate escalation level based on age.

        Args:
            days_old: Days since insight was created
            prefs: User's escalation preferences

        Returns:
            Escalation level (0-3)
        """
        if days_old >= prefs.critical_threshold_days:
            return 3  # Critical (GitHub + channel + DM)
        elif days_old >= prefs.channel_threshold_days:
            return 2  # Channel post
        elif days_old >= prefs.dm_threshold_days:
            return 1  # DM only
        else:
            return 0  # No escalation yet

    def _execute_escalation(
        self, insight: ProactiveInsight, target_level: int, prefs: EscalationPreferences
    ) -> Dict[str, int]:
        """Execute escalation actions based on level and preferences.

        Args:
            insight: Insight to escalate
            target_level: Target escalation level (1-3)
            prefs: User's escalation preferences

        Returns:
            Dict with counts of actions taken
        """
        results = {"dm_sent": 0, "channel_posts": 0, "github_comments": 0}

        # Get user info
        user = self.db.query(User).filter_by(id=insight.user_id).first()
        if not user:
            logger.error(f"User {insight.user_id} not found for insight {insight.id}")
            return results

        # Level 1: DM to user
        if target_level >= 1 and prefs.enable_dm_escalation:
            if self._send_dm_escalation(insight, user, target_level):
                results["dm_sent"] = 1

        # Level 2: Post to channel
        if target_level >= 2 and prefs.enable_channel_escalation:
            if self._send_channel_escalation(insight, user, target_level):
                results["channel_posts"] = 1

        # Level 3: GitHub PR comment
        if target_level >= 3 and prefs.enable_github_escalation:
            if self._send_github_escalation(insight, user, target_level):
                results["github_comments"] = 1

        return results

    def _send_dm_escalation(
        self, insight: ProactiveInsight, user: User, level: int
    ) -> bool:
        """Send DM escalation notification to user.

        Args:
            insight: Insight being escalated
            user: User to notify
            level: Escalation level

        Returns:
            True if successful, False otherwise
        """
        if not user.slack_user_id:
            logger.warning(f"User {user.id} has no slack_user_id, cannot send DM")
            self._record_escalation(
                insight,
                "dm",
                level,
                user.slack_user_id or "unknown",
                None,
                False,
                "User has no slack_user_id",
            )
            return False

        try:
            # Build escalation message
            created_at = self._ensure_timezone_aware(insight.created_at)
            days_old = (datetime.now(timezone.utc) - created_at).days
            message = self._build_dm_message(insight, days_old, level)

            # Send DM via Slack WebClient
            self.slack_client.chat_postMessage(channel=user.slack_user_id, text=message)

            # Record success
            self._record_escalation(
                insight, "dm", level, user.slack_user_id, message, True, None
            )

            logger.info(
                f"Sent DM escalation for insight {insight.id} "
                f"to user {user.slack_user_id}"
            )
            return True

        except Exception as e:
            logger.error(
                f"Error sending DM escalation for insight {insight.id}: {e}",
                exc_info=True,
            )
            self._record_escalation(
                insight, "dm", level, user.slack_user_id, None, False, str(e)
            )
            return False

    def _send_channel_escalation(
        self, insight: ProactiveInsight, user: User, level: int
    ) -> bool:
        """Send channel escalation notification.

        Args:
            insight: Insight being escalated
            user: User who owns the insight
            level: Escalation level

        Returns:
            True if successful, False otherwise
        """
        # Get project-specific internal channels
        if not insight.project_key:
            logger.warning(
                f"Insight {insight.id} has no project_key, "
                f"cannot determine safe channel"
            )
            return False

        safe_channels = self.channel_validator.get_safe_channels_for_project(
            insight.project_key
        )

        if not safe_channels:
            logger.warning(
                f"No safe channels configured for project {insight.project_key}, "
                f"skipping channel escalation"
            )
            self._record_escalation(
                insight,
                "channel",
                level,
                f"project:{insight.project_key}",
                None,
                False,
                "No safe channels configured for project",
            )
            return False

        # Use first safe channel (in production, might want to make this configurable)
        channel_id = safe_channels[0]

        try:
            # Build escalation message
            created_at = self._ensure_timezone_aware(insight.created_at)
            days_old = (datetime.now(timezone.utc) - created_at).days
            message = self._build_channel_message(insight, user, days_old, level)

            # Send to channel via Slack WebClient
            self.slack_client.chat_postMessage(channel=channel_id, text=message)

            # Record success
            self._record_escalation(
                insight, "channel", level, channel_id, message, True, None
            )

            logger.info(
                f"Posted channel escalation for insight {insight.id} "
                f"to channel {channel_id}"
            )
            return True

        except Exception as e:
            logger.error(
                f"Error posting channel escalation for insight {insight.id}: {e}",
                exc_info=True,
            )
            self._record_escalation(
                insight, "channel", level, channel_id, None, False, str(e)
            )
            return False

    def _send_github_escalation(
        self, insight: ProactiveInsight, user: User, level: int
    ) -> bool:
        """Send GitHub PR comment escalation.

        Args:
            insight: Insight being escalated
            user: User who owns the insight
            level: Escalation level

        Returns:
            True if successful, False otherwise
        """
        # Extract PR URL from insight metadata
        metadata = insight.metadata_json or {}
        pr_url = metadata.get("pr_url") or metadata.get("url")

        if not pr_url:
            logger.warning(
                f"Insight {insight.id} has no pr_url in metadata, "
                f"cannot add GitHub comment"
            )
            self._record_escalation(
                insight,
                "github_comment",
                level,
                "no_pr_url",
                None,
                False,
                "No PR URL found in insight metadata",
            )
            return False

        try:
            # Build escalation comment
            created_at = self._ensure_timezone_aware(insight.created_at)
            days_old = (datetime.now(timezone.utc) - created_at).days
            comment = self._build_github_comment(insight, days_old, level)

            # Add comment via GitHubClient
            self.github_client.add_pr_comment(pr_url, comment)

            # Record success
            self._record_escalation(
                insight, "github_comment", level, pr_url, comment, True, None
            )

            logger.info(
                f"Added GitHub comment escalation for insight {insight.id} "
                f"on PR {pr_url}"
            )
            return True

        except Exception as e:
            logger.error(
                f"Error adding GitHub comment for insight {insight.id}: {e}",
                exc_info=True,
            )
            self._record_escalation(
                insight,
                "github_comment",
                level,
                pr_url or "unknown",
                None,
                False,
                str(e),
            )
            return False

    def _build_dm_message(
        self, insight: ProactiveInsight, days_old: int, level: int
    ) -> str:
        """Build DM escalation message.

        Args:
            insight: Insight being escalated
            days_old: Days since insight was created
            level: Escalation level

        Returns:
            Message text
        """
        severity_emoji = {
            "info": ":information_source:",
            "warning": ":warning:",
            "critical": ":rotating_light:",
        }

        emoji = severity_emoji.get(insight.severity, ":bell:")
        urgency = "CRITICAL" if level >= 3 else "URGENT" if level >= 2 else "REMINDER"

        message = f"{emoji} *{urgency}: {insight.title}*\n\n"
        message += f"This item has been waiting for *{days_old} days*.\n\n"
        message += f"{insight.description}\n\n"

        if insight.metadata_json:
            metadata = insight.metadata_json
            if metadata.get("pr_url"):
                message += f":link: PR: {metadata['pr_url']}\n"
            if metadata.get("project_key"):
                message += f":file_folder: Project: {metadata['project_key']}\n"

        message += f"\n_Escalation Level {level}/3_"
        return message

    def _build_channel_message(
        self, insight: ProactiveInsight, user: User, days_old: int, level: int
    ) -> str:
        """Build channel escalation message.

        Args:
            insight: Insight being escalated
            user: User who owns the insight
            days_old: Days since insight was created
            level: Escalation level

        Returns:
            Message text
        """
        severity_emoji = {
            "info": ":information_source:",
            "warning": ":warning:",
            "critical": ":rotating_light:",
        }

        emoji = severity_emoji.get(insight.severity, ":bell:")
        urgency = "CRITICAL" if level >= 3 else "URGENT" if level >= 2 else "REMINDER"

        user_mention = f"<@{user.slack_user_id}>" if user.slack_user_id else user.email

        message = f"{emoji} *{urgency}: {insight.title}*\n\n"
        message += f"Hey {user_mention}, this item has been waiting for "
        message += f"*{days_old} days* and needs attention.\n\n"
        message += f"{insight.description}\n\n"

        if insight.metadata_json:
            metadata = insight.metadata_json
            if metadata.get("pr_url"):
                message += f":link: PR: {metadata['pr_url']}\n"
            if metadata.get("project_key"):
                message += f":file_folder: Project: {metadata['project_key']}\n"

        message += f"\n_Escalation Level {level}/3 - Auto-escalated_"
        return message

    def _build_github_comment(
        self, insight: ProactiveInsight, days_old: int, level: int
    ) -> str:
        """Build GitHub PR comment.

        Args:
            insight: Insight being escalated
            days_old: Days since insight was created
            level: Escalation level

        Returns:
            Comment text
        """
        urgency = (
            "🚨 **CRITICAL**"
            if level >= 3
            else "⚠️ **URGENT**" if level >= 2 else "📌 **REMINDER**"
        )

        comment = f"{urgency}: This PR has been waiting for **{days_old} days**.\n\n"
        comment += f"{insight.description}\n\n"
        comment += f"---\n_Auto-escalated by PM Agent (Level {level}/3)_"

        return comment

    def _record_escalation(
        self,
        insight: ProactiveInsight,
        escalation_type: str,
        level: int,
        target: str,
        message: Optional[str],
        success: bool,
        error_message: Optional[str],
    ) -> None:
        """Record escalation action in audit trail.

        Args:
            insight: Insight being escalated
            escalation_type: Type of escalation ('dm', 'channel', 'github_comment')
            level: Escalation level
            target: Target (user ID, channel ID, PR URL)
            message: Message sent (if successful)
            success: Whether escalation succeeded
            error_message: Error message (if failed)
        """
        try:
            history = EscalationHistory(
                insight_id=insight.id,
                escalation_type=escalation_type,
                escalation_level=level,
                target=target,
                message_sent=message,
                success=success,
                error_message=error_message,
                created_at=datetime.now(timezone.utc),
            )
            self.db.add(history)
            self.db.commit()

        except Exception as e:
            logger.error(
                f"Error recording escalation history for insight {insight.id}: {e}",
                exc_info=True,
            )
            self.db.rollback()
