#!/usr/bin/env python3
"""Main PM Agent orchestrator."""

import asyncio
import logging
import argparse
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import schedule
import time

from sqlalchemy import create_engine, Column, String, DateTime, Boolean, JSON, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from config.settings import settings
from src.integrations.fireflies import FirefliesClient, MeetingTranscript
from src.integrations.jira_mcp import JiraMCPClient, JiraTicket
from src.processors.transcript_analyzer import TranscriptAnalyzer, ActionItem
from src.managers.notifications import NotificationManager, NotificationContent
from src.models.learning import Learning


# Setup logging
logging.basicConfig(
    level=getattr(logging, settings.agent.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database setup
Base = declarative_base()


class ProcessedMeeting(Base):
    """Database model for tracking processed meetings."""
    __tablename__ = 'processed_meetings'

    meeting_id = Column(String, primary_key=True)
    title = Column(String)
    date = Column(DateTime)
    processed_at = Column(DateTime, default=datetime.utcnow)
    analyzed_at = Column(DateTime)
    summary = Column(String)
    key_decisions = Column(JSON)
    blockers = Column(JSON)
    action_items = Column(JSON)
    tickets_created = Column(JSON)
    todos_created = Column(JSON)
    success = Column(Boolean, default=True)


class TodoItem(Base):
    """Database model for tracking TODOs."""
    __tablename__ = 'todo_items'

    id = Column(String, primary_key=True)
    title = Column(String)
    description = Column(String)
    assignee = Column(String)
    due_date = Column(DateTime)
    status = Column(String, default='pending')
    ticket_key = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    source_meeting_id = Column(String)
    priority = Column(String, default='Medium')
    project_key = Column(String)


class UserPreference(Base):
    """Database model for user project preferences."""
    __tablename__ = 'user_preferences'

    id = Column(String, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    slack_username = Column(String)
    notification_cadence = Column(String, default='daily')  # daily, weekly, monthly
    selected_projects = Column(JSON)  # List of Jira project keys
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    last_notification_sent = Column(DateTime)


class ProjectChange(Base):
    """Database model for tracking Jira project changes."""
    __tablename__ = 'project_changes'

    id = Column(String, primary_key=True)
    project_key = Column(String, nullable=False)
    change_type = Column(String, nullable=False)  # created, updated, status_changed, assignee_changed, time_logged
    ticket_key = Column(String, nullable=False)
    ticket_title = Column(String)
    old_value = Column(String)
    new_value = Column(String)
    assignee = Column(String)
    reporter = Column(String)
    priority = Column(String)
    status = Column(String)
    change_timestamp = Column(DateTime, nullable=False)
    detected_at = Column(DateTime, default=datetime.utcnow)
    change_details = Column(JSON)  # Additional metadata about the change


class MeetingProjectConnection(Base):
    """Database model for storing meeting-project relevance connections."""
    __tablename__ = 'meeting_project_connections'

    id = Column(String, primary_key=True)
    meeting_id = Column(String, nullable=False)
    meeting_title = Column(String)
    meeting_date = Column(DateTime)
    project_key = Column(String, nullable=False)
    project_name = Column(String)
    relevance_score = Column(String)  # Store as string to handle float values
    confidence = Column(String)
    matching_factors = Column(JSON)  # List of factors that led to the connection
    created_at = Column(DateTime, default=datetime.utcnow)
    last_confirmed_at = Column(DateTime)  # When this connection was last verified
    is_verified = Column(Boolean, default=False)  # Whether this connection has been manually verified


class PMAgent:
    """Main PM Agent orchestrator."""

    def __init__(self):
        """Initialize the PM Agent."""
        self.fireflies_client = FirefliesClient(settings.fireflies.api_key)
        self.jira_client = JiraMCPClient(
            jira_url=settings.jira.url,
            username=settings.jira.username,
            api_token=settings.jira.api_token
        )
        self.analyzer = TranscriptAnalyzer()
        self.notifier = NotificationManager(settings.notifications)

        # Database setup
        engine = create_engine(settings.agent.database_url)
        Base.metadata.create_all(engine)

        # Run database migrations
        self._run_migrations(engine)

        Session = sessionmaker(bind=engine)
        self.db_session = Session()

    def _run_migrations(self, engine):
        """Run database migrations to handle schema changes."""
        try:
            with engine.connect() as conn:
                # Check if we need to migrate slack_user_id to slack_username
                try:
                    # Try to query the old column
                    conn.execute(text("SELECT slack_user_id FROM user_preferences LIMIT 1"))

                    # If we get here, the old column exists, so we need to migrate
                    logger.info("Migrating slack_user_id to slack_username...")

                    # Add new column
                    try:
                        conn.execute(text("ALTER TABLE user_preferences ADD COLUMN slack_username TEXT"))
                        conn.commit()
                    except Exception:
                        # Column might already exist
                        pass

                    # Copy data from old column to new column
                    conn.execute(text("UPDATE user_preferences SET slack_username = slack_user_id WHERE slack_user_id IS NOT NULL"))
                    conn.commit()

                    # Drop old column (SQLite doesn't support DROP COLUMN directly, so we'll leave it)
                    logger.info("Migration completed successfully")

                except Exception:
                    # Old column doesn't exist, so no migration needed
                    pass

        except Exception as e:
            logger.warning(f"Migration failed or not needed: {e}")

    async def process_meetings(self):
        """Process new meetings from Fireflies."""
        logger.info("Starting meeting processing...")

        try:
            # Get last processed meeting ID
            last_processed = self.db_session.query(ProcessedMeeting).order_by(
                ProcessedMeeting.processed_at.desc()
            ).first()
            last_meeting_id = last_processed.meeting_id if last_processed else None

            # Fetch new meetings
            meetings = self.fireflies_client.get_unprocessed_meetings(last_meeting_id)
            logger.info(f"Found {len(meetings)} new meetings to process")

            for meeting_data in meetings:
                await self._process_single_meeting(meeting_data)

        except Exception as e:
            logger.error(f"Error processing meetings: {e}")
            await self.notifier.send_urgent_notification(
                "Meeting Processing Failed",
                f"Failed to process meetings: {str(e)}"
            )

    async def _process_single_meeting(self, meeting_data: Dict[str, Any]):
        """Process a single meeting."""
        meeting_id = meeting_data.get("id")
        meeting_title = meeting_data.get("title", "Untitled Meeting")

        try:
            logger.info(f"Processing meeting: {meeting_title}")

            # Get full transcript
            transcript = self.fireflies_client.get_meeting_transcript(meeting_id)
            if not transcript:
                logger.warning(f"Could not fetch transcript for meeting {meeting_id}")
                return

            # Analyze transcript
            analysis = self.analyzer.analyze_transcript(
                transcript.transcript,
                meeting_title,
                transcript.date
            )

            # Create Jira tickets from action items
            tickets_created = await self._create_tickets_from_action_items(
                analysis.action_items,
                meeting_title
            )

            # Store TODOs in database
            for item in analysis.action_items:
                todo = TodoItem(
                    id=f"{meeting_id}_{hash(item.title)}",
                    title=item.title,
                    description=item.description,
                    assignee=item.assignee,
                    due_date=datetime.fromisoformat(item.due_date) if item.due_date else None,
                    source_meeting_id=meeting_id,
                    ticket_key=tickets_created.get(item.title),
                    project_key=settings.jira.default_project  # Use the default project from settings
                )
                self.db_session.add(todo)

            # Record processed meeting
            processed = ProcessedMeeting(
                meeting_id=meeting_id,
                title=meeting_title,
                date=transcript.date,
                action_items=[item.dict() for item in analysis.action_items],
                tickets_created=tickets_created
            )
            self.db_session.add(processed)
            self.db_session.commit()

            # Send notification
            await self.notifier.send_meeting_processed_notification(
                meeting_title,
                len(analysis.action_items),
                list(tickets_created.values())
            )

            logger.info(f"Successfully processed meeting: {meeting_title}")

        except Exception as e:
            logger.error(f"Error processing meeting {meeting_id}: {e}")
            # Record failed processing
            processed = ProcessedMeeting(
                meeting_id=meeting_id,
                title=meeting_title,
                date=datetime.now(),
                success=False
            )
            self.db_session.add(processed)
            self.db_session.commit()

    async def _create_tickets_from_action_items(self, action_items: List[ActionItem],
                                               meeting_title: str) -> Dict[str, str]:
        """Create Jira tickets from action items."""
        tickets_created = {}

        async with self.jira_client as client:
            for item in action_items:
                try:
                    # Prepare ticket
                    ticket = JiraTicket(
                        summary=item.title,
                        description=f"From meeting: {meeting_title}\n\n{item.description}\n\nContext: {item.context}",
                        issue_type="Task",
                        priority=item.priority,
                        project_key=settings.jira.default_project,
                        assignee=item.assignee,
                        due_date=item.due_date,
                        labels=["pm-agent", "auto-created"]
                    )

                    # Create ticket
                    result = await client.create_ticket(ticket)
                    if result.get("success"):
                        ticket_key = result.get("key")
                        tickets_created[item.title] = ticket_key
                        logger.info(f"Created ticket {ticket_key} for: {item.title}")
                    else:
                        logger.error(f"Failed to create ticket for: {item.title}")

                except Exception as e:
                    logger.error(f"Error creating ticket for {item.title}: {e}")

        return tickets_created

    async def send_daily_digest(self):
        """Send daily digest of TODOs and overdue items."""
        logger.info("Preparing daily digest...")

        try:
            # Get overdue TODOs
            overdue = self.db_session.query(TodoItem).filter(
                TodoItem.due_date < datetime.now(),
                TodoItem.status != 'completed'
            ).all()

            # Get TODOs due today
            today_start = datetime.now().replace(hour=0, minute=0, second=0)
            today_end = today_start + timedelta(days=1)
            due_today = self.db_session.query(TodoItem).filter(
                TodoItem.due_date >= today_start,
                TodoItem.due_date < today_end,
                TodoItem.status != 'completed'
            ).all()

            # Get all pending TODOs
            all_todos = self.db_session.query(TodoItem).filter(
                TodoItem.status == 'pending'
            ).limit(20).all()

            # Check Jira for overdue tickets
            async with self.jira_client as client:
                jira_overdue = await client.get_overdue_tickets(settings.jira.default_project)
                jira_due_soon = await client.get_tickets_due_soon(3, settings.jira.default_project)

            # Prepare digest data
            overdue_items = [{"title": t.title, "assignee": t.assignee} for t in overdue]
            overdue_items.extend([{"title": t.get("summary"), "assignee": t.get("assignee")} for t in jira_overdue])

            due_today_items = [{"title": t.title, "assignee": t.assignee} for t in due_today]
            due_today_items.extend([{"title": t.get("summary"), "assignee": t.get("assignee")} for t in jira_due_soon])

            todo_items = [{"title": t.title, "description": t.description[:100]} for t in all_todos]

            # Send digest
            await self.notifier.send_daily_digest(todo_items, overdue_items, due_today_items)

            logger.info("Daily digest sent successfully")

        except Exception as e:
            logger.error(f"Error sending daily digest: {e}")

    async def check_urgent_items(self):
        """Check for urgent items requiring immediate attention."""
        logger.info("Checking for urgent items...")

        try:
            # Check for items due within 2 hours
            urgent_deadline = datetime.now() + timedelta(hours=2)
            urgent_todos = self.db_session.query(TodoItem).filter(
                TodoItem.due_date <= urgent_deadline,
                TodoItem.due_date > datetime.now(),
                TodoItem.status != 'completed'
            ).all()

            for todo in urgent_todos:
                await self.notifier.send_urgent_notification(
                    "TODO Due Soon",
                    f"Task '{todo.title}' is due at {todo.due_date.strftime('%I:%M %p')}",
                    {"key": todo.ticket_key, "summary": todo.title, "assignee": todo.assignee}
                )

        except Exception as e:
            logger.error(f"Error checking urgent items: {e}")

    async def run_once(self):
        """Run the agent once (for testing or manual execution)."""
        await self.process_meetings()
        await self.send_daily_digest()
        await self.check_urgent_items()

    def run_scheduled(self):
        """Run the agent on a schedule."""
        # Schedule tasks
        schedule.every().day.at("08:00").do(
            lambda: asyncio.run(self.send_daily_digest())
        )
        schedule.every().day.at("17:00").do(
            lambda: asyncio.run(self.send_daily_digest())
        )
        schedule.every().hour.do(
            lambda: asyncio.run(self.process_meetings())
        )
        schedule.every(30).minutes.do(
            lambda: asyncio.run(self.check_urgent_items())
        )

        logger.info("PM Agent started - running on schedule")
        while True:
            schedule.run_pending()
            time.sleep(60)


async def test_connections():
    """Test all connections and integrations."""
    agent = PMAgent()

    print("Testing connections...")

    # Test Fireflies
    try:
        meetings = agent.fireflies_client.get_recent_meetings(days_back=1)
        print(f"✅ Fireflies: Connected, found {len(meetings)} recent meetings")
    except Exception as e:
        print(f"❌ Fireflies: Failed - {e}")

    # Test Jira MCP
    try:
        async with agent.jira_client as client:
            result = await client.search_tickets("project = PM", max_results=1)
            print(f"✅ Jira MCP: Connected")
    except Exception as e:
        print(f"❌ Jira MCP: Failed - {e}")

    # Test Notifications
    try:
        results = await agent.notifier.test_channels()
        for channel, success in results.items():
            status = "✅" if success else "❌"
            print(f"{status} {channel.capitalize()}: {'Connected' if success else 'Failed'}")
    except Exception as e:
        print(f"❌ Notifications: Failed - {e}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="PM Agent - Autonomous Project Management Assistant")
    parser.add_argument("--mode", choices=["development", "production", "test"], default="development",
                       help="Run mode")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--test", action="store_true", help="Test connections")

    args = parser.parse_args()

    if args.test:
        asyncio.run(test_connections())
        return

    agent = PMAgent()

    if args.once or args.mode == "development":
        logger.info("Running agent once...")
        asyncio.run(agent.run_once())
    else:
        agent.run_scheduled()


if __name__ == "__main__":
    main()