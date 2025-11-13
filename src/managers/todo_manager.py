"""TODO management system for web UI and Slack integration."""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, and_, or_

from config.settings import settings
from src.models import TodoItem, Base
from src.managers.notifications import NotificationManager, NotificationContent


logger = logging.getLogger(__name__)


@dataclass
class TodoSummary:
    """Summary statistics for TODO items."""

    total: int
    overdue: int
    due_today: int
    due_this_week: int
    completed_today: int
    by_assignee: Dict[str, int]
    by_priority: Dict[str, int]


class TodoManager:
    """Manages TODO items across web UI and Slack."""

    def __init__(self):
        """Initialize TODO manager."""
        from src.utils.database import get_engine

        self.engine = get_engine()  # Use centralized engine with proper pool settings

        # Try to create tables, but don't fail if we don't have permissions
        try:
            Base.metadata.create_all(self.engine)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.warning(
                f"Could not create database tables (may already exist or lack permissions): {e}"
            )
            # Continue anyway - tables may already exist

        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        self.notifier = NotificationManager(settings.notifications)

    def get_active_todos(self, assignee: str = None, limit: int = 50) -> List[TodoItem]:
        """Get active TODO items."""
        query = self.session.query(TodoItem).filter(
            TodoItem.status.in_(["pending", "in_progress"])
        )

        if assignee:
            query = query.filter(TodoItem.assignee == assignee)

        return (
            query.order_by(
                TodoItem.due_date.asc().nullslast(), TodoItem.created_at.desc()
            )
            .limit(limit)
            .all()
        )

    def get_todo(self, todo_id: str) -> Optional[TodoItem]:
        """Get a single TODO by ID."""
        return self.session.query(TodoItem).filter(TodoItem.id == todo_id).first()

    def get_overdue_todos(self, assignee: str = None) -> List[TodoItem]:
        """Get overdue TODO items."""
        now = datetime.now()
        query = self.session.query(TodoItem).filter(
            and_(
                TodoItem.status.in_(["pending", "in_progress"]), TodoItem.due_date < now
            )
        )

        if assignee:
            query = query.filter(TodoItem.assignee == assignee)

        return query.order_by(TodoItem.due_date.asc()).all()

    def get_due_soon_todos(self, days: int = 3, assignee: str = None) -> List[TodoItem]:
        """Get TODO items due within specified days."""
        now = datetime.now()
        future = now + timedelta(days=days)

        query = self.session.query(TodoItem).filter(
            and_(
                TodoItem.status.in_(["pending", "in_progress"]),
                TodoItem.due_date >= now,
                TodoItem.due_date <= future,
            )
        )

        if assignee:
            query = query.filter(TodoItem.assignee == assignee)

        return query.order_by(TodoItem.due_date.asc()).all()

    def get_todo_summary(self) -> TodoSummary:
        """Get summary statistics for all TODOs."""
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        week_end = now + timedelta(days=7)

        # Active todos
        active_todos = (
            self.session.query(TodoItem)
            .filter(TodoItem.status.in_(["pending", "in_progress"]))
            .all()
        )

        # Overdue
        overdue = len([t for t in active_todos if t.due_date and t.due_date < now])

        # Due today
        due_today = len(
            [
                t
                for t in active_todos
                if t.due_date and today_start <= t.due_date < today_end
            ]
        )

        # Due this week
        due_week = len(
            [t for t in active_todos if t.due_date and now <= t.due_date <= week_end]
        )

        # Completed today
        completed_today = (
            self.session.query(TodoItem)
            .filter(
                and_(
                    TodoItem.status == "completed",
                    TodoItem.updated_at >= today_start,
                    TodoItem.updated_at < today_end,
                )
            )
            .count()
        )

        # By assignee
        by_assignee = {}
        for todo in active_todos:
            assignee = todo.assignee or "Unassigned"
            by_assignee[assignee] = by_assignee.get(assignee, 0) + 1

        # By priority
        by_priority = {"High": 0, "Medium": 0, "Low": 0}
        for todo in active_todos:
            priority = getattr(todo, "priority", "Medium") or "Medium"
            if priority in by_priority:
                by_priority[priority] += 1

        return TodoSummary(
            total=len(active_todos),
            overdue=overdue,
            due_today=due_today,
            due_this_week=due_week,
            completed_today=completed_today,
            by_assignee=by_assignee,
            by_priority=by_priority,
        )

    def complete_todo(
        self, todo_id: str, completed_by: str = None, notes: str = None
    ) -> bool:
        """Mark a TODO as complete."""
        try:
            todo = self.session.query(TodoItem).filter_by(id=todo_id).first()
            if not todo:
                return False

            todo.status = "completed"
            todo.updated_at = datetime.now()

            # Add completion notes if provided
            if notes:
                todo.description += f"\n\nCompleted: {notes}"

            self.session.commit()

            # Send notification
            asyncio.create_task(self._send_completion_notification(todo, completed_by))

            logger.info(f"TODO completed: {todo.title} by {completed_by}")
            return True

        except Exception as e:
            logger.error(f"Error completing TODO {todo_id}: {e}")
            self.session.rollback()
            return False

    def update_todo(self, todo_id: str, updates: Dict[str, Any]) -> bool:
        """Update a TODO item."""
        try:
            todo = self.session.query(TodoItem).filter_by(id=todo_id).first()
            if not todo:
                return False

            # Update allowed fields
            allowed_fields = [
                "title",
                "description",
                "assignee",
                "due_date",
                "status",
                "project_key",
            ]
            for field, value in updates.items():
                if field in allowed_fields and hasattr(todo, field):
                    if field == "due_date" and isinstance(value, str):
                        value = datetime.fromisoformat(value) if value else None
                    setattr(todo, field, value)

            todo.updated_at = datetime.now()
            self.session.commit()

            logger.info(f"TODO updated: {todo.title}")
            return True

        except Exception as e:
            logger.error(f"Error updating TODO {todo_id}: {e}")
            self.session.rollback()
            return False

    def snooze_todo(self, todo_id: str, days: int = 1) -> bool:
        """Snooze a TODO by extending its due date."""
        try:
            todo = self.session.query(TodoItem).filter_by(id=todo_id).first()
            if not todo:
                return False

            if todo.due_date:
                todo.due_date += timedelta(days=days)
            else:
                todo.due_date = datetime.now() + timedelta(days=days)

            todo.updated_at = datetime.now()
            self.session.commit()

            logger.info(f"TODO snoozed: {todo.title} for {days} days")
            return True

        except Exception as e:
            logger.error(f"Error snoozing TODO {todo_id}: {e}")
            self.session.rollback()
            return False

    def delete_todo(self, todo_id: str) -> bool:
        """Delete a TODO item."""
        try:
            todo = self.session.query(TodoItem).filter_by(id=todo_id).first()
            if not todo:
                return False

            self.session.delete(todo)
            self.session.commit()

            logger.info(f"TODO deleted: {todo.title}")
            return True

        except Exception as e:
            logger.error(f"Error deleting TODO {todo_id}: {e}")
            self.session.rollback()
            return False

    def get_todos_for_user(self, assignee: str) -> Dict[str, List[TodoItem]]:
        """Get categorized TODOs for a specific user."""
        user_todos = self.get_active_todos(assignee=assignee)

        return {
            "overdue": [
                t for t in user_todos if t.due_date and t.due_date < datetime.now()
            ],
            "due_today": [t for t in user_todos if self._is_due_today(t)],
            "due_soon": [t for t in user_todos if self._is_due_soon(t, days=3)],
            "other": [
                t
                for t in user_todos
                if not (
                    (t.due_date and t.due_date < datetime.now())
                    or self._is_due_today(t)
                    or self._is_due_soon(t, days=3)
                )
            ],
        }

    async def send_daily_todo_digest(self, assignee: str = None):
        """Send daily TODO digest via notifications."""
        summary = self.get_todo_summary()

        if assignee:
            user_todos = self.get_todos_for_user(assignee)
            await self._send_user_digest(assignee, user_todos)
        else:
            await self._send_team_digest(summary)

    async def send_overdue_reminders(self):
        """Send reminders for overdue items."""
        overdue_todos = self.get_overdue_todos()

        # Group by assignee
        by_assignee = {}
        for todo in overdue_todos:
            assignee = todo.assignee or "Unassigned"
            if assignee not in by_assignee:
                by_assignee[assignee] = []
            by_assignee[assignee].append(todo)

        # Send individual reminders
        for assignee, todos in by_assignee.items():
            if assignee != "Unassigned":
                await self._send_overdue_reminder(assignee, todos)

    def _is_due_today(self, todo: TodoItem) -> bool:
        """Check if TODO is due today."""
        if not todo.due_date:
            return False
        today = datetime.now().date()
        return todo.due_date.date() == today

    def _is_due_soon(self, todo: TodoItem, days: int = 3) -> bool:
        """Check if TODO is due within specified days."""
        if not todo.due_date:
            return False
        now = datetime.now()
        future = now + timedelta(days=days)
        return now <= todo.due_date <= future and not self._is_due_today(todo)

    async def _send_completion_notification(self, todo: TodoItem, completed_by: str):
        """Send notification when TODO is completed."""
        notification = NotificationContent(
            title="TODO Completed",
            body=f"✅ *{todo.title}* completed by {completed_by or todo.assignee}",
            priority="normal",
        )
        await self.notifier.send_notification(notification, channels=["slack"])

    async def _send_user_digest(self, assignee: str, todos: Dict[str, List[TodoItem]]):
        """Send personalized TODO digest to user."""
        total_count = sum(len(todo_list) for todo_list in todos.values())

        if total_count == 0:
            return

        body = f"📋 *Daily TODO Digest for {assignee}*\n\n"

        if todos["overdue"]:
            body += f"🚨 *{len(todos['overdue'])} Overdue Items*\n"
            for todo in todos["overdue"][:3]:
                body += f"  • {todo.title}\n"
            if len(todos["overdue"]) > 3:
                body += f"  • ... and {len(todos['overdue']) - 3} more\n"
            body += "\n"

        if todos["due_today"]:
            body += f"📅 *{len(todos['due_today'])} Due Today*\n"
            for todo in todos["due_today"]:
                body += f"  • {todo.title}\n"
            body += "\n"

        if todos["due_soon"]:
            body += f"⏰ *{len(todos['due_soon'])} Due This Week*\n"
            for todo in todos["due_soon"][:3]:
                days_left = (todo.due_date - datetime.now()).days
                body += f"  • {todo.title} (in {days_left} days)\n"

        notification = NotificationContent(
            title=f"TODO Digest - {assignee}", body=body, priority="normal"
        )
        await self.notifier.send_notification(notification, channels=["slack"])

    async def _send_team_digest(self, summary: TodoSummary):
        """Send team-wide TODO summary."""
        body = f"📊 *Team TODO Summary*\n\n"
        body += f"📋 Total Active: {summary.total}\n"
        body += f"🚨 Overdue: {summary.overdue}\n"
        body += f"📅 Due Today: {summary.due_today}\n"
        body += f"⏰ Due This Week: {summary.due_this_week}\n"
        body += f"✅ Completed Today: {summary.completed_today}\n\n"

        if summary.by_assignee:
            body += "*By Assignee:*\n"
            for assignee, count in sorted(summary.by_assignee.items()):
                body += f"  • {assignee}: {count} items\n"

        notification = NotificationContent(
            title="Team TODO Summary", body=body, priority="normal"
        )
        await self.notifier.send_notification(notification, channels=["slack"])

    async def _send_overdue_reminder(self, assignee: str, todos: List[TodoItem]):
        """Send overdue reminder to specific user."""
        body = f"⚠️ *Overdue Items for {assignee}*\n\n"

        for todo in todos[:5]:
            days_overdue = (datetime.now() - todo.due_date).days
            body += f"• {todo.title} ({days_overdue} days overdue)\n"

        if len(todos) > 5:
            body += f"• ... and {len(todos) - 5} more overdue items\n"

        body += f"\n💡 Use the TODO dashboard to update or complete these items."

        notification = NotificationContent(
            title="Overdue TODO Reminder", body=body, priority="high"
        )
        await self.notifier.send_notification(notification, channels=["slack"])

    def __del__(self):
        """Close database session."""
        if hasattr(self, "session"):
            self.session.close()


# Add import for asyncio at the top of the file
import asyncio
