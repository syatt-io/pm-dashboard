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
        """Send daily TODO digest to all configured channels."""
        try:
            logger.info("Sending daily TODO digest")

            summary = self.todo_manager.get_todo_summary()

            if summary.total == 0:
                # Send "no todos" message
                content = NotificationContent(
                    title="Daily TODO Digest",
                    body="🎉 No active TODOs today! Great job team!",
                    priority="normal"
                )
                await self.notifier.send_notification(content, channels=["slack"])
                return

            # Create digest content
            body = f"📋 *Daily TODO Digest - {datetime.now().strftime('%B %d, %Y')}*\n\n"
            body += f"📊 *Summary:*\n"
            body += f"• Total Active: {summary.total}\n"
            body += f"• Overdue: {summary.overdue}\n"
            body += f"• Due Today: {summary.due_today}\n"
            body += f"• Completed Today: {summary.completed_today}\n\n"

            # Add assignee breakdown
            if summary.by_assignee:
                body += "*By Team Member:*\n"
                for assignee, count in sorted(summary.by_assignee.items()):
                    body += f"• {assignee}: {count} items\n"

            content = NotificationContent(
                title="Daily TODO Digest",
                body=body,
                priority="high" if summary.overdue > 0 else "normal"
            )

            # Send to all channels
            await self.notifier.send_notification(content, channels=["slack", "email"])

            # Send Slack digest with interactive elements
            if self.slack_bot:
                await self.slack_bot.send_daily_digest()

            logger.info(f"Daily digest sent: {summary.total} active TODOs")

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

            # Get summary data
            summary = self.todo_manager.get_todo_summary()
            now = datetime.now()
            week_start = now - timedelta(days=7)

            # Get completed items from last week
            from main import TodoItem
            completed_last_week = self.todo_manager.session.query(TodoItem).filter(
                TodoItem.status == 'completed',
                TodoItem.updated_at >= week_start
            ).all()

            body = f"📊 *Weekly TODO Summary - Week of {week_start.strftime('%B %d, %Y')}*\n\n"

            body += f"*Current Status:*\n"
            body += f"• Active TODOs: {summary.total}\n"
            body += f"• Overdue: {summary.overdue}\n"
            body += f"• Due This Week: {summary.due_this_week}\n\n"

            body += f"*Last Week's Progress:*\n"
            body += f"• Completed: {len(completed_last_week)} items\n\n"

            # Top performers
            completion_by_user = {}
            for todo in completed_last_week:
                assignee = todo.assignee or 'Unknown'
                completion_by_user[assignee] = completion_by_user.get(assignee, 0) + 1

            if completion_by_user:
                body += "*Top Performers Last Week:*\n"
                sorted_performers = sorted(completion_by_user.items(), key=lambda x: x[1], reverse=True)
                for assignee, count in sorted_performers[:5]:
                    body += f"• {assignee}: {count} completed\n"

            # Areas needing attention
            if summary.overdue > 0:
                body += f"\n⚠️ *Attention Needed:* {summary.overdue} overdue items\n"

            body += f"\n📈 Keep up the great work!"

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
                        summary_body += f"  • Forecasted: {project['forecasted_hours']:.1f}h\n"
                        summary_body += f"  • Actual: {project['actual_hours']:.1f}h\n"
                        summary_body += f"  • Usage: {project['percentage']:.1f}%\n"

                # Only send notification if in production
                import os
                if os.getenv('FLASK_ENV') == 'production':
                    content = NotificationContent(
                        title="Tempo Hours Sync",
                        body=summary_body,
                        priority="normal"
                    )
                    asyncio.run(self.notifier.send_notification(content, channels=["slack"]))
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
                    asyncio.run(self.notifier.send_notification(content, channels=["slack"]))

        except Exception as e:
            logger.error(f"Error in scheduled Tempo sync: {e}")

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
                    INNER JOIN project_monthly_forecast pmf
                        ON p.key = pmf.project_key
                    WHERE p.is_active = true
                        AND pmf.month_year = :current_month
                        AND pmf.forecasted_hours > 0
                    ORDER BY p.name
                """), {"current_month": current_month})

                projects = []
                for row in result:
                    forecasted = float(row[2]) if row[2] else 0
                    actual = float(row[3]) if row[3] else 0

                    if forecasted > 0:
                        percentage = (actual / forecasted) * 100

                        # Color coding based on usage
                        if percentage >= 100:
                            emoji = "🔴"  # Red - over budget
                        elif percentage >= 80:
                            emoji = "🟡"  # Yellow - close to budget
                        else:
                            emoji = "🟢"  # Green - well within budget

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