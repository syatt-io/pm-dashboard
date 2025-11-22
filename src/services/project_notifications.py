"""Project notification service for sending change summaries."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from collections import defaultdict

from config.settings import settings
from src.managers.notifications import NotificationManager, NotificationContent
from src.services.project_monitor import ProjectMonitor


logger = logging.getLogger(__name__)


class ProjectNotificationService:
    """Service for generating and sending project change notifications."""

    def __init__(self):
        """Initialize the notification service."""
        self.notifier = NotificationManager(settings.notifications)
        self.monitor = ProjectMonitor()

    async def send_user_notifications(self, email: str, force: bool = False) -> bool:
        """Send notifications to a specific user based on their cadence."""
        try:
            from src.models import UserPreference
            from sqlalchemy.orm import sessionmaker
            from sqlalchemy import create_engine

            engine = create_engine(settings.agent.database_url)
            Session = sessionmaker(bind=engine)
            db_session = Session()

            user_pref = db_session.query(UserPreference).filter_by(email=email).first()

            if not user_pref or not user_pref.selected_projects:
                db_session.close()
                logger.info(f"No projects selected for user {email}")
                return False

            # Check if notification is due (unless forced)
            if not force and user_pref.last_notification_sent:
                cadence = user_pref.notification_cadence
                last_sent = user_pref.last_notification_sent
                now = datetime.now()

                if cadence == "daily" and (now - last_sent).days < 1:
                    db_session.close()
                    return False
                elif cadence == "weekly" and (now - last_sent).days < 7:
                    db_session.close()
                    return False
                elif cadence == "monthly" and (now - last_sent).days < 30:
                    db_session.close()
                    return False

            # Determine the time period to look back
            cadence = user_pref.notification_cadence
            if cadence == "daily":
                since = datetime.now() - timedelta(days=1)
            elif cadence == "weekly":
                since = datetime.now() - timedelta(days=7)
            elif cadence == "monthly":
                since = datetime.now() - timedelta(days=30)
            else:
                since = datetime.now() - timedelta(days=1)

            # Get user's project changes
            changes = await self.monitor.get_user_project_changes(email, since)

            if not changes:
                logger.info(f"No changes found for user {email}")
                db_session.close()
                return False

            # Generate notification content
            notification_content = self._generate_notification_content(
                changes, user_pref.selected_projects, cadence
            )

            # Send Slack DM if user has Slack ID
            if user_pref.slack_user_id:
                await self._send_slack_dm(user_pref.slack_user_id, notification_content)

            # Always send via regular notification channels as well
            notification = NotificationContent(
                title=notification_content["title"],
                body=notification_content["body"],
                priority="normal",
            )
            await self.notifier.send_notification(notification, channels=["slack"])

            # Update last notification sent time
            user_pref.last_notification_sent = datetime.now()
            db_session.commit()
            db_session.close()

            logger.info(f"Sent notification to user {email}")
            return True

        except Exception as e:
            logger.error(f"Error sending notifications to user {email}: {e}")
            return False

    def _generate_notification_content(
        self, changes: List[Dict[str, Any]], selected_projects: List[str], cadence: str
    ) -> Dict[str, str]:
        """Generate comprehensive notification content."""

        # Group changes by project and type
        project_changes = defaultdict(lambda: defaultdict(list))
        for change in changes:
            project_changes[change["project_key"]][change["change_type"]].append(change)

        # Generate summary statistics
        total_changes = len(changes)
        projects_with_changes = len(project_changes)

        # Count change types
        change_type_counts = defaultdict(int)
        for change in changes:
            change_type_counts[change["change_type"]] += 1

        period_text = {
            "daily": "today",
            "weekly": "this week",
            "monthly": "this month",
        }.get(cadence, "recently")

        title = f"📊 Project Changes Summary - {total_changes} changes {period_text}"

        # Build detailed body
        body_parts = []

        # Overview section
        body_parts.append(
            f"*{total_changes} total changes* across *{projects_with_changes} projects* {period_text}"
        )
        body_parts.append("")

        # Change type breakdown
        if change_type_counts:
            body_parts.append("*📈 Change Breakdown:*")
            for change_type, count in sorted(
                change_type_counts.items(), key=lambda x: x[1], reverse=True
            ):
                emoji = self._get_change_emoji(change_type)
                readable_type = self._get_readable_change_type(change_type)
                body_parts.append(f"  {emoji} {readable_type}: {count}")
            body_parts.append("")

        # Project-by-project details
        body_parts.append("*🎯 Project Details:*")
        for project_key in sorted(project_changes.keys()):
            project_change_types = project_changes[project_key]
            project_total = sum(
                len(changes) for changes in project_change_types.values()
            )

            body_parts.append(f"*{project_key}* ({project_total} changes)")

            # Show top changes for this project
            all_project_changes = []
            for change_list in project_change_types.values():
                all_project_changes.extend(change_list)

            # Sort by timestamp, newest first
            all_project_changes.sort(key=lambda x: x["change_timestamp"], reverse=True)

            # Show up to 5 most recent changes
            for change in all_project_changes[:5]:
                emoji = self._get_change_emoji(change["change_type"])
                time_str = change["change_timestamp"].strftime("%m/%d %H:%M")

                if change["change_type"] == "created":
                    body_parts.append(
                        f"  {emoji} {time_str} - New: {change['ticket_key']} - {change['ticket_title'][:50]}"
                    )
                elif change["change_type"] == "status_changed":
                    body_parts.append(
                        f"  {emoji} {time_str} - Status: {change['ticket_key']} → {change['new_value']}"
                    )
                elif change["change_type"] == "assignee_changed":
                    body_parts.append(
                        f"  {emoji} {time_str} - Assigned: {change['ticket_key']} → {change['new_value']}"
                    )
                else:
                    readable_type = self._get_readable_change_type(
                        change["change_type"]
                    )
                    body_parts.append(
                        f"  {emoji} {time_str} - {readable_type}: {change['ticket_key']}"
                    )

            if len(all_project_changes) > 5:
                body_parts.append(
                    f"  ... and {len(all_project_changes) - 5} more changes"
                )
            body_parts.append("")

        # Action items section
        if any(change["change_type"] == "assignee_changed" for change in changes):
            body_parts.append("*🎯 Action Items:*")
            assigned_to_me = [
                c
                for c in changes
                if c["change_type"] == "assignee_changed"
                and c["new_value"]
                and "you" in c["new_value"].lower()
            ]
            if assigned_to_me:
                body_parts.append(f"  • {len(assigned_to_me)} tickets newly assigned")

            overdue_mentions = [
                c
                for c in changes
                if "overdue" in str(c.get("change_details", {})).lower()
            ]
            if overdue_mentions:
                body_parts.append(
                    f"  • Check {len(overdue_mentions)} tickets mentioned as overdue"
                )
            body_parts.append("")

        # Footer
        body_parts.append(f"📊 View full details in the PM Agent dashboard")
        body_parts.append(f"⚙️ Update your notification preferences in My Projects")

        return {"title": title, "body": "\n".join(body_parts)}

    def _get_change_emoji(self, change_type: str) -> str:
        """Get emoji for change type."""
        emoji_map = {
            "created": "🆕",
            "updated": "📝",
            "status_changed": "🔄",
            "assignee_changed": "👤",
            "priority_changed": "⚡",
            "time_logged": "⏱️",
            "title_changed": "📋",
            "description_changed": "📄",
            "estimate_changed": "📊",
            "labels_changed": "🏷️",
            "fix_version_changed": "🎯",
            "components_changed": "🧩",
        }
        return emoji_map.get(change_type, "📌")

    def _get_readable_change_type(self, change_type: str) -> str:
        """Get human-readable change type."""
        readable_map = {
            "created": "New Ticket",
            "updated": "Updated",
            "status_changed": "Status Change",
            "assignee_changed": "Assignee Change",
            "priority_changed": "Priority Change",
            "time_logged": "Time Logged",
            "title_changed": "Title Change",
            "description_changed": "Description Change",
            "estimate_changed": "Estimate Change",
            "labels_changed": "Labels Change",
            "fix_version_changed": "Fix Version Change",
            "components_changed": "Components Change",
        }
        return readable_map.get(change_type, change_type.replace("_", " ").title())

    async def _send_slack_dm(self, slack_user_id: str, content: Dict[str, str]):
        """Send direct message to Slack user."""
        try:
            # This would integrate with Slack Bot API for direct messages
            # For now, we'll use the regular notification system
            logger.info(
                f"Would send DM to Slack user {slack_user_id}: {content['title']}"
            )

            # TODO: Implement actual Slack DM sending
            # This would require the Slack Bot to have permission to send DMs
            # and the user's Slack workspace to allow bot DMs

        except Exception as e:
            logger.error(f"Error sending Slack DM to {slack_user_id}: {e}")

    async def send_daily_notifications(self):
        """Send notifications to all users who are due for daily notifications."""
        try:
            from src.models import UserPreference
            from sqlalchemy.orm import sessionmaker
            from sqlalchemy import create_engine

            engine = create_engine(settings.agent.database_url)
            Session = sessionmaker(bind=engine)
            db_session = Session()

            # Get users who want daily notifications
            daily_users = (
                db_session.query(UserPreference)
                .filter_by(notification_cadence="daily")
                .all()
            )

            db_session.close()

            logger.info(f"Sending daily notifications to {len(daily_users)} users")

            sent_count = 0
            for user in daily_users:
                if await self.send_user_notifications(user.email):
                    sent_count += 1

            logger.info(
                f"Sent daily notifications to {sent_count}/{len(daily_users)} users"
            )

        except Exception as e:
            logger.error(f"Error sending daily notifications: {e}")

    async def send_weekly_notifications(self):
        """Send notifications to all users who are due for weekly notifications."""
        try:
            from src.models import UserPreference
            from sqlalchemy.orm import sessionmaker
            from sqlalchemy import create_engine

            engine = create_engine(settings.agent.database_url)
            Session = sessionmaker(bind=engine)
            db_session = Session()

            # Get users who want weekly notifications
            weekly_users = (
                db_session.query(UserPreference)
                .filter_by(notification_cadence="weekly")
                .all()
            )

            db_session.close()

            logger.info(f"Sending weekly notifications to {len(weekly_users)} users")

            sent_count = 0
            for user in weekly_users:
                if await self.send_user_notifications(user.email):
                    sent_count += 1

            logger.info(
                f"Sent weekly notifications to {sent_count}/{len(weekly_users)} users"
            )

        except Exception as e:
            logger.error(f"Error sending weekly notifications: {e}")

    async def send_monthly_notifications(self):
        """Send notifications to all users who are due for monthly notifications."""
        try:
            from src.models import UserPreference
            from sqlalchemy.orm import sessionmaker
            from sqlalchemy import create_engine

            engine = create_engine(settings.agent.database_url)
            Session = sessionmaker(bind=engine)
            db_session = Session()

            # Get users who want monthly notifications
            monthly_users = (
                db_session.query(UserPreference)
                .filter_by(notification_cadence="monthly")
                .all()
            )

            db_session.close()

            logger.info(f"Sending monthly notifications to {len(monthly_users)} users")

            sent_count = 0
            for user in monthly_users:
                if await self.send_user_notifications(user.email):
                    sent_count += 1

            logger.info(
                f"Sent monthly notifications to {sent_count}/{len(monthly_users)} users"
            )

        except Exception as e:
            logger.error(f"Error sending monthly notifications: {e}")
