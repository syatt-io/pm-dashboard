"""Scheduled tasks for TODO reminders and notifications."""

import asyncio
import logging
import schedule
import time
from datetime import datetime, timedelta
from threading import Thread
from typing import Optional

from config.settings import settings
from src.managers.todo_manager import TodoManager
from src.managers.notifications import NotificationManager, NotificationContent
from src.managers.slack_bot import SlackTodoBot
from src.services.hours_report_agent import HoursReportAgent
from src.integrations.jira_mcp import JiraMCPClient
from src.jobs.tempo_sync import run_tempo_sync
from src.services.insight_detector import detect_insights_for_all_users
from src.services.daily_brief_generator import send_daily_briefs
from src.services.auto_escalation import AutoEscalationService


logger = logging.getLogger(__name__)


class TodoScheduler:
    """Scheduler for TODO reminders and automated notifications."""

    def __init__(self):
        """Initialize scheduler with managers."""
        self.todo_manager = TodoManager()
        self.notifier = NotificationManager(settings.notifications)
        self.slack_bot = None
        self.hours_report_agent = None
        self.running = False
        self.thread = None

        # Initialize Slack bot if available
        if settings.notifications.slack_bot_token:
            try:
                self.slack_bot = SlackTodoBot(
                    bot_token=settings.notifications.slack_bot_token,
                    signing_secret=getattr(settings.notifications, 'slack_signing_secret', 'dummy_secret')
                )
            except Exception as e:
                logger.warning(f"Could not initialize Slack bot for scheduler: {e}")

        # Initialize hours report agent
        try:
            async def create_jira_client():
                return JiraMCPClient(
                    jira_url=settings.jira.url,
                    username=settings.jira.username,
                    api_token=settings.jira.api_token
                )

            # Create a mock client for sync initialization
            self.hours_report_agent = HoursReportAgent(
                jira_client=None,  # Will be created in async context
                notification_manager=self.notifier,
                database_url=settings.agent.database_url
            )
        except Exception as e:
            logger.warning(f"Could not initialize hours report agent: {e}")

        self._setup_schedules()

    def _setup_schedules(self):
        """Set up scheduled tasks."""
        # Daily digest at 9 AM
        schedule.every().day.at("09:00").do(self._run_async, self.send_daily_digest)

        # Overdue reminders at 10 AM and 2 PM
        schedule.every().day.at("10:00").do(self._run_async, self.send_overdue_reminders)
        schedule.every().day.at("14:00").do(self._run_async, self.send_overdue_reminders)

        # Due today reminders at 9:30 AM
        schedule.every().day.at("09:30").do(self._run_async, self.send_due_today_reminders)

        # Weekly summary on Mondays at 9 AM
        schedule.every().monday.at("09:00").do(self._run_async, self.send_weekly_summary)

        # Weekly hours reports on Mondays at 10 AM
        schedule.every().monday.at("10:00").do(self._run_async, self.send_weekly_hours_reports)

        # Check for urgent items every 2 hours during work hours
        for hour in [9, 11, 13, 15, 17]:
            schedule.every().day.at(f"{hour:02d}:00").do(self._run_async, self.check_urgent_items)

        # Tempo hours sync at 4 AM EST (9 AM UTC)
        # Note: This runs at 9 AM UTC which is 4 AM EST (during DST) or 10 AM UTC for standard time
        schedule.every().day.at("09:00").do(self._run_sync, self.sync_tempo_hours)

        # Proactive insights detection every 4 hours during work hours (8am, 12pm, 4pm EST)
        schedule.every().day.at("08:00").do(self._run_sync, self.detect_proactive_insights)
        schedule.every().day.at("12:00").do(self._run_sync, self.detect_proactive_insights)
        schedule.every().day.at("16:00").do(self._run_sync, self.detect_proactive_insights)

        # Daily brief delivery - check hourly to handle different user timezones
        # Primary delivery at 9 AM EST
        schedule.every().day.at("09:00").do(self._run_sync, self.send_proactive_briefs)

        # Auto-escalation checks every 6 hours (6am, 12pm, 6pm, 12am EST)
        schedule.every().day.at("06:00").do(self._run_sync, self.run_auto_escalation)
        schedule.every().day.at("12:00").do(self._run_sync, self.run_auto_escalation)
        schedule.every().day.at("18:00").do(self._run_sync, self.run_auto_escalation)
        schedule.every().day.at("00:00").do(self._run_sync, self.run_auto_escalation)

        logger.info("Scheduled tasks configured")

    def _run_async(self, async_func, *args, **kwargs):
        """Run async function in event loop."""
        try:
            asyncio.run(async_func(*args, **kwargs))
        except Exception as e:
            logger.error(f"Error running scheduled task {async_func.__name__}: {e}")

    def _run_sync(self, sync_func, *args, **kwargs):
        """Run synchronous function."""
        try:
            sync_func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error running scheduled task {sync_func.__name__}: {e}")

    def start(self):
        """Start the scheduler in a background thread."""
        if self.running:
            logger.warning("Scheduler is already running")
            return

        self.running = True
        self.thread = Thread(target=self._run_scheduler, daemon=True)
        self.thread.start()
        logger.info("TODO scheduler started")

    def stop(self):
        """Stop the scheduler."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("TODO scheduler stopped")

    def _run_scheduler(self):
        """Run the scheduler loop."""
        while self.running:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                time.sleep(60)

    async def send_daily_digest(self):
        """Send daily TODO digest to all configured channels and individual DMs."""
        try:
            logger.info("Sending daily TODO digest")

            # Get all active todos
            active_todos = self.todo_manager.get_active_todos(limit=100)

            # Get users who have opted in for daily TODO digest
            from src.utils.database import session_scope
            from src.models.user import User

            opted_in_users = []
            with session_scope() as db_session:
                opted_in_users = db_session.query(User).filter(
                    User.notify_daily_todo_digest == True,
                    User.slack_user_id.isnot(None)
                ).all()

                # Detach users from session to use them outside the context
                for user in opted_in_users:
                    db_session.expunge(user)

            logger.info(f"Found {len(opted_in_users)} users opted in for daily TODO digest")

            # Send individual DMs to opted-in users
            for user in opted_in_users:
                try:
                    # Filter TODOs for this specific user
                    user_todos = [todo for todo in active_todos if todo.assignee == user.email or todo.assignee == user.name]

                    if not user_todos:
                        # Send "no todos" message to user
                        user_body = f"📋 *Daily TODO Digest - {datetime.now().strftime('%B %d, %Y')}*\n\n"
                        user_body += "🎉 No active TODOs assigned to you today! Great job!"
                    else:
                        # Group user's TODOs by project
                        todos_by_project = {}
                        for todo in user_todos:
                            project = todo.project_key or "No Project"
                            if project not in todos_by_project:
                                todos_by_project[project] = []
                            todos_by_project[project].append(todo)

                        # Create digest content for user
                        user_body = f"📋 *Daily TODO Digest - {datetime.now().strftime('%B %d, %Y')}*\n\n"
                        user_body += f"You have {len(user_todos)} active TODO(s):\n\n"

                        # Show TODOs grouped by project
                        for project in sorted(todos_by_project.keys()):
                            todos = todos_by_project[project]
                            user_body += f"*{project}*\n"
                            for todo in todos:
                                user_body += f"• {todo.title}"
                                if todo.description:
                                    # Truncate description to 50 chars
                                    desc = todo.description[:50] + "..." if len(todo.description) > 50 else todo.description
                                    user_body += f" - {desc}"
                                user_body += "\n"
                            user_body += "\n"

                    # Send DM to user
                    await self.notifier._send_slack_dm(
                        slack_user_id=user.slack_user_id,
                        message=user_body
                    )
                    logger.info(f"Sent daily digest DM to user {user.email} ({len(user_todos)} TODOs)")

                except Exception as user_error:
                    logger.error(f"Error sending daily digest to user {user.email}: {user_error}")

            # Also send system-wide digest to channel (for admins/monitoring)
            if not active_todos:
                # Send "no todos" message
                content = NotificationContent(
                    title="Daily TODO Digest",
                    body="🎉 No active TODOs today! Great job team!",
                    priority="normal"
                )
                await self.notifier.send_notification(content, channels=["slack"])
                return

            # Group TODOs by project for system-wide message
            todos_by_project = {}
            for todo in active_todos:
                project = todo.project_key or "No Project"
                if project not in todos_by_project:
                    todos_by_project[project] = []
                todos_by_project[project].append(todo)

            # Create minimal digest content
            body = f"📋 *Daily TODO Digest - {datetime.now().strftime('%B %d, %Y')}*\n\n"

            # Show TODOs grouped by project
            for project in sorted(todos_by_project.keys()):
                todos = todos_by_project[project]
                body += f"*{project}*\n"
                for todo in todos:
                    assignee = todo.assignee or "Unassigned"
                    body += f"• {todo.title}"
                    if todo.description:
                        # Truncate description to 50 chars
                        desc = todo.description[:50] + "..." if len(todo.description) > 50 else todo.description
                        body += f" - {desc}"
                    body += f" ({assignee})\n"
                body += "\n"

            content = NotificationContent(
                title="Daily TODO Digest",
                body=body,
                priority="normal"
            )

            # Send to all channels (system-wide)
            await self.notifier.send_notification(content, channels=["slack"])

            logger.info(f"Daily digest sent: {len(active_todos)} active TODOs, {len(opted_in_users)} users notified")

        except Exception as e:
            logger.error(f"Error sending daily digest: {e}")

    async def send_overdue_reminders(self):
        """Send reminders for overdue TODOs."""
        try:
            overdue_todos = self.todo_manager.get_overdue_todos()

            if not overdue_todos:
                logger.info("No overdue TODOs found")
                return

            # Group by assignee
            by_assignee = {}
            for todo in overdue_todos:
                assignee = todo.assignee or 'Unassigned'
                if assignee not in by_assignee:
                    by_assignee[assignee] = []
                by_assignee[assignee].append(todo)

            # Send individual reminders
            for assignee, todos in by_assignee.items():
                if assignee == 'Unassigned':
                    continue

                await self.todo_manager._send_overdue_reminder(assignee, todos)

            # Send team summary for all overdue items
            if len(overdue_todos) > 3:  # Only if significant number
                body = f"⚠️ *Team Overdue Alert*\n\n"
                body += f"There are {len(overdue_todos)} overdue TODO items across the team.\n\n"

                body += "*Most Overdue:*\n"
                for todo in sorted(overdue_todos, key=lambda t: t.due_date)[:5]:
                    days_overdue = (datetime.now() - todo.due_date).days
                    body += f"• {todo.title} - {days_overdue} days ({todo.assignee or 'Unassigned'})\n"

                content = NotificationContent(
                    title="Team Overdue Alert",
                    body=body,
                    priority="high"
                )

                await self.notifier.send_notification(content, channels=["slack"])

            logger.info(f"Overdue reminders sent for {len(overdue_todos)} items")

        except Exception as e:
            logger.error(f"Error sending overdue reminders: {e}")

    async def send_due_today_reminders(self):
        """Send reminders for TODOs due today."""
        try:
            now = datetime.now()
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            today_end = today_start + timedelta(days=1)

            # Get TODOs due today
            due_today = []
            active_todos = self.todo_manager.get_active_todos()

            for todo in active_todos:
                if todo.due_date and today_start <= todo.due_date < today_end:
                    due_today.append(todo)

            if not due_today:
                logger.info("No TODOs due today")
                return

            # Group by assignee
            by_assignee = {}
            for todo in due_today:
                assignee = todo.assignee or 'Unassigned'
                if assignee not in by_assignee:
                    by_assignee[assignee] = []
                by_assignee[assignee].append(todo)

            # Send individual reminders
            for assignee, todos in by_assignee.items():
                if assignee == 'Unassigned':
                    continue

                body = f"📅 *Items Due Today for {assignee}*\n\n"
                for todo in todos:
                    body += f"• {todo.title}\n"
                    if todo.description:
                        body += f"  _{todo.description[:100]}{'...' if len(todo.description) > 100 else ''}_\n"

                body += f"\n💡 Use the TODO dashboard to manage these items."

                content = NotificationContent(
                    title="TODOs Due Today",
                    body=body,
                    priority="normal"
                )

                await self.notifier.send_notification(content, channels=["slack"])

            logger.info(f"Due today reminders sent for {len(due_today)} items")

        except Exception as e:
            logger.error(f"Error sending due today reminders: {e}")

    async def send_weekly_summary(self):
        """Send weekly TODO summary."""
        try:
            logger.info("Sending weekly TODO summary")

            # Get all active todos
            active_todos = self.todo_manager.get_active_todos(limit=100)
            now = datetime.now()
            week_start = now - timedelta(days=7)

            # Get completed items from last week
            from main import TodoItem
            completed_last_week = self.todo_manager.session.query(TodoItem).filter(
                TodoItem.status == 'completed',
                TodoItem.updated_at >= week_start
            ).all()

            body = f"📊 *Weekly TODO Summary - Week of {week_start.strftime('%B %d, %Y')}*\n\n"

            # Show completed items grouped by project
            if completed_last_week:
                body += f"*✅ Completed Last Week ({len(completed_last_week)} items):*\n\n"
                completed_by_project = {}
                for todo in completed_last_week:
                    project = todo.project_key or "No Project"
                    if project not in completed_by_project:
                        completed_by_project[project] = []
                    completed_by_project[project].append(todo)

                for project in sorted(completed_by_project.keys()):
                    todos = completed_by_project[project]
                    body += f"*{project}*\n"
                    for todo in todos:
                        assignee = todo.assignee or "Unassigned"
                        body += f"• {todo.title} ({assignee})\n"
                    body += "\n"

            # Show active TODOs grouped by project
            if active_todos:
                body += f"*📋 Active TODOs ({len(active_todos)} items):*\n\n"
                todos_by_project = {}
                for todo in active_todos:
                    project = todo.project_key or "No Project"
                    if project not in todos_by_project:
                        todos_by_project[project] = []
                    todos_by_project[project].append(todo)

                for project in sorted(todos_by_project.keys()):
                    todos = todos_by_project[project]
                    body += f"*{project}*\n"
                    for todo in todos:
                        assignee = todo.assignee or "Unassigned"
                        body += f"• {todo.title}"
                        if todo.description:
                            desc = todo.description[:50] + "..." if len(todo.description) > 50 else todo.description
                            body += f" - {desc}"
                        body += f" ({assignee})\n"
                    body += "\n"

            if not completed_last_week and not active_todos:
                body += "🎉 No TODOs to report! Great job team!\n"

            content = NotificationContent(
                title="Weekly TODO Summary",
                body=body,
                priority="normal"
            )

            await self.notifier.send_notification(content, channels=["slack", "email"])

            logger.info("Weekly summary sent")

        except Exception as e:
            logger.error(f"Error sending weekly summary: {e}")

    async def check_urgent_items(self):
        """Check for urgent items that need immediate attention."""
        try:
            # Check for high priority overdue items
            overdue_todos = self.todo_manager.get_overdue_todos()
            urgent_items = [
                todo for todo in overdue_todos
                if getattr(todo, 'priority', 'Medium') == 'High'
                and (datetime.now() - todo.due_date).days >= 1
            ]

            if not urgent_items:
                return

            body = f"🚨 *URGENT ITEMS REQUIRING ATTENTION* 🚨\n\n"
            body += f"The following high-priority items are overdue:\n\n"

            for todo in urgent_items[:5]:
                days_overdue = (datetime.now() - todo.due_date).days
                body += f"• *{todo.title}*\n"
                body += f"  Assignee: {todo.assignee or 'Unassigned'}\n"
                body += f"  Overdue: {days_overdue} days\n\n"

            body += "Please address these items immediately or update their status."

            content = NotificationContent(
                title="URGENT: High Priority Items Overdue",
                body=body,
                priority="urgent"
            )

            await self.notifier.send_notification(content, channels=["slack", "email"])

            logger.warning(f"Urgent alert sent for {len(urgent_items)} high-priority overdue items")

        except Exception as e:
            logger.error(f"Error checking urgent items: {e}")

    async def send_completion_celebration(self, todo_title: str, assignee: str):
        """Send celebration message for completed TODO."""
        try:
            content = NotificationContent(
                title="TODO Completed! 🎉",
                body=f"✅ *{todo_title}* completed by {assignee}\n\nGreat work!",
                priority="normal"
            )

            await self.notifier.send_notification(content, channels=["slack"])

        except Exception as e:
            logger.error(f"Error sending completion celebration: {e}")

    async def send_custom_reminder(self, assignee: str, message: str, priority: str = "normal"):
        """Send custom reminder to specific user."""
        try:
            content = NotificationContent(
                title=f"Reminder for {assignee}",
                body=message,
                priority=priority
            )

            await self.notifier.send_notification(content, channels=["slack"])

        except Exception as e:
            logger.error(f"Error sending custom reminder: {e}")

    async def send_weekly_hours_reports(self):
        """Send weekly hours tracking reports for all active projects."""
        if not self.hours_report_agent:
            logger.warning("Hours report agent not initialized, skipping weekly reports")
            return

        try:
            logger.info("Starting weekly hours tracking reports")

            # Create Jira client for the report agent
            async with JiraMCPClient(
                jira_url=settings.jira.url,
                username=settings.jira.username,
                api_token=settings.jira.api_token
            ) as jira_client:
                # Update the agent's jira client
                self.hours_report_agent.jira_client = jira_client

                # Generate and send reports
                result = await self.hours_report_agent.send_weekly_reports()

                logger.info(f"Weekly hours reports completed: {result['emails_sent']} emails sent for {result['total_projects']} projects")

                # Send summary to team if there were any reports
                if result['total_projects'] > 0:
                    summary_body = f"📊 *Weekly Hours Reports Summary*\n\n"
                    summary_body += f"• Reports generated for {result['total_projects']} active projects\n"
                    summary_body += f"• {result['emails_sent']} notification emails sent\n"

                    if result['errors'] > 0:
                        summary_body += f"• ⚠️ {result['errors']} errors occurred\n"

                    # Add project status overview
                    on_track = sum(1 for r in result['reports'] if r['status'] == 'on_track')
                    over_budget = sum(1 for r in result['reports'] if r['status'] == 'over_budget')
                    under_utilized = sum(1 for r in result['reports'] if r['status'] == 'under_utilized')

                    summary_body += f"\n📈 *Project Status Overview:*\n"
                    summary_body += f"• ✅ On Track: {on_track}\n"
                    summary_body += f"• ⚠️ Over Budget: {over_budget}\n"
                    summary_body += f"• 📉 Under Utilized: {under_utilized}\n"

                    if over_budget > 0:
                        summary_body += f"\n🚨 *Projects requiring attention:*\n"
                        for report in result['reports']:
                            if report['status'] == 'over_budget':
                                summary_body += f"• {report['project_name']}: {report['usage_percentage']:.1f}% usage\n"

                    content = NotificationContent(
                        title="Weekly Hours Reports Summary",
                        body=summary_body,
                        priority="normal"
                    )

                    await self.notifier.send_notification(content, channels=["slack"])

        except Exception as e:
            logger.error(f"Error sending weekly hours reports: {e}")

    def sync_tempo_hours(self):
        """Sync Tempo hours to database (synchronous wrapper)."""
        try:
            logger.info("Starting scheduled Tempo hours sync")
            stats = run_tempo_sync()

            if stats.get("success"):
                logger.info(
                    f"Tempo sync completed successfully: "
                    f"{stats['projects_updated']} projects updated in {stats['duration_seconds']:.2f}s"
                )

                # Get project hours summary from database
                project_summary = self._get_project_hours_summary()

                # Send notification about sync completion with project status
                summary_body = f"✅ *Tempo Hours Sync Completed*\n\n"
                summary_body += f"• Projects Updated: {stats['projects_updated']}\n"
                summary_body += f"• Duration: {stats['duration_seconds']:.1f}s\n"
                summary_body += f"• Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC\n"

                if stats.get('unique_projects_tracked', 0) > 0:
                    summary_body += f"• Unique Projects Tracked: {stats['unique_projects_tracked']}\n"

                # Add project hours summary if available
                if project_summary:
                    summary_body += f"\n📊 *{datetime.now().strftime('%B %Y')} Hours Summary:*\n"

                    for project in project_summary:
                        status_emoji = project['emoji']
                        summary_body += f"\n{status_emoji} *{project['name']}* ({project['key']})\n"

                        if project['forecasted_hours'] > 0:
                            summary_body += f"  • Forecasted: {project['forecasted_hours']:.1f}h\n"
                            summary_body += f"  • Actual: {project['actual_hours']:.1f}h\n"
                            summary_body += f"  • Usage: {project['percentage']:.1f}%\n"
                        else:
                            # No forecast - just show actual hours
                            summary_body += f"  • Actual: {project['actual_hours']:.1f}h\n"
                            summary_body += f"  • (No forecast set)\n"

                # Only send notification if in production
                import os
                flask_env = os.getenv('FLASK_ENV')
                logger.info(f"FLASK_ENV={flask_env}, checking if should send notification...")
                if flask_env == 'production':
                    logger.info("Sending Tempo sync notification to Slack...")
                    content = NotificationContent(
                        title="Tempo Hours Sync",
                        body=summary_body,
                        priority="normal"
                    )
                    try:
                        # Send system-wide notification to channel
                        asyncio.run(self.notifier.send_notification(content, channels=["slack"]))
                        logger.info("✅ Tempo sync notification sent to channel successfully")

                        # Send individual DMs to opted-in users
                        from src.utils.database import session_scope
                        from src.models.user import User

                        opted_in_users = []
                        with session_scope() as db_session:
                            opted_in_users = db_session.query(User).filter(
                                User.notify_project_hours_forecast == True,
                                User.slack_user_id.isnot(None)
                            ).all()

                            # Detach users from session to use them outside the context
                            for user in opted_in_users:
                                db_session.expunge(user)

                        logger.info(f"Found {len(opted_in_users)} users opted in for project hours forecast")

                        # Send DMs to opted-in users
                        async def send_dms():
                            for user in opted_in_users:
                                try:
                                    await self.notifier._send_slack_dm(
                                        slack_user_id=user.slack_user_id,
                                        message=summary_body
                                    )
                                    logger.info(f"Sent project hours forecast DM to user {user.email}")
                                except Exception as user_error:
                                    logger.error(f"Error sending project hours forecast to user {user.email}: {user_error}")

                        asyncio.run(send_dms())
                        logger.info(f"✅ Sent project hours forecast to {len(opted_in_users)} users")

                    except Exception as notif_error:
                        logger.error(f"❌ Failed to send Tempo sync notification: {notif_error}", exc_info=True)
                        # Re-raise to ensure Celery task is marked as failed
                        raise
                else:
                    logger.info(f"Skipping notification (not in production, FLASK_ENV={flask_env})")
            else:
                error_msg = stats.get("error", "Unknown error")
                logger.error(f"Tempo sync failed: {error_msg}")

                # Send error notification
                content = NotificationContent(
                    title="⚠️ Tempo Hours Sync Failed",
                    body=f"Error: {error_msg}\n\nPlease check logs for details.",
                    priority="high"
                )

                import os
                if os.getenv('FLASK_ENV') == 'production':
                    try:
                        asyncio.run(self.notifier.send_notification(content, channels=["slack"]))
                    except Exception as notif_error:
                        logger.error(f"❌ Failed to send error notification: {notif_error}", exc_info=True)

                # Raise exception to mark Celery task as failed
                raise Exception(f"Tempo sync failed: {error_msg}")

        except Exception as e:
            logger.error(f"Error in scheduled Tempo sync: {e}", exc_info=True)

            # Send critical error notification
            import os
            if os.getenv('FLASK_ENV') == 'production':
                try:
                    content = NotificationContent(
                        title="🚨 Tempo Hours Sync Critical Error",
                        body=f"Critical error occurred during Tempo sync:\n\n{str(e)}\n\nPlease check logs immediately.",
                        priority="urgent"
                    )
                    asyncio.run(self.notifier.send_notification(content, channels=["slack"]))
                except Exception as notif_error:
                    logger.error(f"❌ Failed to send critical error notification: {notif_error}", exc_info=True)

            # Re-raise exception to ensure Celery task is marked as failed
            raise

    def _get_project_hours_summary(self):
        """Get summary of actual vs forecasted hours for current month."""
        try:
            from sqlalchemy import text
            from src.utils.database import get_engine

            engine = get_engine()
            now = datetime.now()
            current_month = datetime(now.year, now.month, 1).date()

            with engine.connect() as conn:
                result = conn.execute(text("""
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
                """), {"current_month": current_month})

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

                        projects.append({
                            'key': row[0],
                            'name': row[1],
                            'forecasted_hours': forecasted,
                            'actual_hours': actual,
                            'percentage': percentage,
                            'emoji': emoji
                        })

                return projects

        except Exception as e:
            logger.error(f"Error getting project hours summary: {e}")
            return []

    def detect_proactive_insights(self):
        """Run proactive insight detection for all users."""
        try:
            logger.info("Running proactive insight detection")
            stats = detect_insights_for_all_users()
            logger.info(f"Insight detection complete: {stats}")

            # Send Slack notification if enabled
            if stats['insights_detected'] > 0 and self.slack_bot:
                message = (
                    f"🔍 *Proactive Insight Detection Complete*\n\n"
                    f"• Users processed: {stats['users_processed']}\n"
                    f"• Insights detected: {stats['insights_detected']}\n"
                    f"• Insights stored: {stats['insights_stored']}\n"
                )
                if stats['errors']:
                    message += f"• Errors: {len(stats['errors'])}\n"

                try:
                    self.slack_bot.post_message(
                        channel=settings.notifications.slack_channel,
                        text=message
                    )
                except Exception as e:
                    logger.error(f"Error sending Slack notification: {e}")

        except Exception as e:
            logger.error(f"Error in proactive insight detection: {e}", exc_info=True)

    def send_proactive_briefs(self):
        """Send daily briefs to all users."""
        try:
            logger.info("Running daily brief delivery")
            stats = send_daily_briefs()
            logger.info(f"Daily brief delivery complete: {stats}")

            # Send Slack notification if enabled
            if (stats['briefs_sent_slack'] > 0 or stats['briefs_sent_email'] > 0) and self.slack_bot:
                message = (
                    f"📬 *Daily Brief Delivery Complete*\n\n"
                    f"• Users processed: {stats['users_processed']}\n"
                    f"• Briefs sent via Slack: {stats['briefs_sent_slack']}\n"
                    f"• Briefs sent via Email: {stats['briefs_sent_email']}\n"
                    f"• Total insights delivered: {stats['total_insights_delivered']}\n"
                )
                if stats['errors']:
                    message += f"• Errors: {len(stats['errors'])}\n"

                try:
                    self.slack_bot.post_message(
                        channel=settings.notifications.slack_channel,
                        text=message
                    )
                except Exception as e:
                    logger.error(f"Error sending Slack notification: {e}")

        except Exception as e:
            logger.error(f"Error in daily brief delivery: {e}", exc_info=True)

    def run_auto_escalation(self):
        """Run auto-escalation check for stale insights."""
        try:
            logger.info("Running auto-escalation check")

            from src.utils.database import session_scope

            with session_scope() as db:
                escalation_service = AutoEscalationService(db)
                stats = escalation_service.run_escalation_check()

            logger.info(f"Auto-escalation check complete: {stats}")

            # Send Slack notification if escalations were performed
            if stats['escalations_performed'] > 0 and self.slack_bot:
                message = (
                    f"🚨 *Auto-Escalation Summary*\n\n"
                    f"• Insights checked: {stats['total_checked']}\n"
                    f"• Escalations performed: {stats['escalations_performed']}\n"
                    f"• DMs sent: {stats['dm_sent']}\n"
                    f"• Channel posts: {stats['channel_posts']}\n"
                    f"• GitHub comments: {stats['github_comments']}\n"
                )
                if stats['errors'] > 0:
                    message += f"• Errors: {stats['errors']}\n"

                try:
                    self.slack_bot.post_message(
                        channel=settings.notifications.slack_channel,
                        text=message
                    )
                except Exception as e:
                    logger.error(f"Error sending Slack notification: {e}")

        except Exception as e:
            logger.error(f"Error in auto-escalation check: {e}", exc_info=True)


# Global scheduler instance
scheduler = None


def start_scheduler():
    """Start the global scheduler."""
    global scheduler
    if scheduler is None:
        scheduler = TodoScheduler()
        scheduler.start()
        logger.info("Global TODO scheduler started")
    else:
        logger.warning("Scheduler already started")


def stop_scheduler():
    """Stop the global scheduler."""
    global scheduler
    if scheduler:
        scheduler.stop()
        scheduler = None
        logger.info("Global TODO scheduler stopped")


def get_scheduler() -> Optional[TodoScheduler]:
    """Get the global scheduler instance."""
    return scheduler