"""
Tempo Hours Sync Job

Scheduled job to update current month and YTD hours from Tempo for all projects.
Runs nightly at 4am EST.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.integrations.tempo import TempoAPIClient

logger = logging.getLogger(__name__)


class TempoSyncJob:
    """Scheduled job to sync Tempo hours to database"""

    def __init__(self):
        self.tempo_client = TempoAPIClient()

        # Get database URL from environment
        self.database_url = os.getenv("DATABASE_URL")
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable is required")

        # Create database engine and session
        self.engine = create_engine(self.database_url)
        self.Session = sessionmaker(bind=self.engine)

    def get_active_projects(self) -> list:
        """Get list of active project keys from database"""
        session = self.Session()
        try:
            result = session.execute(
                text("SELECT key FROM projects WHERE is_active = true")
            )
            projects = [row[0] for row in result]
            logger.info(f"Found {len(projects)} active projects")
            return projects
        finally:
            session.close()

    def update_project_hours(
        self, current_month_hours: Dict[str, float], cumulative_hours: Dict[str, float]
    ) -> Dict[str, int]:
        """
        Update project hours in database.

        Args:
            current_month_hours: Dict of project_key -> current month hours
            cumulative_hours: Dict of project_key -> all-time cumulative hours

        Returns:
            Dict with update statistics
        """
        session = self.Session()
        updated_count = 0
        skipped_count = 0

        try:
            active_projects = self.get_active_projects()

            # Get current month (first day of month)
            now = datetime.now()
            current_month = datetime(now.year, now.month, 1).date()

            for project_key in active_projects:
                current = current_month_hours.get(project_key, 0)
                cumulative = cumulative_hours.get(project_key, 0)

                # Update cumulative hours in projects table
                session.execute(
                    text(
                        """
                        UPDATE projects
                        SET cumulative_hours = :cumulative,
                            updated_at = NOW()
                        WHERE key = :project_key
                    """
                    ),
                    {"cumulative": cumulative, "project_key": project_key},
                )

                # Upsert current month hours into project_monthly_forecast
                result = session.execute(
                    text(
                        """
                        INSERT INTO project_monthly_forecast
                            (project_key, month_year, actual_monthly_hours, updated_at)
                        VALUES
                            (:project_key, :month_year, :actual_hours, NOW())
                        ON CONFLICT (project_key, month_year)
                        DO UPDATE SET
                            actual_monthly_hours = :actual_hours,
                            updated_at = NOW()
                    """
                    ),
                    {
                        "project_key": project_key,
                        "month_year": current_month,
                        "actual_hours": current,
                    },
                )

                updated_count += 1
                logger.info(
                    f"Updated {project_key}: "
                    f"current_month={current:.2f}h, cumulative={cumulative:.2f}h"
                )

            session.commit()
            logger.info(
                f"Successfully updated {updated_count} projects, skipped {skipped_count}"
            )

            return {
                "updated": updated_count,
                "skipped": skipped_count,
                "total": len(active_projects),
            }

        except Exception as e:
            session.rollback()
            logger.error(f"Error updating project hours: {e}")
            raise
        finally:
            session.close()

    def _get_ytd_hours_optimized(self, active_projects: list) -> Dict[str, float]:
        """
        Get year-to-date hours for specific projects using server-side filtering.

        This is optimized to query each project individually using Tempo API v4's
        projectId parameter, reducing data transfer compared to fetching
        all worklogs and filtering client-side.

        Args:
            active_projects: List of project keys to fetch hours for

        Returns:
            Dictionary mapping project keys to YTD hours
        """
        from datetime import datetime

        # Year-to-date: Jan 1 of current year to today
        now = datetime.now()
        start_date = now.replace(month=1, day=1).strftime("%Y-%m-%d")
        today = now.strftime("%Y-%m-%d")
        ytd_hours = {}

        logger.info(
            f"Fetching YTD hours ({start_date} to {today}) for {len(active_projects)} projects individually..."
        )

        for idx, project_key in enumerate(active_projects, 1):
            try:
                logger.info(
                    f"[{idx}/{len(active_projects)}] Fetching hours for {project_key}..."
                )

                # Use server-side project filtering (Tempo API v4 projectId parameter)
                worklogs = self.tempo_client.get_worklogs(
                    from_date=start_date, to_date=today, project_key=project_key
                )

                # Process worklogs for this project
                project_hours, processed, skipped = self.tempo_client.process_worklogs(
                    worklogs
                )

                # Store hours for this project (should only have one key)
                if project_key in project_hours:
                    ytd_hours[project_key] = project_hours[project_key]
                    logger.info(
                        f"  ✅ {project_key}: {project_hours[project_key]:.2f}h ({len(worklogs)} worklogs)"
                    )
                else:
                    # No worklogs for this project
                    ytd_hours[project_key] = 0.0
                    logger.info(f"  ℹ️  {project_key}: 0.00h (no worklogs)")

            except Exception as e:
                logger.error(
                    f"  ❌ Error fetching hours for {project_key}: {e}", exc_info=True
                )
                # Continue with next project instead of failing entire sync
                ytd_hours[project_key] = 0.0

        logger.info(f"Completed fetching hours for {len(ytd_hours)} projects")
        return ytd_hours

    def _get_project_hours_summary(self):
        """Get summary of actual vs forecasted hours for current month."""
        try:
            now = datetime.now()
            current_month = datetime(now.year, now.month, 1).date()

            with self.engine.connect() as conn:
                result = conn.execute(
                    text(
                        """
                    SELECT
                        p.key,
                        p.name,
                        pmf.forecasted_hours,
                        pmf.actual_monthly_hours
                    FROM projects p
                    LEFT JOIN project_monthly_forecast pmf
                        ON p.key = pmf.project_key
                        AND pmf.month_year = :current_month
                    WHERE p.is_active = true
                        AND (
                            pmf.actual_monthly_hours > 0
                            OR pmf.forecasted_hours > 0
                        )
                    ORDER BY p.name
                """
                    ),
                    {"current_month": current_month},
                )

                projects = []
                for row in result:
                    forecasted = float(row[2]) if row[2] else 0
                    actual = float(row[3]) if row[3] else 0

                    # Show all projects with actual hours or forecasted hours
                    if actual > 0 or forecasted > 0:
                        if forecasted > 0:
                            percentage = (actual / forecasted) * 100

                            # Color coding based on usage
                            if percentage >= 100:
                                emoji = "🔴"  # Red - over budget
                            elif percentage >= 80:
                                emoji = "🟡"  # Yellow - close to budget
                            else:
                                emoji = "🟢"  # Green - well within budget
                        else:
                            # No forecast, just show actual hours
                            percentage = 0
                            emoji = "⚪"  # White - no forecast

                        projects.append(
                            {
                                "key": row[0],
                                "name": row[1],
                                "forecasted_hours": forecasted,
                                "actual_hours": actual,
                                "percentage": percentage,
                                "emoji": emoji,
                            }
                        )

                return projects

        except Exception as e:
            logger.error(f"Error getting project hours summary: {e}")
            return []

    def send_slack_notification(self, stats: Dict):
        """
        Send Slack notification about Tempo sync completion.
        Sends personalized DMs to opted-in users with their watched projects.

        Args:
            stats: Dictionary containing job execution statistics
        """
        # Log IMMEDIATELY before any other operations
        print(f"[TEMPO_SYNC_DEBUG] send_slack_notification() called with stats: {stats}")
        logger.info(f"[TEMPO_SYNC_DEBUG] send_slack_notification() method invoked")

        try:
            logger.info("Preparing Tempo sync notification...")

            # Get project hours summary from database
            project_summary = self._get_project_hours_summary()

            # Build summary message
            summary_body = f"✅ *Tempo Hours Sync Completed*\n\n"
            summary_body += f"• Projects Updated: {stats['projects_updated']}\n"
            summary_body += f"• Duration: {stats['duration_seconds']:.1f}s\n"
            summary_body += (
                f"• Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
            )

            if stats.get("unique_projects_tracked", 0) > 0:
                summary_body += f"• Unique Projects Tracked: {stats['unique_projects_tracked']}\n"

            # Add project hours summary if available
            if project_summary:
                summary_body += (
                    f"\n📊 *{datetime.now().strftime('%B %Y')} Hours Summary:*\n"
                )

                for project in project_summary:
                    status_emoji = project["emoji"]
                    summary_body += (
                        f"\n{status_emoji} *{project['name']}* ({project['key']})\n"
                    )

                    if project["forecasted_hours"] > 0:
                        summary_body += (
                            f"  • Forecasted: {project['forecasted_hours']:.1f}h\n"
                        )
                        summary_body += (
                            f"  • Actual: {project['actual_hours']:.1f}h\n"
                        )
                        summary_body += f"  • Usage: {project['percentage']:.1f}%\n"
                    else:
                        # No forecast - just show actual hours
                        summary_body += (
                            f"  • Actual: {project['actual_hours']:.1f}h\n"
                        )
                        summary_body += f"  • (No forecast set)\n"

            # Send notification to opted-in users
            logger.info("Sending Tempo sync notification to opted-in users...")

            # Import notification manager
            from src.managers.notifications import NotificationManager
            from src.utils.database import session_scope
            from src.models.user import User, UserWatchedProject
            from sqlalchemy.orm import joinedload

            # Get notification manager instance
            notifier = NotificationManager()

            # Get opted-in users
            opted_in_users = []
            with session_scope() as db_session:
                # Get users who:
                # 1. Have notify_project_hours_forecast enabled
                # 2. Have a Slack user ID configured
                # 3. Are watching at least one project
                opted_in_users = (
                    db_session.query(User)
                    .options(joinedload(User.watched_projects))  # Eagerly load watched_projects
                    .join(
                        UserWatchedProject,
                        User.id == UserWatchedProject.user_id,
                    )
                    .filter(
                        User.notify_project_hours_forecast == True,
                        User.slack_user_id.isnot(None),
                    )
                    .distinct()  # Avoid duplicates if user watches multiple projects
                    .all()
                )

                # Convert watched_projects to simple data structure BEFORE expunge
                # This avoids SQLAlchemy detached instance errors
                for user in opted_in_users:
                    user.watched_project_keys = [
                        wp.project_key for wp in user.watched_projects
                    ]
                    db_session.expunge(user)

            logger.info(
                f"Found {len(opted_in_users)} users opted in for project hours forecast"
            )

            # Send DMs to opted-in users with personalized project summaries
            async def send_dms():
                for user in opted_in_users:
                    try:
                        # Get user's watched project keys
                        watched_project_keys = set(user.watched_project_keys)

                        # Filter project_summary to only include user's watched projects
                        user_projects = [
                            proj
                            for proj in project_summary
                            if proj["key"] in watched_project_keys
                        ]

                        # Skip if user has no relevant projects in this summary
                        if not user_projects:
                            logger.info(
                                f"Skipping user {user.email} - no watched projects in current summary"
                            )
                            continue

                        # Build personalized summary
                        personalized_body = (
                            f"✅ *Tempo Hours Sync Completed*\n\n"
                        )
                        personalized_body += f"• Projects Updated: {stats['projects_updated']}\n"
                        personalized_body += f"• Duration: {stats['duration_seconds']:.1f}s\n"
                        personalized_body += f"• Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC\n"

                        # Add personalized project hours summary
                        personalized_body += f"\n📊 *{datetime.now().strftime('%B %Y')} Hours Summary* (Your Watched Projects):\n"

                        for project in user_projects:
                            status_emoji = project["emoji"]
                            personalized_body += f"\n{status_emoji} *{project['name']}* ({project['key']})\n"

                            if project["forecasted_hours"] > 0:
                                personalized_body += f"  • Forecasted: {project['forecasted_hours']:.1f}h\n"
                                personalized_body += f"  • Actual: {project['actual_hours']:.1f}h\n"
                                personalized_body += f"  • Usage: {project['percentage']:.1f}%\n"
                            else:
                                # No forecast - just show actual hours
                                personalized_body += f"  • Actual: {project['actual_hours']:.1f}h\n"
                                personalized_body += (
                                    f"  • (No forecast set)\n"
                                )

                        await notifier._send_slack_dm(
                            slack_user_id=user.slack_user_id,
                            message=personalized_body,
                        )
                        logger.info(
                            f"Sent personalized project hours forecast DM to user {user.email} ({len(user_projects)} projects)"
                        )
                    except Exception as user_error:
                        logger.error(
                            f"Error sending project hours forecast to user {user.email}: {user_error}"
                        )

            asyncio.run(send_dms())
            logger.info(
                f"✅ Sent project hours forecast to {len(opted_in_users)} users"
            )

        except Exception as e:
            logger.error(
                f"❌ Failed to send Tempo sync notification: {e}",
                exc_info=True,
            )
            # Don't re-raise - notification failure shouldn't fail the job

    def run(self) -> Dict:
        """
        Execute the Tempo sync job.

        Returns:
            Dict with job execution statistics
        """
        start_time = datetime.now()
        logger.info(f"Starting Tempo sync job at {start_time}")

        try:
            # Get list of active projects first
            active_projects = self.get_active_projects()
            logger.info(f"Syncing hours for {len(active_projects)} active projects")

            # Fetch current month hours (no filter - still fast)
            logger.info("Fetching current month hours from Tempo...")
            current_month_hours = self.tempo_client.get_current_month_hours()

            # Fetch year-to-date hours per project using server-side filtering
            # OPTIMIZATION: Query each project individually instead of fetching ALL worklogs
            # Uses Tempo API v4 projectId filter to reduce data transfer
            logger.info(
                f"Fetching year-to-date hours from Tempo for {len(active_projects)} projects (optimized)..."
            )
            cumulative_hours = self._get_ytd_hours_optimized(active_projects)

            # Update database
            logger.info("Updating database...")
            update_stats = self.update_project_hours(
                current_month_hours, cumulative_hours
            )

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            stats = {
                "success": True,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration,
                "projects_updated": update_stats["updated"],
                "projects_skipped": update_stats["skipped"],
                "total_projects": update_stats["total"],
                "unique_projects_tracked": len(current_month_hours),
            }

            logger.info(f"Tempo sync job completed successfully in {duration:.2f}s")
            logger.info(f"Stats: {stats}")

            # Send Slack notification on success
            logger.info("[TEMPO_SYNC_DEBUG] About to call send_slack_notification()")
            print(f"[TEMPO_SYNC_DEBUG] About to call send_slack_notification() with stats: {stats}")
            try:
                self.send_slack_notification(stats)
                logger.info("[TEMPO_SYNC_DEBUG] send_slack_notification() completed successfully")
            except Exception as notif_error:
                logger.error(
                    f"[TEMPO_SYNC_DEBUG] Failed to send success notification (job still succeeded): {notif_error}",
                    exc_info=True,
                )
                print(f"[TEMPO_SYNC_DEBUG] Exception in send_slack_notification: {notif_error}")

            return stats

        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            logger.error(f"Tempo sync job failed after {duration:.2f}s: {e}")

            error_stats = {
                "success": False,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration,
                "error": str(e),
            }

            # Send Slack notification on failure
            try:
                self.send_slack_notification(error_stats)
            except Exception as notif_error:
                logger.error(
                    f"Failed to send failure notification: {notif_error}",
                    exc_info=True,
                )

            return error_stats


def run_tempo_sync():
    """
    Entry point for the Tempo sync job.
    This function is called by the scheduler.
    """
    try:
        job = TempoSyncJob()
        return job.run()
    except Exception as e:
        logger.error(f"Failed to initialize or run Tempo sync job: {e}", exc_info=True)
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

    print("Running Tempo sync job manually...")
    stats = run_tempo_sync()
    print(f"\nJob completed: {stats}")
