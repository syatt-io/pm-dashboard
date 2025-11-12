"""
Time Tracking Compliance Job

Scheduled job to monitor weekly time tracking compliance in Tempo.
Runs every Monday at 10 AM EST to review previous week's time entries.
Sends reminders to non-compliant team members and reports to PMs.
"""

import logging
import os
import asyncio
from datetime import datetime, timedelta, date
from typing import Dict, List, Tuple
from collections import defaultdict
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.integrations.tempo import TempoAPIClient
from src.models import TimeTrackingCompliance, UserTeam, User
from src.managers.notifications import NotificationManager
from config.settings import settings

logger = logging.getLogger(__name__)


class TimeTrackingComplianceJob:
    """Monitors weekly time tracking compliance and sends reminders."""

    # Compliance threshold: 32 hours (allows for meetings/admin time)
    COMPLIANT_THRESHOLD = 32.0
    PARTIAL_THRESHOLD = 16.0

    def __init__(self):
        """Initialize the job with required clients and database connection."""
        self.tempo_client = TempoAPIClient()
        self.notification_manager = NotificationManager(settings)

        # Get database URL from environment
        self.database_url = os.getenv("DATABASE_URL")
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable is required")

        # Create database engine and session
        self.engine = create_engine(self.database_url)
        self.Session = sessionmaker(bind=self.engine)

    def get_previous_week_dates(self) -> Tuple[date, date]:
        """
        Calculate the previous week's date range (Monday to Sunday).

        Returns:
            Tuple of (week_start_date, week_end_date) as date objects
        """
        # Get today's date
        today = datetime.now().date()

        # Find last Monday (start of previous week)
        # weekday(): Monday=0, Sunday=6
        days_since_monday = (today.weekday() + 7) % 7  # Days since last Monday
        if days_since_monday == 0:
            # If today is Monday, go back 7 days to get previous Monday
            days_since_monday = 7

        last_monday = today - timedelta(days=days_since_monday)
        previous_monday = last_monday - timedelta(days=7)

        # Calculate Sunday (6 days after Monday)
        previous_sunday = previous_monday + timedelta(days=6)

        logger.info(f"Previous week: {previous_monday} to {previous_sunday}")
        return previous_monday, previous_sunday

    def fetch_weekly_worklogs(self, start_date: date, end_date: date) -> List[Dict]:
        """
        Fetch all worklogs for the specified week.

        Args:
            start_date: Monday of the week
            end_date: Sunday of the week

        Returns:
            List of worklog dictionaries from Tempo API
        """
        logger.info(f"Fetching worklogs for {start_date} to {end_date}")

        worklogs = self.tempo_client.get_worklogs(
            from_date=start_date.isoformat(), to_date=end_date.isoformat()
        )

        logger.info(f"Fetched {len(worklogs)} worklogs for the week")
        return worklogs

    def calculate_user_hours(self, worklogs: List[Dict]) -> Dict[str, float]:
        """
        Calculate total hours logged per user for the week.

        Args:
            worklogs: List of worklog dictionaries

        Returns:
            Dictionary mapping account_id -> total_hours
        """
        user_hours = defaultdict(float)

        for worklog in worklogs:
            author = worklog.get("author", {})
            account_id = author.get("accountId")

            if account_id:
                # Convert seconds to hours
                seconds = worklog.get("timeSpentSeconds", 0)
                hours = seconds / 3600.0
                user_hours[account_id] += hours

        logger.info(f"Calculated hours for {len(user_hours)} users")
        return dict(user_hours)

    def classify_users(
        self, user_hours: Dict[str, float]
    ) -> Tuple[List[Dict], List[Dict], List[Dict], List[Dict]]:
        """
        Classify users by compliance status using User table.

        Args:
            user_hours: Dictionary of account_id -> total_hours

        Returns:
            Tuple of (compliant_users, partial_users, non_compliant_users, unmapped_tempo_users)
            Each list contains dicts with account_id, hours, user_name, and threshold
        """
        session = self.Session()
        try:
            compliant = []
            partial = []
            non_compliant = []
            unmapped_tempo_users = []

            # Get all users with jira_account_id mapped (active team members)
            mapped_users = (
                session.query(User)
                .filter(User.jira_account_id.isnot(None), User.is_active == True)
                .all()
            )

            logger.info(
                f"Checking compliance for {len(mapped_users)} mapped team members"
            )

            # Track which Tempo users we've mapped
            mapped_account_ids = set()

            for user in mapped_users:
                account_id = user.jira_account_id
                mapped_account_ids.add(account_id)
                hours = user_hours.get(account_id, 0.0)
                user_name = user.name
                threshold = user.weekly_hours_minimum  # Per-user threshold

                # Calculate partial threshold (50% of user's threshold)
                partial_threshold = threshold * 0.5

                user_data = {
                    "account_id": account_id,
                    "user_name": user_name,
                    "hours": hours,
                    "team": user.team or "Unassigned",
                    "threshold": threshold,
                    "email": user.email,
                }

                if hours >= threshold:
                    compliant.append(user_data)
                elif hours >= partial_threshold:
                    partial.append(user_data)
                else:
                    non_compliant.append(user_data)

            # Find unmapped Tempo users (logged time but not in User table)
            for account_id, hours in user_hours.items():
                if account_id not in mapped_account_ids:
                    # Try to get user name from Jira API
                    user_email = self._get_user_email(account_id)
                    unmapped_tempo_users.append(
                        {
                            "account_id": account_id,
                            "hours": hours,
                            "email": user_email or "unknown",
                        }
                    )

            logger.info(
                f"Compliance breakdown - Compliant: {len(compliant)}, "
                f"Partial: {len(partial)}, Non-compliant: {len(non_compliant)}, "
                f"Unmapped Tempo users: {len(unmapped_tempo_users)}"
            )

            return compliant, partial, non_compliant, unmapped_tempo_users

        finally:
            session.close()

    def store_compliance_data(self, week_start: date, all_users: List[Dict]) -> None:
        """
        Store compliance data in database.

        Args:
            week_start: Monday of the week being tracked
            all_users: List of all users with their hours and compliance status
        """
        session = self.Session()
        try:
            for user_data in all_users:
                is_compliant = user_data["hours"] >= self.COMPLIANT_THRESHOLD

                # Upsert compliance record
                existing = (
                    session.query(TimeTrackingCompliance)
                    .filter_by(
                        user_account_id=user_data["account_id"],
                        week_start_date=week_start,
                    )
                    .first()
                )

                if existing:
                    existing.hours_logged = user_data["hours"]
                    existing.is_compliant = is_compliant
                else:
                    compliance_record = TimeTrackingCompliance(
                        user_account_id=user_data["account_id"],
                        week_start_date=week_start,
                        hours_logged=user_data["hours"],
                        is_compliant=is_compliant,
                        notification_sent=False,
                        pm_notified=False,
                    )
                    session.add(compliance_record)

            session.commit()
            logger.info(f"Stored compliance data for {len(all_users)} users")

        except Exception as e:
            session.rollback()
            logger.error(f"Error storing compliance data: {e}")
            raise
        finally:
            session.close()

    async def send_user_notifications(
        self,
        partial_users: List[Dict],
        non_compliant_users: List[Dict],
        week_start: date,
        week_end: date,
    ) -> Dict[str, int]:
        """
        Send Slack DMs to users who need to log time.

        Args:
            partial_users: Users with 16-31 hours logged
            non_compliant_users: Users with <16 hours logged
            week_start: Monday of the week
            week_end: Sunday of the week

        Returns:
            Dictionary with notification statistics
        """
        stats = {"partial": 0, "non_compliant": 0, "failed": 0}

        # Get user Slack IDs from database
        session = self.Session()
        try:
            all_notifications = partial_users + non_compliant_users

            for user_data in all_notifications:
                account_id = user_data["account_id"]
                hours = user_data["hours"]
                user_name = user_data["user_name"]

                # Get user email from Jira API
                user_email = self._get_user_email(account_id)
                if not user_email:
                    logger.warning(
                        f"No email found for user {user_name} ({account_id})"
                    )
                    stats["failed"] += 1
                    continue

                # Look up Slack user ID by email
                db_user = session.query(User).filter_by(email=user_email).first()
                if not db_user or not db_user.slack_user_id:
                    logger.warning(
                        f"No User/Slack ID found for {user_name} ({user_email})"
                    )
                    stats["failed"] += 1
                    continue

                # Craft appropriate message based on hours logged
                if hours >= self.PARTIAL_THRESHOLD:
                    # Partial logger (16-31 hours)
                    message = (
                        f"📊 *Time Tracking Reminder*\n\n"
                        f"Hi {user_name.split()[0]}! You logged *{hours:.1f}/40 hours* last week "
                        f"({week_start.strftime('%b %d')} - {week_end.strftime('%b %d')}).\n\n"
                        f"Please review your calendar and update Tempo with any missing entries. "
                        f"Accurate time tracking helps us manage project budgets effectively.\n\n"
                        f"Thanks! 🙏"
                    )
                else:
                    # Non-compliant (<16 hours)
                    message = (
                        f"⚠️  *Time Tracking Alert*\n\n"
                        f"Hi {user_name.split()[0]}, you logged only *{hours:.1f} hours* last week "
                        f"({week_start.strftime('%b %d')} - {week_end.strftime('%b %d')}).\n\n"
                        f"Please update Tempo with your hours ASAP. If you were on PTO or had low "
                        f"billable hours, please make sure that's reflected in Tempo.\n\n"
                        f"Need help? Reach out to your PM. Thanks! 🙏"
                    )

                # Send DM
                try:
                    result = await self.notification_manager._send_slack_dm(
                        slack_user_id=db_user.slack_user_id, message=message
                    )

                    if result.get("success"):
                        if hours >= self.PARTIAL_THRESHOLD:
                            stats["partial"] += 1
                        else:
                            stats["non_compliant"] += 1

                        # Mark as notified in database
                        self._mark_notification_sent(session, account_id, week_start)
                    else:
                        logger.error(
                            f"Failed to send DM to {user_name}: {result.get('error')}"
                        )
                        stats["failed"] += 1

                except Exception as e:
                    logger.error(f"Error sending DM to {user_name}: {e}")
                    stats["failed"] += 1

            session.commit()

        finally:
            session.close()

        logger.info(
            f"Sent {stats['partial']} partial + {stats['non_compliant']} non-compliant notifications"
        )
        return stats

    def _get_user_email(self, account_id: str) -> str:
        """
        Get user email from Jira API using account ID.

        Args:
            account_id: Jira/Tempo account ID

        Returns:
            User email address or empty string if not found
        """
        try:
            import requests

            # Use Tempo client's Jira credentials
            url = f"{self.tempo_client.jira_url}/rest/api/3/user"
            params = {"accountId": account_id}
            response = requests.get(
                url, headers=self.tempo_client.jira_headers, params=params, timeout=10
            )
            response.raise_for_status()

            user_data = response.json()
            email = user_data.get("emailAddress", "")
            return email

        except Exception as e:
            logger.debug(f"Error getting email for account ID {account_id}: {e}")
            return ""

    def _mark_notification_sent(
        self, session, account_id: str, week_start: date
    ) -> None:
        """Mark that notification was sent to user."""
        record = (
            session.query(TimeTrackingCompliance)
            .filter_by(user_account_id=account_id, week_start_date=week_start)
            .first()
        )

        if record:
            record.notification_sent = True

    async def send_pm_summary(
        self,
        compliant_users: List[Dict],
        partial_users: List[Dict],
        non_compliant_users: List[Dict],
        unmapped_tempo_users: List[Dict],
        week_start: date,
        week_end: date,
    ) -> None:
        """
        Send summary to PM Slack channel.

        Args:
            compliant_users: List of compliant users
            partial_users: List of partial loggers
            non_compliant_users: List of non-compliant users
            unmapped_tempo_users: List of Tempo users not mapped in User table
            week_start: Monday of the week
            week_end: Sunday of the week
        """
        total = len(compliant_users) + len(partial_users) + len(non_compliant_users)
        if total == 0:
            logger.warning("No team members found in database")
            return

        compliance_pct = (len(compliant_users) / total) * 100

        # Build message
        message_lines = [
            f"📊 *Weekly Time Tracking Compliance Report*",
            f"Week of {week_start.strftime('%b %d')} - {week_end.strftime('%b %d')}\n",
            f"*Overall Compliance: {compliance_pct:.1f}%* ({len(compliant_users)}/{total} team members)\n",
        ]

        # Compliant section
        if compliant_users:
            message_lines.append(
                f"✅ *Compliant ({len(compliant_users)}):* ≥32 hours logged"
            )
            # Group by team
            by_team = defaultdict(list)
            for user in compliant_users:
                by_team[user["team"]].append(
                    f"{user['user_name']} ({user['hours']:.1f}h)"
                )

            for team, users in sorted(by_team.items()):
                message_lines.append(
                    f"  • {team}: {', '.join(users[:5])}"
                    + (f" +{len(users)-5} more" if len(users) > 5 else "")
                )

            message_lines.append("")

        # Partial section
        if partial_users:
            message_lines.append(
                f"🟡 *Partial ({len(partial_users)}):* 16-31 hours logged"
            )
            for user in partial_users[:10]:  # Limit to 10
                message_lines.append(
                    f"  • {user['user_name']} ({user['team']}): {user['hours']:.1f}h"
                )
            if len(partial_users) > 10:
                message_lines.append(f"  ... and {len(partial_users) - 10} more")
            message_lines.append("")

        # Non-compliant section
        if non_compliant_users:
            message_lines.append(
                f"🔴 *Non-Compliant ({len(non_compliant_users)}):* <16 hours logged"
            )
            for user in non_compliant_users[:10]:  # Limit to 10
                message_lines.append(
                    f"  • {user['user_name']} ({user['team']}): {user['hours']:.1f}h"
                )
            if len(non_compliant_users) > 10:
                message_lines.append(f"  ... and {len(non_compliant_users) - 10} more")
            message_lines.append("")

        # Repeat offenders check
        repeat_offenders = self._find_repeat_offenders(non_compliant_users, week_start)
        if repeat_offenders:
            message_lines.append(f"⚠️  *Repeat Offenders (2+ weeks):*")
            for user in repeat_offenders:
                message_lines.append(f"  • {user['user_name']} ({user['team']})")
            message_lines.append("")

        # Unmapped Tempo users section
        if unmapped_tempo_users:
            message_lines.append(
                f"❓ *Unmapped Tempo Users ({len(unmapped_tempo_users)}):* Time logged but not in User Management"
            )
            for user in unmapped_tempo_users[:10]:  # Limit to 10
                message_lines.append(
                    f"  • {user['email']} ({user['account_id']}): {user['hours']:.1f}h"
                )
            if len(unmapped_tempo_users) > 10:
                message_lines.append(f"  ... and {len(unmapped_tempo_users) - 10} more")
            message_lines.append(
                "_Add these users to User Management to track their compliance._"
            )
            message_lines.append("")

        message = "\n".join(message_lines)

        # Send to PM channel (configured in settings or environment)
        pm_channel = os.getenv("SLACK_PM_CHANNEL", "#pm-alerts")

        try:
            # Use the Slack client directly for channel messages
            if self.notification_manager.slack_client:
                response = self.notification_manager.slack_client.chat_postMessage(
                    channel=pm_channel, text=message
                )
                logger.info(f"Sent PM summary to {pm_channel}")
            else:
                logger.warning("Slack not configured, cannot send PM summary")

        except Exception as e:
            logger.error(f"Error sending PM summary: {e}")

    def _find_repeat_offenders(
        self, non_compliant_users: List[Dict], current_week: date
    ) -> List[Dict]:
        """
        Find users who have been non-compliant for 2+ consecutive weeks.

        Args:
            non_compliant_users: List of currently non-compliant users
            current_week: Monday of current week being processed

        Returns:
            List of repeat offenders
        """
        session = self.Session()
        try:
            repeat_offenders = []

            for user in non_compliant_users:
                account_id = user["account_id"]

                # Check previous week
                previous_week = current_week - timedelta(days=7)
                previous_record = (
                    session.query(TimeTrackingCompliance)
                    .filter_by(
                        user_account_id=account_id,
                        week_start_date=previous_week,
                        is_compliant=False,
                    )
                    .first()
                )

                if previous_record:
                    repeat_offenders.append(user)

            return repeat_offenders

        finally:
            session.close()

    def run(self) -> Dict:
        """
        Execute the Time Tracking Compliance job.

        Returns:
            Dictionary with job execution statistics
        """
        start_time = datetime.now()
        logger.info(f"Starting Time Tracking Compliance job at {start_time}")

        try:
            # Get previous week dates
            week_start, week_end = self.get_previous_week_dates()

            # Fetch worklogs
            worklogs = self.fetch_weekly_worklogs(week_start, week_end)

            # Calculate hours per user
            user_hours = self.calculate_user_hours(worklogs)

            # Classify users by compliance
            compliant, partial, non_compliant, unmapped_tempo_users = (
                self.classify_users(user_hours)
            )

            # Combine all users for storage
            all_users = compliant + partial + non_compliant

            # Store compliance data
            self.store_compliance_data(week_start, all_users)

            # Send PM summary only (no individual DMs for testing phase)
            asyncio.run(
                self.send_pm_summary(
                    compliant,
                    partial,
                    non_compliant,
                    unmapped_tempo_users,
                    week_start,
                    week_end,
                )
            )

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            stats = {
                "success": True,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration,
                "week_start": week_start.isoformat(),
                "week_end": week_end.isoformat(),
                "total_users": len(all_users),
                "compliant_users": len(compliant),
                "partial_users": len(partial),
                "non_compliant_users": len(non_compliant),
                "unmapped_tempo_users": len(unmapped_tempo_users),
                "compliance_percentage": (
                    (len(compliant) / len(all_users) * 100) if all_users else 0
                ),
            }

            logger.info(
                f"Time Tracking Compliance job completed successfully in {duration:.2f}s"
            )
            logger.info(f"Stats: {stats}")

            return stats

        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            logger.error(
                f"Time Tracking Compliance job failed after {duration:.2f}s: {e}",
                exc_info=True,
            )

            return {
                "success": False,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration,
                "error": str(e),
            }


def run_time_tracking_compliance():
    """
    Entry point for the Time Tracking Compliance job.
    This function is called by the scheduler.
    """
    try:
        job = TimeTrackingComplianceJob()
        return job.run()
    except Exception as e:
        logger.error(
            f"Failed to initialize or run Time Tracking Compliance job: {e}",
            exc_info=True,
        )
        return {
            "success": False,
            "error": str(e),
            "start_time": datetime.now().isoformat(),
            "end_time": datetime.now().isoformat(),
            "duration_seconds": 0,
        }


if __name__ == "__main__":
    # Allow running job manually for testing
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    print("Running Time Tracking Compliance job manually...")
    stats = run_time_tracking_compliance()
    print(f"\nJob completed: {stats}")
