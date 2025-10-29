"""
Meeting Analysis Sync Job

Scheduled job to automatically analyze meetings from active projects.
Runs nightly at 7 AM UTC (3 AM EST) with 3-day lookback window.
"""

import logging
import time
import json
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.integrations.fireflies import FirefliesClient
from src.processors.transcript_analyzer import TranscriptAnalyzer

logger = logging.getLogger(__name__)


class MeetingAnalysisSyncJob:
    """Scheduled job to analyze meetings from active projects"""

    def __init__(self):
        # Get database URL from environment
        self.database_url = os.getenv("DATABASE_URL")
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable is required")

        # Get system-level Fireflies API key
        self.fireflies_api_key = os.getenv("FIREFLIES_SYSTEM_API_KEY")
        if not self.fireflies_api_key:
            raise ValueError("FIREFLIES_SYSTEM_API_KEY environment variable is required")

        # Initialize clients
        self.fireflies_client = FirefliesClient(api_key=self.fireflies_api_key)
        self.analyzer = TranscriptAnalyzer()

        # Create database engine and session
        self.engine = create_engine(self.database_url)
        self.Session = sessionmaker(bind=self.engine)

    def get_active_projects(self) -> List[Dict[str, any]]:
        """Get list of active projects with their keywords from database"""
        session = self.Session()
        try:
            # Get active projects
            result = session.execute(
                text("SELECT key, name FROM projects WHERE is_active = true")
            )
            projects = [{"key": row[0], "name": row[1]} for row in result]

            # Get keywords for each project
            for project in projects:
                keyword_result = session.execute(
                    text("SELECT keyword FROM project_keywords WHERE project_key = :project_key"),
                    {"project_key": project["key"]}
                )
                project["keywords"] = [row[0].lower() for row in keyword_result]

            logger.info(f"Found {len(projects)} active projects")
            return projects
        finally:
            session.close()

    def get_unanalyzed_meetings(self, days_back: int = 3) -> List[Dict]:
        """
        Fetch meetings from Fireflies that haven't been analyzed yet.

        Args:
            days_back: Number of days to look back (default 3)

        Returns:
            List of unanalyzed meeting dictionaries
        """
        logger.info(f"Fetching meetings from last {days_back} days...")

        # Fetch recent meetings from Fireflies
        all_meetings = self.fireflies_client.get_recent_meetings(
            days_back=days_back,
            limit=100
        )

        logger.info(f"Found {len(all_meetings)} total meetings from Fireflies")

        # Get already processed meeting IDs from database
        session = self.Session()
        try:
            result = session.execute(
                text("SELECT fireflies_id FROM processed_meetings WHERE fireflies_id IS NOT NULL")
            )
            processed_ids = {row[0] for row in result}
            logger.info(f"Found {len(processed_ids)} already processed meetings in database")
        finally:
            session.close()

        # Filter to only unanalyzed meetings
        unanalyzed = [m for m in all_meetings if m.get("id") not in processed_ids]
        logger.info(f"Found {len(unanalyzed)} unanalyzed meetings")

        return unanalyzed

    def filter_meetings_by_projects(
        self,
        meetings: List[Dict],
        projects: List[Dict[str, any]]
    ) -> List[tuple]:
        """
        Filter meetings by project keywords.

        Args:
            meetings: List of meeting dictionaries
            projects: List of active projects with keywords

        Returns:
            List of tuples: (meeting, matched_project)
        """
        matched_meetings = []

        for meeting in meetings:
            title = meeting.get("title", "").lower()

            # Try to match against project keywords
            for project in projects:
                if not project.get("keywords"):
                    continue

                # Check if any keyword appears in meeting title
                for keyword in project["keywords"]:
                    if keyword in title:
                        matched_meetings.append((meeting, project))
                        logger.info(
                            f"Matched meeting '{meeting.get('title')}' to project {project['key']} "
                            f"via keyword '{keyword}'"
                        )
                        break  # Only match to first project found
                else:
                    continue
                break  # Break outer loop if match found

        logger.info(f"Matched {len(matched_meetings)} meetings to active projects")
        return matched_meetings

    def analyze_meeting(self, meeting: Dict, project: Dict) -> bool:
        """
        Analyze a single meeting and store results in database.

        Args:
            meeting: Meeting dictionary from Fireflies
            project: Matched project dictionary

        Returns:
            True if successful, False otherwise
        """
        meeting_id = meeting.get("id")
        meeting_title = meeting.get("title", "Untitled Meeting")

        try:
            logger.info(f"Analyzing meeting: {meeting_title} (ID: {meeting_id})")

            # Fetch full transcript
            transcript_data = self.fireflies_client.get_meeting_transcript(meeting_id)
            if not transcript_data:
                logger.error(f"Failed to fetch transcript for meeting {meeting_id}")
                return False

            transcript_text = transcript_data.get("transcript", "")
            if not transcript_text or len(transcript_text) < 100:
                logger.warning(f"Transcript too short or empty for meeting {meeting_id}, skipping")
                return False

            # Convert date from milliseconds to datetime
            date_ms = meeting.get("date")
            if isinstance(date_ms, (int, float)) and date_ms > 1000000000000:
                meeting_date = datetime.fromtimestamp(date_ms / 1000)
            else:
                meeting_date = datetime.now()

            # Run AI analysis
            analysis = self.analyzer.analyze_transcript(
                transcript=transcript_text,
                meeting_title=meeting_title,
                meeting_date=meeting_date
            )

            # Prepare action items for storage
            action_items_data = []
            for item in analysis.action_items:
                action_items_data.append({
                    "title": item.title,
                    "description": item.description,
                    "assignee": item.assignee,
                    "due_date": item.due_date,
                    "priority": item.priority,
                    "context": item.context,
                    "dependencies": item.dependencies or []
                })

            # Store in database
            session = self.Session()
            try:
                # Create new processed meeting record
                meeting_uuid = str(uuid.uuid4())
                now = datetime.now(timezone.utc)

                session.execute(
                    text("""
                        INSERT INTO processed_meetings (
                            id, fireflies_id, title, date, duration,
                            executive_summary, outcomes, action_items,
                            blockers_and_constraints, timeline_and_milestones,
                            key_discussions, analyzed_at, created_at, updated_at
                        ) VALUES (
                            :id, :fireflies_id, :title, :date, :duration,
                            :executive_summary, :outcomes, :action_items,
                            :blockers_and_constraints, :timeline_and_milestones,
                            :key_discussions, :analyzed_at, :created_at, :updated_at
                        )
                    """),
                    {
                        "id": meeting_uuid,
                        "fireflies_id": meeting_id,
                        "title": meeting_title,
                        "date": meeting_date,
                        "duration": meeting.get("duration", 0),
                        "executive_summary": analysis.executive_summary,
                        "outcomes": json.dumps(analysis.outcomes or []),
                        "action_items": json.dumps(action_items_data),
                        "blockers_and_constraints": json.dumps(analysis.blockers_and_constraints or []),
                        "timeline_and_milestones": json.dumps(analysis.timeline_and_milestones or []),
                        "key_discussions": json.dumps(analysis.key_discussions or []),
                        "analyzed_at": now,
                        "created_at": now,
                        "updated_at": now
                    }
                )

                session.commit()

                logger.info(
                    f"Successfully analyzed meeting {meeting_id}: "
                    f"{len(analysis.action_items)} action items, "
                    f"{len(analysis.outcomes)} outcomes, "
                    f"{len(analysis.blockers_and_constraints)} blockers"
                )
                return True

            except Exception as e:
                session.rollback()
                logger.error(f"Database error storing meeting {meeting_id}: {e}")
                return False
            finally:
                session.close()

        except Exception as e:
            logger.error(f"Error analyzing meeting {meeting_id}: {e}", exc_info=True)
            return False

    def send_slack_notification(self, stats: Dict):
        """Send Slack notification with job stats"""
        try:
            from slack_sdk import WebClient

            slack_token = os.getenv("SLACK_BOT_TOKEN")
            slack_channel = os.getenv("SLACK_CHANNEL")

            if not slack_token or not slack_channel:
                logger.info("Slack not configured, skipping notification")
                return

            client = WebClient(token=slack_token)

            # Build message
            if stats.get("success"):
                emoji = "✅"
                color = "good"
                title = "Meeting Analysis Sync Completed"
            else:
                emoji = "❌"
                color = "danger"
                title = "Meeting Analysis Sync Failed"

            message_blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"{emoji} {title}"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Active Projects:* {stats.get('active_projects', 0)}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Meetings Analyzed:* {stats.get('meetings_analyzed', 0)}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Errors:* {stats.get('errors', 0)}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Duration:* {stats.get('duration_seconds', 0):.1f}s"
                        }
                    ]
                }
            ]

            if stats.get("error"):
                message_blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Error:* {stats['error']}"
                    }
                })

            # Send to Slack
            client.chat_postMessage(
                channel=slack_channel,
                blocks=message_blocks,
                text=title  # Fallback text
            )

            logger.info(f"Sent Slack notification to {slack_channel}")

        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")

    def run(self) -> Dict:
        """
        Execute the meeting analysis sync job.

        Returns:
            Dict with job execution statistics
        """
        start_time = datetime.now()
        logger.info(f"Starting meeting analysis sync job at {start_time}")

        stats = {
            "success": False,
            "start_time": start_time.isoformat(),
            "active_projects": 0,
            "meetings_analyzed": 0,
            "errors": 0,
            "meetings_matched": 0,
            "meetings_total": 0
        }

        try:
            # Get active projects
            logger.info("Fetching active projects...")
            active_projects = self.get_active_projects()
            stats["active_projects"] = len(active_projects)

            if not active_projects:
                logger.warning("No active projects found, exiting")
                stats["success"] = True
                return stats

            # Get unanalyzed meetings
            unanalyzed_meetings = self.get_unanalyzed_meetings(days_back=3)
            stats["meetings_total"] = len(unanalyzed_meetings)

            if not unanalyzed_meetings:
                logger.info("No unanalyzed meetings found")
                stats["success"] = True
                return stats

            # Filter by project keywords
            matched_meetings = self.filter_meetings_by_projects(
                unanalyzed_meetings,
                active_projects
            )
            stats["meetings_matched"] = len(matched_meetings)

            if not matched_meetings:
                logger.info("No meetings matched to active projects")
                stats["success"] = True
                return stats

            # Analyze each matched meeting
            logger.info(f"Analyzing {len(matched_meetings)} matched meetings...")

            for meeting, project in matched_meetings:
                try:
                    success = self.analyze_meeting(meeting, project)
                    if success:
                        stats["meetings_analyzed"] += 1
                    else:
                        stats["errors"] += 1

                    # Rate limiting: sleep between analyses
                    time.sleep(2)

                except Exception as e:
                    logger.error(f"Error processing meeting {meeting.get('id')}: {e}")
                    stats["errors"] += 1

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            stats["success"] = True
            stats["end_time"] = end_time.isoformat()
            stats["duration_seconds"] = duration

            logger.info(f"Meeting analysis sync completed successfully in {duration:.2f}s")
            logger.info(f"Stats: {stats}")

            # Send Slack notification
            self.send_slack_notification(stats)

            return stats

        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            logger.error(f"Meeting analysis sync failed after {duration:.2f}s: {e}", exc_info=True)

            stats["success"] = False
            stats["end_time"] = end_time.isoformat()
            stats["duration_seconds"] = duration
            stats["error"] = str(e)

            # Send failure notification
            self.send_slack_notification(stats)

            return stats


def run_meeting_analysis_sync():
    """
    Entry point for the meeting analysis sync job.
    This function is called by the scheduler.
    """
    try:
        job = MeetingAnalysisSyncJob()
        return job.run()
    except Exception as e:
        logger.error(f"Failed to initialize or run meeting analysis sync job: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "start_time": datetime.now().isoformat(),
            "end_time": datetime.now().isoformat(),
            "duration_seconds": 0
        }


if __name__ == "__main__":
    # Allow running job manually for testing
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("Running meeting analysis sync job manually...")
    stats = run_meeting_analysis_sync()
    print(f"\nJob completed: {json.dumps(stats, indent=2)}")
