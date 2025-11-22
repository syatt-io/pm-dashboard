#!/usr/bin/env python3
"""Interactive PM Agent - Reviews and confirms before creating tickets."""

import asyncio
import logging
import argparse
from datetime import datetime
from typing import List, Dict, Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config.settings import settings
from src.integrations.fireflies import FirefliesClient
from src.integrations.jira_mcp import JiraMCPClient, JiraTicket
from src.processors.transcript_analyzer import TranscriptAnalyzer
from src.processors.interactive_processor import InteractiveProcessor, ReviewedItem
from src.managers.notifications import NotificationManager, NotificationContent
from src.models import ProcessedMeeting, TodoItem, Base


logging.basicConfig(
    level=getattr(logging, settings.agent.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class InteractivePMAgent:
    """Interactive PM Agent that asks for confirmation."""

    def __init__(self):
        """Initialize the Interactive PM Agent."""
        self.fireflies_client = FirefliesClient(settings.fireflies.api_key)
        self.jira_client = JiraMCPClient(
            jira_url=settings.jira.url,
            username=settings.jira.username,
            api_token=settings.jira.api_token,
        )
        self.analyzer = TranscriptAnalyzer()
        self.interactive = InteractiveProcessor()
        self.notifier = NotificationManager(settings.notifications)

        # Database setup
        engine = create_engine(settings.agent.database_url)
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        self.db_session = Session()

    async def process_meeting_interactive(self, meeting_id: str = None):
        """Process meetings with interactive review."""

        # Get meetings
        if meeting_id:
            # Process specific meeting
            meeting_data = {"id": meeting_id}
        else:
            # Get recent meetings and let user choose
            meetings = self.fireflies_client.get_recent_meetings(days_back=10)
            if not meetings:
                print("❌ No meetings found in Fireflies")
                return

            meeting_data = self._select_meeting(meetings)
            if not meeting_data:
                return

        # Process the selected meeting
        await self._process_meeting_with_review(meeting_data)

    def _select_meeting(self, meetings: List[Dict]) -> Dict:
        """Let user select a meeting to process."""
        print("\n📋 Available Meetings:\n")

        for i, meeting in enumerate(meetings[:10], 1):
            # Parse date
            date_val = meeting.get("date", 0)
            if isinstance(date_val, (int, float)) and date_val > 1000000000000:
                meeting_date = datetime.fromtimestamp(date_val / 1000)
                date_str = meeting_date.strftime("%Y-%m-%d %I:%M %p")
            else:
                date_str = str(date_val)

            title = meeting.get("title", "Untitled")
            duration = meeting.get("duration", 0)

            print(f"{i}. {title}")
            print(f"   Date: {date_str}")
            print(f"   Duration: {duration:.0f} minutes\n")

        choice = input("Select meeting number (or 'q' to quit): ")

        if choice.lower() == "q":
            return None

        try:
            index = int(choice) - 1
            if 0 <= index < len(meetings):
                return meetings[index]
        except ValueError:
            pass

        print("Invalid selection")
        return None

    async def _process_meeting_with_review(self, meeting_data: Dict):
        """Process a meeting with interactive review."""
        meeting_id = meeting_data.get("id")
        meeting_title = meeting_data.get("title", "Untitled Meeting")

        print(f"\n🔄 Processing: {meeting_title}")

        # Get full transcript
        transcript = self.fireflies_client.get_meeting_transcript(meeting_id)
        if not transcript:
            print("❌ Could not fetch transcript")
            return

        print(f"✅ Got transcript ({len(transcript.transcript)} characters)")

        # Analyze transcript
        print("🤖 Analyzing with AI...")
        analysis = self.analyzer.analyze_transcript(
            transcript.transcript, meeting_title, transcript.date
        )

        # Interactive review
        reviewed_items, should_proceed = self.interactive.review_meeting_analysis(
            meeting_title, analysis, settings.jira.default_project
        )

        if not should_proceed:
            print("\n❌ Cancelled by user")
            return

        # Process approved items
        results = await self._execute_reviewed_actions(
            reviewed_items, meeting_id, meeting_title, transcript.date
        )

        # Display results
        self.interactive.display_processing_results(results)

        # Send notification
        if results.get("jira_created") or results.get("todos_created"):
            await self._send_completion_notification(meeting_title, results)

    async def _execute_reviewed_actions(
        self,
        reviewed_items: List[ReviewedItem],
        meeting_id: str,
        meeting_title: str,
        meeting_date: datetime,
    ) -> Dict[str, Any]:
        """Execute the reviewed and approved actions."""
        results = {"jira_created": [], "todos_created": [], "errors": []}

        # Separate items by destination
        jira_items = [r for r in reviewed_items if r.destination == "jira"]
        todo_items = [r for r in reviewed_items if r.destination == "todo"]

        # Create Jira tickets
        if jira_items:
            async with self.jira_client as client:
                for reviewed in jira_items:
                    try:
                        item = reviewed.original

                        ticket = JiraTicket(
                            summary=reviewed.modified_title or item.title,
                            description=f"From meeting: {meeting_title}\n\n"
                            f"{item.description}\n\n"
                            f"Context: {item.context}",
                            issue_type=reviewed.jira_issue_type or "Task",
                            priority=reviewed.modified_priority or item.priority,
                            project_key=reviewed.jira_project,
                            assignee=reviewed.modified_assignee or item.assignee,
                            due_date=reviewed.modified_due_date or item.due_date,
                            labels=["pm-agent", "auto-created", "interactive"],
                        )

                        result = await client.create_ticket(ticket)
                        if result.get("success"):
                            ticket_key = result.get("key")
                            results["jira_created"].append(ticket_key)
                            logger.info(f"Created ticket {ticket_key}")
                        else:
                            error = f"Failed to create ticket for: {item.title}"
                            results["errors"].append(error)
                            logger.error(error)

                    except Exception as e:
                        error = f"Error creating ticket: {str(e)}"
                        results["errors"].append(error)
                        logger.error(error)

        # Create TODO items
        for reviewed in todo_items:
            try:
                item = reviewed.original

                todo = TodoItem(
                    id=f"{meeting_id}_{hash(item.title)}",
                    title=reviewed.modified_title or item.title,
                    description=item.description,
                    assignee=reviewed.modified_assignee or item.assignee,
                    due_date=(
                        datetime.fromisoformat(reviewed.modified_due_date)
                        if reviewed.modified_due_date
                        else (
                            datetime.fromisoformat(item.due_date)
                            if item.due_date
                            else None
                        )
                    ),
                    source_meeting_id=meeting_id,
                    status="pending",
                )

                self.db_session.add(todo)
                results["todos_created"].append(todo.title)
                logger.info(f"Created TODO: {todo.title}")

            except Exception as e:
                error = f"Error creating TODO: {str(e)}"
                results["errors"].append(error)
                logger.error(error)

        # Record processed meeting
        try:
            processed = ProcessedMeeting(
                meeting_id=meeting_id,
                title=meeting_title,
                date=meeting_date,
                action_items=[
                    {
                        "title": r.modified_title or r.original.title,
                        "destination": r.destination,
                    }
                    for r in reviewed_items
                ],
                tickets_created=results["jira_created"],
                success=len(results["errors"]) == 0,
            )
            self.db_session.add(processed)
            self.db_session.commit()
        except Exception as e:
            logger.error(f"Error recording processed meeting: {e}")

        return results

    async def _send_completion_notification(
        self, meeting_title: str, results: Dict[str, Any]
    ):
        """Send notification about completed processing."""
        body = f"Meeting *{meeting_title}* has been processed.\n\n"

        if results["jira_created"]:
            body += f"✅ Created {len(results['jira_created'])} Jira tickets\n"
            for ticket in results["jira_created"][:5]:
                body += f"  • {ticket}\n"

        if results["todos_created"]:
            body += f"\n✅ Added {len(results['todos_created'])} TODO items\n"
            for todo in results["todos_created"][:5]:
                body += f"  • {todo}\n"

        if results["errors"]:
            body += f"\n⚠️ {len(results['errors'])} errors occurred"

        notification = NotificationContent(
            title="Meeting Processed (Interactive)",
            body=body,
            priority="normal",
            footer=f"Processed at {datetime.now().strftime('%I:%M %p')}",
        )

        await self.notifier.send_notification(notification, channels=["slack"])


async def main():
    """Main entry point for interactive mode."""
    parser = argparse.ArgumentParser(description="Interactive PM Agent")
    parser.add_argument("--meeting-id", help="Process specific meeting by ID")
    parser.add_argument(
        "--days-back",
        type=int,
        default=10,
        help="Number of days to look back for meetings",
    )

    args = parser.parse_args()

    agent = InteractivePMAgent()

    try:
        await agent.process_meeting_interactive(args.meeting_id)
    except KeyboardInterrupt:
        print("\n\n❌ Cancelled by user")
    except Exception as e:
        logger.error(f"Error in interactive processing: {e}")
        print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
