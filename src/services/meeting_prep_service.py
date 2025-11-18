"""Meeting prep digest delivery service for automated project notifications."""

import logging
from datetime import datetime, timezone, date
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
import asyncio
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from src.models import User, UserNotificationPreferences
from src.managers.notifications import NotificationManager
from src.services.project_activity_aggregator import ProjectActivityAggregator
from src.utils.database import get_db
from config.settings import settings

logger = logging.getLogger(__name__)


class MeetingPrepDeliveryService:
    """Service for generating and delivering meeting prep digests to users."""

    def __init__(self, db: Session = None):
        """Initialize the meeting prep delivery service.

        Args:
            db: Database session (optional, will create if not provided)
        """
        self.db = db or next(get_db())
        self.notification_manager = NotificationManager(settings)
        self.aggregator = ProjectActivityAggregator()

    def send_meeting_prep_digests(self) -> Dict[str, Any]:
        """Send meeting prep digests to all users watching projects with meetings today.

        This is the main entry point for the Celery task.

        Returns:
            Dictionary with delivery statistics
        """
        stats = {
            "projects_with_meetings_today": [],
            "digests_sent_slack": 0,
            "digests_sent_email": 0,
            "total_users_notified": set(),
            "errors": [],
        }

        try:
            # Get projects with meetings scheduled today
            projects_with_meetings = self._get_projects_with_meetings_today()
            stats["projects_with_meetings_today"] = [
                p["key"] for p in projects_with_meetings
            ]

            if not projects_with_meetings:
                logger.info("No projects with meetings scheduled today")
                return stats

            logger.info(
                f"Found {len(projects_with_meetings)} projects with meetings today: {stats['projects_with_meetings_today']}"
            )

            # For each project, get watchers and send digests
            for project in projects_with_meetings:
                project_key = project["key"]
                project_name = project.get("name", project_key)

                try:
                    # Get users watching this project
                    watchers = self._get_project_watchers(project_key)

                    if not watchers:
                        logger.debug(f"No watchers for project {project_key}")
                        continue

                    logger.info(
                        f"Sending meeting prep for {project_key} to {len(watchers)} watchers"
                    )

                    # Send digest to each watcher
                    for user in watchers:
                        try:
                            # Check if already sent today (deduplication)
                            if self._already_sent_today(user.id, project_key):
                                logger.debug(
                                    f"Already sent meeting prep for {project_key} to user {user.id} today"
                                )
                                continue

                            # Generate digest for this user
                            digest_result = self._generate_digest_for_user(
                                user, project_key, project_name
                            )

                            if not digest_result or not digest_result.get(
                                "formatted_agenda"
                            ):
                                logger.warning(
                                    f"Failed to generate digest for {project_key} / user {user.id}"
                                )
                                continue

                            # Send via Slack and Email based on preferences
                            delivery_results = self._deliver_digest(
                                user, project_key, project_name, digest_result
                            )

                            # Track delivery
                            if delivery_results["slack"] or delivery_results["email"]:
                                self._record_delivery(
                                    user.id,
                                    project_key,
                                    delivery_results["slack"],
                                    delivery_results["email"],
                                    digest_result.get("cache_id"),
                                )
                                stats["total_users_notified"].add(user.id)

                                if delivery_results["slack"]:
                                    stats["digests_sent_slack"] += 1
                                if delivery_results["email"]:
                                    stats["digests_sent_email"] += 1

                                logger.info(
                                    f"Delivered meeting prep for {project_key} to user {user.id} "
                                    f"(slack={delivery_results['slack']}, email={delivery_results['email']})"
                                )

                        except Exception as e:
                            logger.error(
                                f"Error sending digest to user {user.id} for project {project_key}: {e}",
                                exc_info=True,
                            )
                            stats["errors"].append(
                                f"User {user.id} / {project_key}: {str(e)}"
                            )

                except Exception as e:
                    logger.error(
                        f"Error processing project {project_key}: {e}", exc_info=True
                    )
                    stats["errors"].append(f"Project {project_key}: {str(e)}")

            stats["total_users_notified"] = len(stats["total_users_notified"])
            logger.info(f"Meeting prep delivery complete: {stats}")

        except Exception as e:
            logger.error(f"Error in meeting prep delivery: {e}", exc_info=True)
            stats["errors"].append(str(e))

        return stats

    def _get_projects_with_meetings_today(self) -> List[Dict[str, Any]]:
        """Get projects with meetings scheduled today based on weekly_meeting_day.

        Returns:
            List of project dictionaries with key and name
        """
        # Get current weekday name (lowercase: "monday", "tuesday", etc.)
        today_weekday = datetime.now(timezone.utc).strftime("%A").lower()

        query = text(
            """
            SELECT key, name
            FROM projects
            WHERE LOWER(weekly_meeting_day) = :today_weekday
            AND is_active = TRUE
        """
        )

        result = self.db.execute(query, {"today_weekday": today_weekday})
        projects = [{"key": row.key, "name": row.name} for row in result.fetchall()]

        return projects

    def _get_project_watchers(self, project_key: str) -> List[User]:
        """Get users watching a specific project.

        Args:
            project_key: Project key (e.g., "BIGO", "BEAU")

        Returns:
            List of User objects
        """
        query = text(
            """
            SELECT u.*
            FROM users u
            JOIN user_watched_projects uwp ON uwp.user_id = u.id
            JOIN projects p ON p.id = uwp.project_id
            WHERE p.key = :project_key
            AND u.is_active = TRUE
        """
        )

        result = self.db.execute(query, {"project_key": project_key})
        user_ids = [row.id for row in result.fetchall()]

        # Fetch full User objects
        users = self.db.query(User).filter(User.id.in_(user_ids)).all()
        return users

    def _already_sent_today(self, user_id: int, project_key: str) -> bool:
        """Check if meeting prep was already sent to user for this project today.

        Args:
            user_id: User ID
            project_key: Project key

        Returns:
            True if already sent today, False otherwise
        """
        query = text(
            """
            SELECT COUNT(*) as count
            FROM meeting_prep_deliveries
            WHERE user_id = :user_id
            AND project_key = :project_key
            AND DATE(delivered_at) = :today
        """
        )

        result = self.db.execute(
            query,
            {
                "user_id": user_id,
                "project_key": project_key,
                "today": date.today(),
            },
        )

        count = result.fetchone().count
        return count > 0

    def _generate_digest_for_user(
        self, user: User, project_key: str, project_name: str
    ) -> Optional[Dict[str, Any]]:
        """Generate weekly digest for a user with attendee context.

        Args:
            user: User to generate digest for
            project_key: Project key
            project_name: Project name

        Returns:
            Dictionary with formatted_agenda, cache_id, and metadata
        """
        try:
            # Use aggregator to generate digest (uses cache if available)
            # Days=7 for weekly digest, include_attendee_context=True for personalization
            result = asyncio.run(
                self.aggregator.aggregate_project_activity(
                    project_key=project_key,
                    days=7,
                    user_email=user.email,
                    include_context=True,
                    include_attendee_context=True,
                )
            )

            if not result or not result.get("formatted_agenda"):
                logger.warning(f"No digest generated for {project_key} / {user.email}")
                return None

            return {
                "formatted_agenda": result["formatted_agenda"],
                "cache_id": result.get("cache_id"),
                "project_name": project_name,
                "user_email": user.email,
            }

        except Exception as e:
            logger.error(
                f"Error generating digest for {project_key} / {user.email}: {e}",
                exc_info=True,
            )
            return None

    def _deliver_digest(
        self,
        user: User,
        project_key: str,
        project_name: str,
        digest_result: Dict[str, Any],
    ) -> Dict[str, bool]:
        """Deliver digest to user via Slack and/or Email based on preferences.

        Args:
            user: User to deliver to
            project_key: Project key
            project_name: Project name
            digest_result: Dictionary with formatted_agenda

        Returns:
            Dictionary with slack and email delivery status
        """
        results = {"slack": False, "email": False}

        # Get user preferences
        prefs = (
            self.db.query(UserNotificationPreferences)
            .filter(UserNotificationPreferences.user_id == user.id)
            .first()
        )

        # Default: Slack enabled, Email disabled (unless user is ID 1 - Mike)
        deliver_slack = prefs.daily_brief_slack if prefs else True
        deliver_email = user.id == 1  # Only Mike gets emails

        formatted_agenda = digest_result["formatted_agenda"]

        # Deliver via Slack
        if deliver_slack and user.slack_user_id:
            try:
                slack_message = self._format_slack_message(
                    project_key, project_name, formatted_agenda
                )
                result = asyncio.run(
                    self.notification_manager._send_slack_dm(
                        user.slack_user_id, slack_message
                    )
                )
                results["slack"] = result.get("success", False)
                if results["slack"]:
                    logger.info(
                        f"Delivered Slack digest for {project_key} to user {user.id}"
                    )
                else:
                    logger.error(
                        f"Failed to deliver Slack digest for {project_key} to user {user.id}: {result.get('error')}"
                    )
            except Exception as e:
                logger.error(
                    f"Error delivering Slack digest for {project_key} to user {user.id}: {e}"
                )

        # Deliver via Email (only for user ID 1)
        if deliver_email:
            try:
                email_html = self._format_email_message(
                    project_key, project_name, formatted_agenda
                )
                result = self._send_email(
                    user.email,
                    f"📅 Meeting Prep: {project_name} ({project_key})",
                    email_html,
                )
                results["email"] = result
                if results["email"]:
                    logger.info(
                        f"Delivered email digest for {project_key} to {user.email}"
                    )
            except Exception as e:
                logger.error(
                    f"Error delivering email digest for {project_key} to {user.email}: {e}"
                )

        return results

    def _format_slack_message(
        self, project_key: str, project_name: str, formatted_agenda: str
    ) -> str:
        """Format digest as Slack message.

        Args:
            project_key: Project key
            project_name: Project name
            formatted_agenda: Markdown formatted digest

        Returns:
            Formatted Slack message
        """
        # Get today's day name for display
        today = datetime.now(timezone.utc).strftime("%A")

        # Add header
        message = f"📅 *{project_name} ({project_key}) Meeting Prep - {today}*\n\n"

        # Convert markdown sections to Slack format
        # The formatted_agenda is already in markdown, we can send it directly
        message += formatted_agenda

        # Add footer with link to project
        if hasattr(settings.web, "base_url"):
            project_url = f"{settings.web.base_url}/projects/{project_key}"
            message += f"\n\n🔗 <{project_url}|View full project details>"

        return message

    def _format_email_message(
        self, project_key: str, project_name: str, formatted_agenda: str
    ) -> str:
        """Format digest as HTML email.

        Args:
            project_key: Project key
            project_name: Project name
            formatted_agenda: Markdown formatted digest

        Returns:
            HTML email body
        """
        today = datetime.now(timezone.utc).strftime("%A, %B %d, %Y")

        # Convert markdown to HTML (basic conversion)
        # In production, you might want to use a proper markdown-to-HTML library
        html_content = formatted_agenda.replace("\n## ", "\n<h2>").replace(
            "\n# ", "\n<h1>"
        )
        html_content = html_content.replace("\n**", "\n<strong>").replace(
            "**\n", "</strong>\n"
        )
        html_content = html_content.replace("\n*", "\n<li>").replace("*\n", "</li>\n")
        html_content = html_content.replace("\n", "<br>\n")

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 800px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #554DFF 0%, #7D00FF 100%);
                 color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
        .content {{ background: #f9f9f9; padding: 20px; }}
        h1 {{ margin: 0; font-size: 24px; }}
        h2 {{ color: #554DFF; margin-top: 20px; }}
        .footer {{ background: #333; color: white; padding: 15px;
                 border-radius: 0 0 8px 8px; text-align: center; }}
        .button {{ display: inline-block; padding: 10px 20px; background: #554DFF;
                 color: white; text-decoration: none; border-radius: 4px; margin-top: 10px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📅 {project_name} ({project_key}) Meeting Prep</h1>
            <p>{today}</p>
        </div>
        <div class="content">
            {html_content}
        </div>
        <div class="footer">
            <p>Autonomous PM Agent | Powered by AI</p>
            <a href="{settings.web.base_url}/projects/{project_key}" class="button">View Project Details</a>
        </div>
    </div>
</body>
</html>
"""
        return html

    def _send_email(self, to_email: str, subject: str, html_body: str) -> bool:
        """Send email via SMTP.

        Args:
            to_email: Recipient email
            subject: Email subject
            html_body: HTML email body

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            smtp_config = self.notification_manager.smtp_config
            if not smtp_config:
                logger.warning("SMTP not configured, cannot send email")
                return False

            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{smtp_config['from_name']} <{smtp_config['from_email']}>"
            msg["To"] = to_email

            part = MIMEText(html_body, "html")
            msg.attach(part)

            with smtplib.SMTP(smtp_config["host"], smtp_config["port"]) as server:
                server.starttls()
                server.login(smtp_config["user"], smtp_config["password"])
                server.send_message(msg)

            return True

        except Exception as e:
            logger.error(f"Error sending email to {to_email}: {e}", exc_info=True)
            return False

    def _record_delivery(
        self,
        user_id: int,
        project_key: str,
        delivered_via_slack: bool,
        delivered_via_email: bool,
        digest_cache_id: Optional[str] = None,
    ):
        """Record delivery in database for deduplication.

        Args:
            user_id: User ID
            project_key: Project key
            delivered_via_slack: Whether delivered via Slack
            delivered_via_email: Whether delivered via Email
            digest_cache_id: Optional digest cache ID
        """
        try:
            import uuid

            query = text(
                """
                INSERT INTO meeting_prep_deliveries (
                    id, user_id, project_key, delivered_at,
                    delivered_via_slack, delivered_via_email, digest_cache_id
                )
                VALUES (
                    :id, :user_id, :project_key, :delivered_at,
                    :delivered_via_slack, :delivered_via_email, :digest_cache_id
                )
            """
            )

            self.db.execute(
                query,
                {
                    "id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "project_key": project_key,
                    "delivered_at": datetime.now(timezone.utc),
                    "delivered_via_slack": delivered_via_slack,
                    "delivered_via_email": delivered_via_email,
                    "digest_cache_id": digest_cache_id,
                },
            )
            # Note: Do NOT commit here - let the caller/tracker manage the transaction

        except Exception as e:
            logger.error(
                f"Error recording delivery for user {user_id} / {project_key}: {e}"
            )
            # Note: Do NOT rollback here - let the caller/tracker handle transaction management
            raise  # Re-raise so the tracker knows to rollback
