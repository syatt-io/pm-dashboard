"""Project Activity Aggregator for generating client meeting agendas."""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import json

from config.settings import settings
from src.integrations.fireflies import FirefliesClient
from src.integrations.jira_mcp import JiraMCPClient
from src.processors.transcript_analyzer import TranscriptAnalyzer
from src.managers.slack_bot import SlackTodoBot
from src.utils.prompt_manager import get_prompt_manager

# MCP Tempo function should be available globally in Claude Code environment
# If not available, define a fallback
if "mcp__Jira_Tempo__retrieveWorklogs" not in globals():

    def mcp__Jira_Tempo__retrieveWorklogs(startDate: str, endDate: str):
        """Fallback function when MCP Tempo is not available."""
        return "No worklogs found for the specified date range."


logger = logging.getLogger(__name__)


@dataclass
class ProjectActivity:
    """Container for aggregated project activity data."""

    project_key: str
    project_name: str
    start_date: str
    end_date: str

    # Meeting data
    meetings: List[Dict[str, Any]]
    meeting_summaries: List[str]

    # Jira ticket activity
    ticket_activity: List[Dict[str, Any]]
    completed_tickets: List[Dict[str, Any]]
    new_tickets: List[Dict[str, Any]]
    jira_ticket_changes: List[Dict[str, Any]]

    # Slack activity (if available)
    slack_messages: List[Dict[str, Any]]
    key_discussions: List[str]

    # Time tracking
    time_entries: List[Dict[str, Any]]
    total_hours: float

    # GitHub activity
    github_prs_merged: List[Dict[str, Any]]
    github_prs_in_review: List[Dict[str, Any]]
    github_prs_open: List[Dict[str, Any]]

    # AI-generated insights (legacy format)
    progress_summary: Optional[str] = None
    key_achievements: Optional[List[str]] = None
    blockers_risks: Optional[List[str]] = None
    next_steps: Optional[List[str]] = None

    # Legacy digest format (4 sections - kept for backward compatibility)
    noteworthy_discussions: Optional[str] = None
    work_completed: Optional[str] = None
    topics_for_discussion: Optional[str] = None
    attention_required: Optional[str] = None

    # New Weekly Recap format (7 sections)
    executive_summary: Optional[str] = None
    followup_on_meeting: Optional[str] = None
    achievements: Optional[str] = None
    active_work: Optional[str] = None
    blockers_and_asks: Optional[str] = None
    proposed_agenda: Optional[str] = None
    progress_notes: Optional[str] = None

    # V2 Strategic Synthesis format (4 sections)
    project_pulse: Optional[str] = None
    story_of_the_week: Optional[str] = None
    looking_ahead_agenda: Optional[str] = None
    internal_pm_notes: Optional[str] = None

    # Historical context from Pinecone (optional)
    historical_context: Optional[List[Dict[str, Any]]] = None

    # Raw meeting insights
    meeting_action_items: Optional[List[Dict[str, Any]]] = None
    meeting_blockers: Optional[List[str]] = None

    # Follow-up on last meeting topics
    last_meeting_followup: Optional[Dict[str, Any]] = None

    # Attendee context for meeting prep (optional, enabled via ENABLE_ATTENDEE_CONTEXT env var)
    attendee_context: Optional[List[Dict[str, Any]]] = None


class ProjectActivityAggregator:
    """Aggregates project activity from multiple sources for agenda generation."""

    def __init__(self, custom_prompt_config: dict = None):
        """
        Initialize the aggregator with required clients.

        Args:
            custom_prompt_config: Optional dict with custom prompt configuration.
                                 If provided, will be used instead of default ai_prompts.yaml
        """
        from sqlalchemy import create_engine, text
        from sqlalchemy.orm import sessionmaker

        # Store text function for later use
        self.text = text

        self.fireflies_client = FirefliesClient(
            api_key=settings.fireflies.api_key, base_url=settings.fireflies.base_url
        )

        self.jira_client = JiraMCPClient(
            jira_url=settings.jira.url,
            username=settings.jira.username,
            api_token=settings.jira.api_token,
        )

        # Initialize TranscriptAnalyzer with properly configured LLM based on provider
        if settings.ai.provider == "openai":
            from langchain_openai import ChatOpenAI

            llm = ChatOpenAI(
                model=settings.ai.model,
                temperature=settings.ai.temperature,
                max_tokens=settings.ai.max_tokens,
                api_key=settings.ai.api_key,
            )
        elif settings.ai.provider == "anthropic":
            from langchain_anthropic import ChatAnthropic

            llm = ChatAnthropic(
                model=settings.ai.model,
                temperature=settings.ai.temperature,
                max_tokens=settings.ai.max_tokens,
                api_key=settings.ai.api_key,
            )
        elif settings.ai.provider == "google":
            from langchain_google_genai import ChatGoogleGenerativeAI

            llm = ChatGoogleGenerativeAI(
                model=settings.ai.model,
                temperature=settings.ai.temperature,
                max_tokens=settings.ai.max_tokens,
                google_api_key=settings.ai.api_key,
            )
        else:
            raise ValueError(f"Unsupported AI provider: {settings.ai.provider}")

        self.analyzer = TranscriptAnalyzer(llm=llm)

        # Initialize Slack bot
        try:
            # Initialize Slack bot with credentials from settings
            if (
                settings.notifications.slack_bot_token
                and settings.notifications.slack_signing_secret
            ):
                self.slack_bot = SlackTodoBot(
                    bot_token=settings.notifications.slack_bot_token,
                    signing_secret=settings.notifications.slack_signing_secret,
                )
            else:
                logger.warning(
                    "Slack credentials not configured, Slack integration disabled"
                )
                self.slack_bot = None
        except Exception as e:
            logger.warning(f"Could not initialize Slack bot: {e}")
            self.slack_bot = None

        # Setup database session for accessing stored meetings
        from src.utils.database import get_engine
        from sqlalchemy.orm import sessionmaker

        engine = get_engine()
        Session = sessionmaker(bind=engine)
        self.session = Session()

        # Initialize prompt manager with custom config if provided
        if custom_prompt_config:
            # Create temporary PromptManager with custom config
            import tempfile
            import yaml

            # Write custom config to temp file
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".yaml", delete=False
            ) as f:
                yaml.dump(custom_prompt_config, f)
                temp_config_path = f.name

            from src.utils.prompt_manager import PromptManager

            self.prompt_manager = PromptManager(config_path=temp_config_path)
            logger.info(
                f"Initialized PromptManager with custom config from temp file: {temp_config_path}"
            )
        else:
            self.prompt_manager = get_prompt_manager()

    async def aggregate_project_activity(
        self,
        project_key: str,
        project_name: str,
        days_back: int = 7,
        include_context: bool = False,
    ) -> ProjectActivity:
        """
        Aggregate activity for a specific project over the specified time period.

        Args:
            project_key: Jira project key (e.g., 'PROJ')
            project_name: Human-readable project name
            days_back: Number of days to look back (default: 7)
            include_context: Whether to include historical context from Pinecone (default: False)

        Returns:
            ProjectActivity containing all aggregated data
        """
        logger.info(
            f"Aggregating activity for project {project_key} ({days_back} days)"
        )

        end_date = datetime.now()
        # Set start_date to beginning of the day N days ago to include full days
        start_date = (end_date - timedelta(days=days_back)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        # Initialize activity container
        activity = ProjectActivity(
            project_key=project_key,
            project_name=project_name,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            meetings=[],
            meeting_summaries=[],
            ticket_activity=[],
            completed_tickets=[],
            new_tickets=[],
            jira_ticket_changes=[],
            slack_messages=[],
            key_discussions=[],
            time_entries=[],
            total_hours=0.0,
            github_prs_merged=[],
            github_prs_in_review=[],
            github_prs_open=[],
        )

        try:
            # Collect data from all sources
            await self._collect_meeting_data(activity, start_date, end_date)
            await self._collect_jira_activity(activity, start_date, end_date)
            await self._collect_slack_messages(activity, start_date, end_date)
            await self._collect_time_tracking_data(activity, start_date, end_date)
            await self._collect_github_activity(activity, days_back)

            # Match meeting topics to activity for follow-up section
            await self._match_topics_to_activity(activity)

            # Collect historical context from Pinecone if requested
            if include_context:
                await self._collect_historical_context(activity, days_back)

            # Generate AI insights
            await self._generate_insights(activity, include_context=include_context)

            # Collect attendee context if requested by user (via checkbox)
            if include_context:
                await self._collect_attendee_context(activity, days_back)

            logger.info(f"Successfully aggregated activity for {project_key}")
            return activity

        except Exception as e:
            logger.error(f"Error aggregating project activity: {e}")
            raise

    async def _collect_meeting_data(
        self, activity: ProjectActivity, start_date: datetime, end_date: datetime
    ):
        """Collect and analyze meeting data for the project."""
        logger.info(f"Starting meeting data collection for {activity.project_key}")
        try:
            # Import the database models
            from src.models import ProcessedMeeting

            # Get meetings that are relevant to this project from the database
            logger.info(
                f"Searching meetings for {activity.project_key} between {start_date} and {end_date}"
            )

            # Query processed_meetings directly by matching keywords in title/summary
            from src.utils.database import get_engine
            from sqlalchemy import text

            # Get project keywords for matching
            keywords_result = None
            try:
                engine = get_engine()
                with engine.connect() as conn:
                    keywords_result = conn.execute(
                        text(
                            """
                        SELECT keyword FROM project_keywords
                        WHERE project_key = :project_key
                    """
                        ),
                        {"project_key": activity.project_key},
                    )
                    keywords = [row[0].lower() for row in keywords_result]
            except Exception as e:
                logger.warning(
                    f"Error loading keywords for {activity.project_key}: {e}"
                )
                keywords = [activity.project_key.lower()]

            logger.info(f"Using keywords for {activity.project_key}: {keywords}")

            # Get all analyzed meetings in date range
            all_analyzed_meetings = (
                self.session.query(ProcessedMeeting)
                .filter(
                    ProcessedMeeting.date >= start_date,
                    ProcessedMeeting.date <= end_date,
                    ProcessedMeeting.analyzed_at.is_not(None),
                )
                .all()
            )

            logger.info(
                f"Found {len(all_analyzed_meetings)} total analyzed meetings in date range"
            )

            # Filter by keyword matching in title or summary
            relevant_meetings = []
            for db_meeting in all_analyzed_meetings:
                title_lower = (db_meeting.title or "").lower()
                summary_lower = (db_meeting.summary or "").lower()

                # Check if any keyword matches title or summary
                if any(
                    keyword in title_lower or keyword in summary_lower
                    for keyword in keywords
                ):
                    # Parse topics from JSON if available
                    topics_data = []
                    if db_meeting.topics:
                        try:
                            import json

                            topics_data = json.loads(db_meeting.topics)
                        except (json.JSONDecodeError, TypeError) as e:
                            logger.warning(
                                f"Failed to parse topics for meeting {db_meeting.id}: {e}"
                            )

                    # Parse action items from JSON if available
                    action_items_data = []
                    if db_meeting.action_items:
                        try:
                            import json

                            action_items_data = json.loads(db_meeting.action_items)
                        except (json.JSONDecodeError, TypeError) as e:
                            logger.warning(
                                f"Failed to parse action items for meeting {db_meeting.id}: {e}"
                            )

                    meeting_data = {
                        "id": db_meeting.fireflies_id or db_meeting.id,
                        "title": db_meeting.title,
                        "date": db_meeting.date.isoformat() if db_meeting.date else "",
                        "topics": topics_data,  # Primary data source (new structure)
                        "action_items": action_items_data,  # Primary data source (new structure)
                        "processed_at": (
                            db_meeting.processed_at.isoformat()
                            if db_meeting.processed_at
                            else ""
                        ),
                        "analyzed_at": (
                            db_meeting.analyzed_at.isoformat()
                            if db_meeting.analyzed_at
                            else ""
                        ),
                    }
                    relevant_meetings.append(meeting_data)
                    logger.info(
                        f"Matched meeting: {db_meeting.title} with {len(topics_data)} topics and {len(action_items_data)} action items"
                    )

            logger.info(
                f"Keyword matching found {len(relevant_meetings)} relevant meetings for {activity.project_key}"
            )

            # ALSO check for live Fireflies meetings that match this project
            try:
                from src.integrations.fireflies import FirefliesClient
                from src.utils.project_matcher import (
                    get_project_search_keywords,
                    check_project_match,
                )
                import os

                fireflies_client = FirefliesClient(os.getenv("FIREFLIES_API_KEY"))

                # Calculate days back from start_date to now
                days_back = (datetime.now() - start_date).days + 1

                # Get live meetings from Fireflies
                meetings = fireflies_client.get_recent_meetings(days_back=days_back)

                # Check each meeting against this project
                keywords = get_project_search_keywords(activity.project_key)
                for meeting in meetings:
                    if check_project_match(meeting, [activity.project_key]):
                        # Check if meeting date is in our range
                        if hasattr(meeting, "date") and meeting.date:
                            meeting_date = meeting.date
                            if isinstance(meeting_date, str):
                                try:
                                    meeting_date = datetime.fromisoformat(
                                        meeting_date.replace("Z", "+00:00")
                                    ).replace(tzinfo=None)
                                except (ValueError, AttributeError):
                                    continue

                            if start_date <= meeting_date <= end_date:
                                # Check if this meeting is already in our database results
                                already_included = any(
                                    db_meeting["id"] == meeting.id
                                    for db_meeting in relevant_meetings
                                )
                                if not already_included:
                                    meeting_data = {
                                        "id": meeting.id,
                                        "title": meeting.title or "Untitled Meeting",
                                        "date": (
                                            meeting_date.isoformat()
                                            if meeting_date
                                            else ""
                                        ),
                                        "summary": getattr(meeting, "summary", "")
                                        or "Live meeting - summary pending analysis",
                                        "processed_at": datetime.now().isoformat(),
                                        "analyzed_at": None,  # Live meeting not yet analyzed
                                    }
                                    relevant_meetings.append(meeting_data)

                logger.info(
                    f"Added {len([m for m in relevant_meetings if not m['analyzed_at']])} live Fireflies meetings to digest"
                )

            except Exception as fireflies_error:
                logger.debug(
                    f"Could not fetch live Fireflies meetings: {fireflies_error}"
                )

            activity.meetings = relevant_meetings
            logger.info(
                f"Found {len(relevant_meetings)} relevant meetings for {activity.project_key}"
            )

        except Exception as e:
            logger.error(f"Error collecting meeting data: {e}")

    async def _collect_jira_activity(
        self, activity: ProjectActivity, start_date: datetime, end_date: datetime
    ):
        """Collect Jira ticket activity for the project."""
        try:
            # Search for tickets updated in the time period
            days_back = (datetime.now() - start_date).days
            search_jql = f"project = {activity.project_key} AND updated >= -{days_back}d ORDER BY updated DESC"

            try:
                # Use the existing JiraMCPClient
                tickets = await self.jira_client.search_tickets(
                    jql=search_jql, max_results=50
                )

                for ticket in tickets:
                    # Parse dates from ticket fields
                    fields = ticket.get("fields", {})
                    created_str = fields.get("created", "")
                    updated_str = fields.get("updated", "")

                    if created_str:
                        created_date = datetime.fromisoformat(
                            created_str.replace("Z", "+00:00")
                        )
                        # Make timezone-naive for comparison
                        created_date = created_date.replace(tzinfo=None)
                    else:
                        created_date = start_date

                    if updated_str:
                        updated_date = datetime.fromisoformat(
                            updated_str.replace("Z", "+00:00")
                        )
                        # Make timezone-naive for comparison
                        updated_date = updated_date.replace(tzinfo=None)
                    else:
                        updated_date = start_date

                    # Process changelog to find recent changes
                    recent_changes = []
                    changelog = ticket.get("changelog", {})
                    if changelog and changelog.get("histories"):
                        for history in changelog.get("histories", []):
                            change_date_str = history.get("created", "")
                            if change_date_str:
                                change_date = datetime.fromisoformat(
                                    change_date_str.replace("Z", "+00:00")
                                )
                                change_date = change_date.replace(tzinfo=None)

                                # Only include changes in our date range
                                if start_date <= change_date <= end_date:
                                    for item in history.get("items", []):
                                        change_info = {
                                            "field": item.get("field", ""),
                                            "fieldtype": item.get("fieldtype", ""),
                                            "from_value": item.get("fromString", ""),
                                            "to_value": item.get("toString", ""),
                                            "changed_by": history.get("author", {}).get(
                                                "displayName", "Unknown"
                                            ),
                                            "changed_at": change_date.isoformat(),
                                        }
                                        recent_changes.append(change_info)

                    # Extract Epic/parent information
                    epic_info = None
                    parent = fields.get("parent")
                    if parent:
                        epic_info = {
                            "key": parent.get("key", ""),
                            "summary": (
                                parent.get("fields", {}).get("summary", "")
                                if parent.get("fields")
                                else ""
                            ),
                        }

                    ticket_data = {
                        "key": ticket.get("key", ""),
                        "summary": fields.get("summary", ""),
                        "status": fields.get("status", {}).get("name", "Unknown"),
                        "assignee": (
                            fields.get("assignee", {}).get("displayName", "Unassigned")
                            if fields.get("assignee")
                            else "Unassigned"
                        ),
                        "priority": (
                            fields.get("priority", {}).get("name", "Medium")
                            if fields.get("priority")
                            else "Medium"
                        ),
                        "created": created_date.isoformat(),
                        "updated": updated_date.isoformat(),
                        "recent_changes": recent_changes,
                        "epic": epic_info,
                    }

                    activity.ticket_activity.append(ticket_data)

                    # Categorize by activity type
                    if created_date >= start_date:
                        activity.new_tickets.append(ticket_data)

                    if fields.get("resolution") and updated_date >= start_date:
                        activity.completed_tickets.append(ticket_data)

            except Exception as e:
                logger.error(f"Error searching Jira tickets: {e}")

        except Exception as e:
            logger.error(f"Error collecting Jira activity: {e}")

    async def _collect_slack_messages(
        self, activity: ProjectActivity, start_date: datetime, end_date: datetime
    ):
        """Collect Slack messages from the project's designated channel."""
        try:
            if not self.slack_bot:
                logger.info(
                    f"Slack bot not available, skipping Slack collection for {activity.project_key}"
                )
                return

            # Query project_resource_mappings for Slack channels
            # Rollback any previous failed transaction
            self.session.rollback()

            result = self.session.execute(
                self.text(
                    "SELECT slack_channel_ids FROM project_resource_mappings WHERE project_key = :key"
                ),
                {"key": activity.project_key},
            ).first()

            if not result or not result[0]:
                logger.info(
                    f"No Slack channels configured for project {activity.project_key}"
                )
                return

            # Parse JSON array of channel IDs
            import json

            slack_channel_ids = (
                json.loads(result[0]) if isinstance(result[0], str) else result[0]
            )

            if not slack_channel_ids or len(slack_channel_ids) == 0:
                logger.info(
                    f"Empty Slack channel list for project {activity.project_key}"
                )
                return

            # For now, use the first channel (we can enhance to support multiple channels later)
            slack_channel = slack_channel_ids[0]
            logger.info(
                f"Found Slack channel '{slack_channel}' for project {activity.project_key} (from {len(slack_channel_ids)} configured channels)"
            )

            # Calculate how many messages to fetch based on the time period
            days_back = (end_date - start_date).days
            message_limit = min(
                50, max(10, days_back * 5)
            )  # 5 messages per day, with bounds

            # Use channel directly if it's already an ID, otherwise try to resolve
            if slack_channel.startswith("C") and len(slack_channel) >= 9:
                channel_id = slack_channel  # Already a channel ID
                logger.info(f"Using channel ID directly: {channel_id}")
            else:
                # Resolve channel name to ID (supports both names and IDs)
                channel_id = await self.slack_bot.resolve_channel_name_to_id(
                    slack_channel
                )

            # Fetch messages from the channel
            messages = await self.slack_bot.read_channel_history(
                channel_id, limit=message_limit
            )

            # Filter messages by date range
            filtered_messages = []
            for message in messages:
                message_timestamp = float(message.get("timestamp", 0))
                message_date = datetime.fromtimestamp(message_timestamp)

                if start_date <= message_date <= end_date:
                    # Filter out bot messages and empty messages
                    if (
                        not message.get("bot_id")
                        and message.get("text")
                        and len(message.get("text", "").strip()) > 10
                    ):
                        filtered_messages.append(
                            {
                                "text": message.get("text", ""),
                                "user": message.get("user", "unknown"),
                                "timestamp": message_date.isoformat(),
                                "ts": message.get("timestamp"),
                            }
                        )

            activity.slack_messages = filtered_messages
            logger.info(
                f"Collected {len(filtered_messages)} Slack messages from {slack_channel} (resolved to {channel_id})"
            )

            # Extract key discussions using AI if we have messages
            if filtered_messages:
                await self._extract_key_discussions(activity, filtered_messages)

        except Exception as e:
            logger.error(f"Error collecting Slack messages: {e}")
            activity.slack_messages = []
            activity.key_discussions = []

    async def _extract_key_discussions(
        self, activity: ProjectActivity, messages: List[Dict[str, Any]]
    ):
        """Extract key discussions and decisions from Slack messages using AI."""
        try:
            # Combine all message text for analysis
            combined_text = "\n".join([f"{msg['text']}" for msg in messages])

            if len(combined_text.strip()) < 50:
                return

            # Get max chars from settings
            max_chars = self.prompt_manager.get_setting(
                "slack_messages_max_chars", 3000
            )

            # Get and format the prompt from configuration
            discussions_prompt = self.prompt_manager.format_prompt(
                "slack_analysis",
                "discussions_prompt_template",
                project_name=activity.project_name,
                project_key=activity.project_key,
                messages=combined_text[:max_chars],  # Limit to avoid token issues
            )

            from langchain_core.messages import HumanMessage, SystemMessage

            messages_for_ai = [
                SystemMessage(
                    content="You are a project manager analyzing team communications. Extract key business and technical discussions from Slack messages."
                ),
                HumanMessage(content=discussions_prompt),
            ]

            # Use the LLM to extract key discussions
            try:
                response = await self.analyzer.llm.ainvoke(messages_for_ai)
            except AttributeError:
                response = self.analyzer.llm.invoke(messages_for_ai)

            # Parse the response
            discussions = (
                json.loads(response.content)
                if response.content.startswith("[")
                else [response.content]
            )
            max_discussions = self.prompt_manager.get_setting("max_key_discussions", 10)
            activity.key_discussions = discussions[
                :max_discussions
            ]  # Limit to configured max

        except Exception as e:
            logger.error(f"Error extracting key discussions: {e}")
            # Fallback: use first few messages as basic discussions
            activity.key_discussions = [
                msg["text"][:100] + "..." for msg in messages[:3]
            ]

    async def _collect_time_tracking_data(
        self, activity: ProjectActivity, start_date: datetime, end_date: datetime
    ):
        """Collect time tracking data using accurate Tempo v4 API with issue ID resolution."""
        try:
            import requests
            import base64
            import re
            from config.settings import settings

            logger.info(
                f"Getting time tracking data via Tempo v4 API for {activity.project_key} ({start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')})"
            )

            # Get Tempo API token
            tempo_token = settings.jira.api_token  # Fallback if no specific Tempo token
            try:
                import os

                tempo_token = os.getenv("TEMPO_API_TOKEN") or tempo_token
            except Exception:
                pass

            # Helper function to get issue key and summary from Jira using issue ID
            issue_cache = {}

            def get_issue_info_from_jira(issue_id):
                """Get issue key and summary from Jira. Returns tuple (key, summary) or (None, None)."""
                if issue_id in issue_cache:
                    return issue_cache[issue_id]

                try:
                    credentials = f"{settings.jira.username}:{settings.jira.api_token}"
                    encoded_credentials = base64.b64encode(
                        credentials.encode()
                    ).decode()

                    headers = {
                        "Authorization": f"Basic {encoded_credentials}",
                        "Accept": "application/json",
                    }

                    url = f"{settings.jira.url}/rest/api/3/issue/{issue_id}?fields=key,summary"
                    response = requests.get(url, headers=headers)
                    response.raise_for_status()
                    issue_data = response.json()
                    issue_key = issue_data.get("key")
                    issue_summary = issue_data.get("fields", {}).get("summary", "")
                    issue_cache[issue_id] = (issue_key, issue_summary)
                    return issue_key, issue_summary
                except Exception as e:
                    logger.debug(f"Error getting issue info for ID {issue_id}: {e}")
                    issue_cache[issue_id] = (None, None)
                    return None, None

            # Get Tempo worklogs using v4 API
            headers = {
                "Authorization": f"Bearer {tempo_token}",
                "Accept": "application/json",
            }

            url = "https://api.tempo.io/4/worklogs"
            params = {
                "from": start_date.strftime("%Y-%m-%d"),
                "to": end_date.strftime("%Y-%m-%d"),
                "limit": 5000,
            }

            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()

            data = response.json()
            worklogs = data.get("results", [])

            # Handle pagination
            page_count = 1
            while data.get("metadata", {}).get("next"):
                next_url = data["metadata"]["next"]
                response = requests.get(next_url, headers=headers)
                response.raise_for_status()
                data = response.json()
                page_worklogs = data.get("results", [])
                worklogs.extend(page_worklogs)
                page_count += 1

            logger.info(
                f"Retrieved {len(worklogs)} worklogs from Tempo API across {page_count} pages"
            )

            # Process worklogs with dual-stage approach
            total_hours = 0.0
            time_entries = []
            processed_count = 0
            skipped_count = 0

            # Track unique issue keys to fetch summaries for
            issue_keys_to_fetch = {}

            for worklog in worklogs:
                description = worklog.get("description", "")
                issue_key = None
                issue_summary = None

                # First try extracting project key from description (faster)
                issue_match = re.search(r"([A-Z]+-\d+)", description)
                if issue_match:
                    issue_key = issue_match.group(1)
                else:
                    # If not found in description, look up via issue ID
                    issue_id = worklog.get("issue", {}).get("id")
                    if issue_id:
                        issue_key, issue_summary = get_issue_info_from_jira(issue_id)

                if not issue_key:
                    skipped_count += 1
                    continue

                project_key = issue_key.split("-")[0]

                # Only include worklogs for the target project
                if project_key != activity.project_key:
                    continue

                processed_count += 1

                # Get hours (timeSpentSeconds / 3600)
                seconds = worklog.get("timeSpentSeconds", 0)
                hours = seconds / 3600

                total_hours += hours

                # Create time entry
                entry = {
                    "issue_key": issue_key,
                    "hours": round(hours, 2),
                    "date": worklog.get("startDate", ""),
                    "description": description,
                    "author": worklog.get("author", {}).get("displayName", "Unknown"),
                }
                # Add issue summary if we already fetched it
                if issue_summary:
                    entry["issue_summary"] = issue_summary
                else:
                    # Mark for batch fetch later
                    if issue_key not in issue_keys_to_fetch:
                        issue_keys_to_fetch[issue_key] = []
                    issue_keys_to_fetch[issue_key].append(entry)

                time_entries.append(entry)

            # Batch fetch missing issue summaries
            if issue_keys_to_fetch:
                logger.info(
                    f"Fetching summaries for {len(issue_keys_to_fetch)} unique issues"
                )
                for issue_key, entries in issue_keys_to_fetch.items():
                    try:
                        # Use Jira API to get summary
                        credentials = (
                            f"{settings.jira.username}:{settings.jira.api_token}"
                        )
                        encoded_credentials = base64.b64encode(
                            credentials.encode()
                        ).decode()

                        headers = {
                            "Authorization": f"Basic {encoded_credentials}",
                            "Accept": "application/json",
                        }

                        url = f"{settings.jira.url}/rest/api/3/issue/{issue_key}?fields=summary,parent"
                        response = requests.get(url, headers=headers)
                        response.raise_for_status()
                        issue_data = response.json()
                        fields = issue_data.get("fields", {})
                        summary = fields.get("summary", "")

                        # Extract Epic/parent information
                        epic_info = None
                        parent = fields.get("parent")
                        if parent:
                            epic_key = parent.get("key", "")
                            epic_summary = (
                                parent.get("fields", {}).get("summary", "")
                                if parent.get("fields")
                                else ""
                            )
                            epic_info = (
                                f"{epic_key}: {epic_summary}" if epic_key else None
                            )

                        # Update all entries with this issue key
                        for entry in entries:
                            entry["issue_summary"] = summary
                            entry["epic"] = epic_info
                    except Exception as e:
                        logger.debug(f"Error fetching summary for {issue_key}: {e}")

            activity.total_hours = round(total_hours, 2)
            activity.time_entries = time_entries

            logger.info(
                f"Accurate Tempo v4 API: Found {activity.total_hours}h logged for {activity.project_key} with {len(time_entries)} entries"
            )
            logger.info(
                f"Processed {processed_count} relevant worklogs, skipped {skipped_count}"
            )
            logger.info(f"Made {len(issue_cache)} Jira API calls for issue key lookups")

        except Exception as e:
            logger.error(f"Error collecting time tracking data via Tempo v4 API: {e}")
            activity.time_entries = []
            activity.total_hours = 0.0

    async def _collect_github_activity(self, activity: ProjectActivity, days_back: int):
        """Collect GitHub PR activity for the project."""
        try:
            from src.integrations.github_client import GitHubClient
            from config.settings import settings

            # Check if GitHub is configured
            is_configured = False
            if (
                settings.github.app_id
                and settings.github.private_key
                and settings.github.installation_id
            ):
                is_configured = True
            elif settings.github.api_token:
                is_configured = True

            if not is_configured:
                logger.warning(
                    "GitHub not configured - skipping PR collection. "
                    "Set GITHUB_APP_ID, GITHUB_APP_PRIVATE_KEY, GITHUB_APP_INSTALLATION_ID "
                    "or GITHUB_API_TOKEN to enable GitHub integration."
                )
                activity.github_prs_merged = []
                activity.github_prs_in_review = []
                activity.github_prs_open = []
                return

            # Initialize GitHub client
            github_client = GitHubClient(
                api_token=settings.github.api_token,
                organization=settings.github.organization,
                app_id=settings.github.app_id,
                private_key=settings.github.private_key,
                installation_id=settings.github.installation_id,
            )

            # Try to get GitHub repos from project_resource_mappings table first
            github_repos = None
            try:
                from sqlalchemy import text

                # Rollback any previous failed transaction
                self.session.rollback()

                logger.info(
                    f"Querying project_resource_mappings for project_key={activity.project_key}"
                )
                result = self.session.execute(
                    text(
                        "SELECT github_repos FROM project_resource_mappings WHERE project_key = :key"
                    ),
                    {"key": activity.project_key},
                ).first()

                logger.info(f"Query result: {result}")
                if result and result[0]:
                    import json

                    logger.info(
                        f"Raw github_repos value: {result[0]}, type: {type(result[0])}"
                    )
                    github_repos = (
                        json.loads(result[0])
                        if isinstance(result[0], str)
                        else result[0]
                    )
                    logger.info(
                        f"Found {len(github_repos)} GitHub repos from database for {activity.project_key}: {github_repos}"
                    )
                else:
                    logger.info(
                        f"No result or empty github_repos for {activity.project_key}"
                    )
            except Exception as e:
                logger.warning(
                    f"Could not query project_resource_mappings: {e}", exc_info=True
                )
                # Ensure we rollback so future queries can work
                self.session.rollback()

            # Fallback: Generate project keywords from project name (split into words)
            if not github_repos:
                project_keywords = [
                    word.lower()
                    for word in activity.project_name.split()
                    if len(word) > 2
                ]
                # Add project key as keyword
                project_keywords.append(activity.project_key.lower())
                logger.info(
                    f"No repos in database, using keyword matching for {activity.project_key}: {project_keywords}"
                )
            else:
                project_keywords = []  # Not needed when we have explicit repos

            # Get PRs organized by state
            # If we have explicit repos, fetch from each one
            if github_repos:
                # Fetch PRs from all mapped repos
                all_merged = []
                all_in_review = []
                all_open = []

                for repo_name in github_repos:
                    logger.info(f"Fetching PRs from repo: {repo_name}")
                    pr_data = await github_client.get_prs_by_date_and_state(
                        project_key=activity.project_key,
                        project_keywords=[],  # Not needed with explicit repo
                        repo_name=repo_name,
                        days_back=days_back,
                    )
                    all_merged.extend(pr_data.get("merged", []))
                    all_in_review.extend(pr_data.get("in_review", []))
                    all_open.extend(pr_data.get("open", []))

                pr_data = {
                    "merged": all_merged,
                    "in_review": all_in_review,
                    "open": all_open,
                }
            else:
                # Fallback to keyword-based auto-detection
                pr_data = await github_client.get_prs_by_date_and_state(
                    project_key=activity.project_key,
                    project_keywords=project_keywords,
                    repo_name=None,  # Auto-detect
                    days_back=days_back,
                )

            # Filter ethel PRs to only include those matching this project
            if github_repos and "ethel" in github_repos:
                logger.info("Filtering ethel PRs by project keywords")
                pr_data = self._filter_ethel_prs(pr_data, activity.project_key)

            # Store PR data in activity
            activity.github_prs_merged = pr_data.get("merged", [])
            activity.github_prs_in_review = pr_data.get("in_review", [])
            activity.github_prs_open = pr_data.get("open", [])

            logger.info(
                f"GitHub activity collected: {len(activity.github_prs_merged)} merged, "
                f"{len(activity.github_prs_in_review)} in review, {len(activity.github_prs_open)} open"
            )

        except Exception as e:
            logger.error(f"Error collecting GitHub activity: {e}", exc_info=True)
            # Don't fail the entire aggregation if GitHub fails
            activity.github_prs_merged = []
            activity.github_prs_in_review = []
            activity.github_prs_open = []

    def _filter_ethel_prs(
        self, pr_data: Dict[str, List[Dict]], project_key: str
    ) -> Dict[str, List[Dict]]:
        """Filter ethel PRs to only include those matching the project's keywords.

        Args:
            pr_data: Dictionary with 'merged', 'in_review', 'open' PR lists
            project_key: Project key to filter by

        Returns:
            Filtered PR data with only matching ethel PRs
        """
        import re
        from sqlalchemy import text

        # Get project keywords from database
        try:
            self.session.rollback()  # Ensure clean state
            result = self.session.execute(
                text("SELECT keyword FROM project_keywords WHERE project_key = :key"),
                {"key": project_key},
            ).fetchall()
            keywords = [row[0].lower() for row in result]
            logger.info(f"Project {project_key} keywords: {keywords}")
        except Exception as e:
            logger.warning(f"Could not load keywords for {project_key}: {e}")
            keywords = [project_key.lower()]

        # Add project key itself as a keyword pattern
        patterns = keywords + [project_key.lower(), f"{project_key.lower()}-\\d+"]

        def matches_project(pr: Dict) -> bool:
            """Check if a PR matches this project based on title/description."""
            # Only filter ethel repo PRs
            if pr.get("repo", {}).get("name") != "ethel":
                return True  # Keep all non-ethel PRs

            title = pr.get("title", "").lower()
            body = pr.get("body", "").lower()
            combined = f"{title} {body}"

            # Check each pattern
            for pattern in patterns:
                # Exact match or regex match
                if pattern in combined or re.search(pattern, combined, re.IGNORECASE):
                    logger.debug(
                        f"ethel PR #{pr.get('number')} matches pattern '{pattern}': {title}"
                    )
                    return True

            logger.debug(
                f"ethel PR #{pr.get('number')} does NOT match {project_key}: {title}"
            )
            return False

        # Filter each PR list
        filtered = {
            "merged": [pr for pr in pr_data.get("merged", []) if matches_project(pr)],
            "in_review": [
                pr for pr in pr_data.get("in_review", []) if matches_project(pr)
            ],
            "open": [pr for pr in pr_data.get("open", []) if matches_project(pr)],
        }

        # Log filtering results
        original_counts = {
            k: len(pr_data.get(k, [])) for k in ["merged", "in_review", "open"]
        }
        filtered_counts = {k: len(v) for k, v in filtered.items()}

        logger.info(
            f"ethel PR filtering for {project_key}: "
            f"merged {original_counts['merged']}->{filtered_counts['merged']}, "
            f"in_review {original_counts['in_review']}->{filtered_counts['in_review']}, "
            f"open {original_counts['open']}->{filtered_counts['open']}"
        )

        return filtered

    async def _collect_historical_context(
        self, activity: ProjectActivity, days_back: int
    ):
        """Collect historical context from Pinecone for richer AI insights."""
        try:
            from src.services.vector_search import VectorSearchService

            logger.info(f"Collecting historical context for {activity.project_key}")

            # Initialize vector search service
            vector_search = VectorSearchService()

            # Check if Pinecone is available
            if not vector_search.is_available():
                logger.warning("Pinecone not available - skipping historical context")
                activity.historical_context = []
                return

            # Build search query based on project context
            search_query = f"{activity.project_name} {activity.project_key} past decisions discussions blockers solutions"

            # Search for relevant historical documents
            results = vector_search.search(
                query=search_query,
                top_k=10,  # Get top 10 most relevant historical docs
                days_back=max(
                    90, days_back * 4
                ),  # Look back 90 days or 4x the current window
                project_key=activity.project_key,
            )

            # Format results for AI consumption
            formatted_context = []
            for result in results:
                formatted_context.append(
                    {
                        "source": result.source,
                        "title": result.title,
                        "content": result.content[:500],  # Limit content length
                        "date": result.date.isoformat() if result.date else None,
                        "relevance_score": result.relevance_score,
                    }
                )

            activity.historical_context = formatted_context
            logger.info(f"Collected {len(formatted_context)} historical context items")

        except Exception as e:
            logger.warning(f"Error collecting historical context: {e}")
            activity.historical_context = []

    async def _collect_attendee_context(
        self, activity: ProjectActivity, days_back: int
    ):
        """
        Collect attendee context for meeting prep - what each team member has been working on.

        Args:
            activity: ProjectActivity object with aggregated data
            days_back: Number of days to look back for activity
        """
        try:
            logger.info(f"Collecting attendee context for {activity.project_key}")

            # Get meeting attendees for this project
            attendees = self._get_meeting_attendees(activity.project_key, days_back)

            if not attendees:
                logger.info(f"No meeting attendees found for {activity.project_key}")
                activity.attendee_context = []
                return

            # Build attendee context list
            attendee_contexts = []

            for email in attendees:
                try:
                    logger.debug(f"Processing attendee: {email}")

                    # Get user activity
                    user_activity = self._get_user_activity(
                        project_key=activity.project_key,
                        email=email,
                        start_date=activity.start_date,
                        end_date=activity.end_date,
                        activity=activity,
                    )

                    # Generate talking points
                    talking_points = await self._generate_talking_points(
                        user_activity, email
                    )

                    # Try to get display name from Jira user cache or fall back to email
                    display_name = email
                    try:
                        # Try to extract name from email (e.g., "john.doe@example.com" -> "John Doe")
                        if "@" in email:
                            username = email.split("@")[0]
                            # Convert to title case and replace dots/underscores with spaces
                            display_name = (
                                username.replace(".", " ").replace("_", " ").title()
                            )
                    except Exception:
                        pass

                    # Build context dict
                    context = {
                        "email": email,
                        "name": display_name,
                        "tickets": user_activity.get("tickets", []),
                        "time_hours": user_activity.get("time_hours", 0.0),
                        "prs": user_activity.get("prs", []),
                        "slack_activity_count": user_activity.get(
                            "slack_activity_count", 0
                        ),
                        "talking_points": talking_points,
                    }

                    attendee_contexts.append(context)
                    logger.debug(
                        f"Added context for {email}: {len(talking_points)} talking points"
                    )

                except Exception as e:
                    logger.warning(f"Error processing attendee {email}: {e}")
                    # Continue with other attendees
                    continue

            activity.attendee_context = attendee_contexts
            logger.info(f"Collected context for {len(attendee_contexts)} attendees")

        except Exception as e:
            logger.warning(f"Error collecting attendee context: {e}")
            activity.attendee_context = []

    async def _match_topics_to_activity(self, activity: ProjectActivity):
        """Match topics from the most recent meeting to project activity."""

        # Get most recent meeting with topics
        if not activity.meetings:
            activity.last_meeting_followup = None
            return

        # Sort meetings by date (most recent first)
        sorted_meetings = sorted(
            activity.meetings, key=lambda m: m.get("date", ""), reverse=True
        )

        # Find first meeting with action items (topics)
        most_recent_meeting = None
        for meeting in sorted_meetings:
            action_items = meeting.get("action_items", [])
            if action_items and len(action_items) > 0:
                most_recent_meeting = meeting
                break

        if not most_recent_meeting:
            activity.last_meeting_followup = None
            return

        # Use action items as "topics" to follow up on
        action_items = most_recent_meeting.get("action_items", [])

        # Initialize result structure
        matched_topics = []

        for action_item in action_items:
            topic_title = action_item.get("title", "Untitled")

            # Initialize containers for matched activity
            matched_tickets = []
            matched_prs = []
            matched_slack = []
            total_time = 0.0

            # Extract keywords from topic title (lowercase, remove common words)
            keywords = self._extract_keywords(topic_title)

            # Check if topic references an Epic (e.g., "SUBS-618: Feature Name")
            epic_key = self._extract_epic_key(topic_title)

            # Match Jira tickets
            for ticket in activity.ticket_activity:
                is_match = False

                # Epic-based matching
                if epic_key and ticket.get("epic", {}).get("key") == epic_key:
                    is_match = True

                # Keyword-based matching
                if not is_match and keywords:
                    ticket_text = (
                        f"{ticket.get('summary', '')} {ticket.get('key', '')}".lower()
                    )
                    if any(kw in ticket_text for kw in keywords):
                        is_match = True

                if is_match:
                    matched_tickets.append(
                        {
                            "key": ticket.get("key", ""),
                            "summary": ticket.get("summary", ""),
                            "status": ticket.get("status", "Unknown"),
                        }
                    )

            # Match GitHub PRs
            all_prs = (
                activity.github_prs_merged
                + activity.github_prs_in_review
                + activity.github_prs_open
            )

            for pr in all_prs:
                pr_text = f"{pr.get('title', '')} {pr.get('body', '')}".lower()

                # Check for Epic key or keywords
                if (epic_key and epic_key.lower() in pr_text) or (
                    keywords and any(kw in pr_text for kw in keywords)
                ):
                    matched_prs.append(
                        {
                            "number": pr.get("number"),
                            "title": pr.get("title", ""),
                            "state": pr.get("state", "unknown"),
                        }
                    )

            # Match Slack messages
            for msg in activity.slack_messages:
                msg_text = msg.get("text", "").lower()

                if keywords and any(kw in msg_text for kw in keywords):
                    matched_slack.append(
                        {
                            "text": msg.get("text", "")[:100],  # Truncate for brevity
                            "user": msg.get("user", "Unknown"),
                        }
                    )

            # Sum time logged on related tickets
            for entry in activity.time_entries:
                entry_key = entry.get("issue_key", "")
                entry_epic = entry.get("epic", "")
                entry_desc = entry.get("description", "").lower()

                # Match by Epic or by ticket key appearing in matched tickets
                if (
                    (epic_key and epic_key in entry_epic)
                    or any(t["key"] == entry_key for t in matched_tickets)
                    or (keywords and any(kw in entry_desc for kw in keywords))
                ):
                    total_time += entry.get("hours", 0)

            # Deduplicate matched_tickets by key
            seen_keys = set()
            unique_tickets = []
            for ticket in matched_tickets:
                if ticket["key"] not in seen_keys:
                    seen_keys.add(ticket["key"])
                    unique_tickets.append(ticket)

            # Add to results
            has_activity = (
                len(unique_tickets) > 0
                or len(matched_prs) > 0
                or len(matched_slack) > 0
                or total_time > 0
            )

            matched_topics.append(
                {
                    "title": topic_title,
                    "has_activity": has_activity,
                    "tickets": unique_tickets[:5],  # Limit to top 5
                    "prs": matched_prs[:5],
                    "slack_messages": matched_slack[:3],
                    "time_logged": round(total_time, 1),
                }
            )

        # Store in activity
        activity.last_meeting_followup = {
            "meeting_title": most_recent_meeting.get("title", "Recent Meeting"),
            "meeting_date": (
                most_recent_meeting.get("date", "")[:10]
                if most_recent_meeting.get("date")
                else "N/A"
            ),
            "topics": matched_topics,
        }

        logger.info(
            f"Matched {len(matched_topics)} topics from last meeting to project activity"
        )

    def _extract_keywords(self, text: str) -> list:
        """Extract meaningful keywords from topic title."""
        # Remove common stopwords
        stopwords = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "is",
            "are",
            "be",
            "this",
            "that",
        }

        # Split on spaces and punctuation, lowercase
        import re

        words = re.findall(r"\b\w+\b", text.lower())

        # Filter out stopwords and short words
        keywords = [w for w in words if w not in stopwords and len(w) > 2]

        return keywords

    def _extract_epic_key(self, text: str) -> str:
        """Extract Epic key if mentioned in topic title (e.g., 'SUBS-618: Feature')."""
        import re

        match = re.search(r"\b([A-Z]+-\d+)\b", text)
        return match.group(1) if match else None

    def _get_meeting_attendees(self, project_key: str, days: int) -> List[str]:
        """
        Get list of unique meeting attendees for the project within the specified days.

        Args:
            project_key: Jira project key
            days: Number of days to look back

        Returns:
            List of unique email addresses of meeting participants
        """
        try:
            from datetime import datetime, timedelta
            from sqlalchemy import text

            cutoff_date = datetime.now() - timedelta(days=days)

            result = self.session.execute(
                text(
                    """
                    SELECT DISTINCT jsonb_array_elements_text(participants) as email
                    FROM meeting_metadata
                    WHERE project_key = :project_key
                    AND last_occurrence > :cutoff_date
                """
                ),
                {"project_key": project_key, "cutoff_date": cutoff_date},
            )

            attendees = [row[0] for row in result if row[0]]
            logger.info(
                f"Found {len(attendees)} unique attendees for {project_key} in last {days} days"
            )
            return attendees

        except Exception as e:
            logger.warning(f"Error getting meeting attendees: {e}")
            return []

    def _get_user_activity(
        self,
        project_key: str,
        email: str,
        start_date: str,
        end_date: str,
        activity: ProjectActivity,
    ) -> Dict[str, Any]:
        """
        Get activity summary for a specific user.

        Args:
            project_key: Jira project key
            email: User's email address
            start_date: Start date in ISO format
            end_date: End date in ISO format
            activity: ProjectActivity object with aggregated data

        Returns:
            Dict with user's tickets, time_hours, prs, and slack_activity_count
        """
        try:
            user_data = {
                "tickets": [],
                "time_hours": 0.0,
                "prs": [],
                "slack_activity_count": 0,
            }

            # Get user's tickets from already-collected ticket activity
            for ticket in activity.ticket_activity:
                assignee_email = ticket.get("assignee_email", "")
                assignee_name = ticket.get("assignee", "")

                # Match by email or name (since we might only have display name)
                if (
                    email.lower() in assignee_email.lower()
                    or email.lower() in assignee_name.lower()
                ):
                    user_data["tickets"].append(
                        {
                            "key": ticket.get("key", ""),
                            "summary": ticket.get("summary", ""),
                            "status": ticket.get("status", "Unknown"),
                        }
                    )

            # Get user's time hours from already-collected time entries
            for entry in activity.time_entries:
                author_name = entry.get("author", "")
                # Match by email or name
                if email.lower() in author_name.lower():
                    user_data["time_hours"] += entry.get("hours", 0)

            # Get user's PRs from already-collected GitHub data
            all_prs = (
                activity.github_prs_merged
                + activity.github_prs_in_review
                + activity.github_prs_open
            )

            for pr in all_prs:
                pr_author = pr.get("author", "")
                # Match by email or username (GitHub username might be in email)
                if email.lower() in pr_author.lower():
                    user_data["prs"].append(
                        {
                            "number": pr.get("number"),
                            "title": pr.get("title", ""),
                            "state": pr.get("state", "unknown"),
                        }
                    )

            # Get user's Slack activity count from already-collected messages
            # Try to match by email or display name
            for msg in activity.slack_messages:
                msg_user = msg.get("user", "")
                msg_user_email = msg.get("user_email", "")

                if (
                    email.lower() in msg_user.lower()
                    or email.lower() in msg_user_email.lower()
                ):
                    user_data["slack_activity_count"] += 1

            # Round time hours
            user_data["time_hours"] = round(user_data["time_hours"], 2)

            logger.debug(
                f"User activity for {email}: {len(user_data['tickets'])} tickets, "
                f"{user_data['time_hours']}h, {len(user_data['prs'])} PRs, "
                f"{user_data['slack_activity_count']} Slack messages"
            )

            return user_data

        except Exception as e:
            logger.warning(f"Error getting user activity for {email}: {e}")
            return {
                "tickets": [],
                "time_hours": 0.0,
                "prs": [],
                "slack_activity_count": 0,
            }

    async def _generate_talking_points(
        self, user_activity: Dict[str, Any], user_email: str
    ) -> List[str]:
        """
        Generate talking points for a user based on their activity.

        Args:
            user_activity: Dict with user's activity data
            user_email: User's email address

        Returns:
            List of 2-4 talking point strings
        """
        try:
            import json
            from langchain_core.messages import HumanMessage, SystemMessage

            # Build activity summary for prompt
            activity_summary = {
                "tickets_count": len(user_activity.get("tickets", [])),
                "tickets": user_activity.get("tickets", [])[
                    :5
                ],  # Limit to 5 for context
                "time_logged_hours": user_activity.get("time_hours", 0),
                "prs_count": len(user_activity.get("prs", [])),
                "prs": user_activity.get("prs", [])[:3],  # Limit to 3
                "slack_messages_count": user_activity.get("slack_activity_count", 0),
            }

            # Skip if no activity
            if (
                activity_summary["tickets_count"] == 0
                and activity_summary["time_logged_hours"] == 0
                and activity_summary["prs_count"] == 0
                and activity_summary["slack_messages_count"] == 0
            ):
                return ["No recent activity tracked"]

            prompt = f"""Based on this team member's recent activity, generate 2-4 concise talking points for a team meeting.
Focus on achievements, blockers, and collaboration opportunities.

User: {user_email}
Activity Summary:
{json.dumps(activity_summary, indent=2)}

Generate 2-4 bullet points (without bullet symbols, just plain text lines).
Keep each point concise and actionable. Format as a JSON array of strings."""

            messages = [
                SystemMessage(
                    content="You are a project manager creating meeting prep materials. Generate concise, actionable talking points."
                ),
                HumanMessage(content=prompt),
            ]

            # Use the LLM to generate talking points
            try:
                response = await self.analyzer.llm.ainvoke(messages)
            except AttributeError:
                response = self.analyzer.llm.invoke(messages)

            # Parse the response
            content = response.content.strip()
            if content.startswith("["):
                talking_points = json.loads(content)
            else:
                # Fallback: split by newlines
                talking_points = [
                    line.strip() for line in content.split("\n") if line.strip()
                ]

            # Limit to 4 points
            talking_points = talking_points[:4]

            logger.debug(
                f"Generated {len(talking_points)} talking points for {user_email}"
            )
            return talking_points

        except Exception as e:
            logger.warning(f"Error generating talking points for {user_email}: {e}")
            # Fallback to basic summary
            tickets = len(user_activity.get("tickets", []))
            hours = user_activity.get("time_hours", 0)
            if tickets > 0 or hours > 0:
                return [f"Working on {tickets} ticket(s), logged {hours} hours"]
            return ["No recent activity tracked"]

    async def _fetch_tempo_direct(
        self, project_key: str, start_date: str, end_date: str
    ) -> tuple[float, list]:
        """Direct Tempo API call as fallback when MCP fails."""
        try:
            import requests
            from config.settings import settings

            # Use the same credentials that would be used for Jira
            tempo_url = (
                f"{settings.jira.url.rstrip('/')}/rest/tempo-timesheets/4/worklogs"
            )

            # Try to get Tempo API token from environment, fallback to Jira token
            import os

            tempo_token = os.getenv("TEMPO_API_TOKEN") or settings.jira.api_token

            headers = {
                "Authorization": f"Bearer {tempo_token}",
                "Content-Type": "application/json",
            }

            params = {
                "dateFrom": start_date,
                "dateTo": end_date,
                "project": project_key,
            }

            logger.info(
                f"Attempting direct Tempo API call for {project_key} from {start_date} to {end_date}"
            )

            response = requests.get(
                tempo_url, headers=headers, params=params, timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                worklogs = data.get("worklogs", [])

                total_hours = 0.0
                time_entries = []

                for worklog in worklogs:
                    issue_key = worklog.get("issue", {}).get("key", "")
                    if issue_key.startswith(f"{project_key}-"):
                        hours = float(worklog.get("timeSpentSeconds", 0)) / 3600.0
                        entry = {
                            "issue_key": issue_key,
                            "hours": hours,
                            "date": worklog.get("started", "").split("T")[0],
                            "description": worklog.get("comment", ""),
                            "author": worklog.get("author", {}).get(
                                "displayName", "Unknown"
                            ),
                        }
                        time_entries.append(entry)
                        total_hours += hours

                logger.info(
                    f"Direct Tempo API found {len(time_entries)} worklogs totaling {total_hours:.2f}h"
                )
                return total_hours, time_entries
            else:
                logger.warning(
                    f"Direct Tempo API returned {response.status_code}: {response.text}"
                )
                return 0.0, []

        except ImportError:
            logger.warning("requests library not available for direct Tempo API call")
            return 0.0, []
        except Exception as e:
            logger.error(f"Error in direct Tempo API call: {e}")
            return 0.0, []

    def _parse_tempo_response(
        self, tempo_response, project_key: str
    ) -> tuple[float, list]:
        """Parse Tempo MCP response format for a specific project."""
        total_hours = 0.0
        time_entries = []

        try:
            # Handle different response formats
            if isinstance(tempo_response, str):
                if "No worklogs found" in tempo_response or not tempo_response.strip():
                    return 0.0, []
                # Try parsing as the old string format
                return self._parse_tempo_worklogs(tempo_response, project_key)

            # Handle structured response (list or dict format)
            worklogs = []
            if isinstance(tempo_response, dict):
                worklogs = tempo_response.get("worklogs", [])
            elif isinstance(tempo_response, list):
                worklogs = tempo_response

            for worklog in worklogs:
                issue_key = (
                    worklog.get("issue", {}).get("key", "")
                    if isinstance(worklog.get("issue"), dict)
                    else worklog.get("issueKey", "")
                )

                # Only process worklogs for our project
                if issue_key.startswith(f"{project_key}-"):
                    hours = (
                        float(worklog.get("timeSpentSeconds", 0)) / 3600.0
                    )  # Convert seconds to hours
                    if hours > 0:
                        entry = {
                            "issue_key": issue_key,
                            "hours": hours,
                            "date": worklog.get("started", "").split("T")[
                                0
                            ],  # Extract date part
                            "description": worklog.get("description", ""),
                            "author": (
                                worklog.get("author", {}).get("displayName", "Unknown")
                                if isinstance(worklog.get("author"), dict)
                                else "Unknown"
                            ),
                        }
                        time_entries.append(entry)
                        total_hours += hours

            logger.info(
                f"Parsed {len(time_entries)} worklogs totaling {total_hours:.2f}h for project {project_key}"
            )
            return total_hours, time_entries

        except Exception as e:
            logger.error(f"Error parsing Tempo response: {e}")
            return 0.0, []

    def _parse_tempo_worklogs(
        self, worklogs_data: str, project_key: str
    ) -> tuple[float, list]:
        """Parse Tempo worklogs data for a specific project - handles both line and concatenated formats."""
        total_hours = 0.0
        worklog_count = 0
        time_entries = []

        if (
            not worklogs_data
            or worklogs_data.strip()
            == "No worklogs found for the specified date range."
        ):
            return 0.0, []

        # Handle both formats: newline-separated OR concatenated
        if "\n" in worklogs_data:
            # Line-separated format (like sync-hours endpoint)
            lines = worklogs_data.strip().split("\n")
            entries_to_process = lines
        else:
            # Concatenated format - split on "IssueKey: "
            entries_to_process = worklogs_data.split("IssueKey: ")[
                1:
            ]  # Skip first empty element
            # Add back the "IssueKey: " prefix we split on
            entries_to_process = [f"IssueKey: {entry}" for entry in entries_to_process]

        for entry in entries_to_process:
            if f"IssueKey: {project_key}-" in entry:
                try:
                    # Parse the entry: "IssueKey: SUBS-607 | IssueId: 34966 | Date: 2025-09-03 | Hours: 0.25 | Description: Activity: Jira"
                    parts = entry.split(" | ")
                    entry_data = {}

                    for part in parts:
                        if part.startswith("IssueKey: "):
                            entry_data["issue_key"] = part.replace("IssueKey: ", "")
                        elif part.startswith("Date: "):
                            entry_data["date"] = part.replace("Date: ", "")
                        elif part.startswith("Hours: "):
                            hours = float(part.replace("Hours: ", ""))
                            entry_data["hours"] = hours
                            total_hours += hours
                            worklog_count += 1
                        elif part.startswith("Description: "):
                            entry_data["description"] = part.replace(
                                "Description: ", ""
                            )

                    # Only add entry if we have the required fields
                    if "issue_key" in entry_data and "hours" in entry_data:
                        time_entries.append(entry_data)

                    # Log first few worklogs for debugging
                    if worklog_count <= 5:
                        logger.info(f"Sample Tempo worklog: {entry.strip()[:100]}...")

                except (ValueError, IndexError) as e:
                    logger.warning(f"Error parsing Tempo entry: {e}")
                    continue

        logger.info(
            f"Tempo MCP for {project_key}: found {worklog_count} worklogs totaling {total_hours} hours"
        )
        return total_hours, time_entries

    async def _generate_insights(
        self, activity: ProjectActivity, include_context: bool = False
    ):
        """Generate AI-powered insights from the aggregated data.

        Args:
            activity: ProjectActivity containing all aggregated data
            include_context: Whether to include historical context in AI prompt
        """
        try:
            # Extract insights from available meeting and ticket data
            # Skip database queries and use existing data directly
            all_action_items = []
            all_blockers = []
            all_decisions = []

            # Process meeting data from direct API calls (not database)
            for meeting in activity.meetings:
                # Extract basic insights from meeting title and summary
                title = meeting.get("title", "")
                summary = meeting.get("summary", "")

                # Simple keyword extraction for action items and blockers
                if (
                    "action" in title.lower()
                    or "todo" in title.lower()
                    or "next steps" in summary.lower()
                ):
                    all_action_items.append(f"Follow up on {title}")

                if (
                    "blocker" in title.lower()
                    or "issue" in title.lower()
                    or "problem" in summary.lower()
                ):
                    all_blockers.append(f"Address issues from {title}")

                if "decision" in title.lower() or "approve" in title.lower():
                    all_decisions.append(f"Decisions made in {title}")

            # Create detailed Jira ticket change summary
            ticket_changes_summary = []
            for ticket in activity.ticket_activity[:10]:  # Limit to top 10 tickets
                if ticket.get("recent_changes"):
                    change_details = []
                    for change in ticket["recent_changes"][
                        :3
                    ]:  # Top 3 changes per ticket
                        if change["field"] in [
                            "status",
                            "assignee",
                            "priority",
                            "resolution",
                        ]:
                            from_val = change["from_value"] or "None"
                            to_val = change["to_value"] or "None"
                            change_details.append(
                                f"{change['field']}: {from_val} → {to_val}"
                            )

                    if change_details:
                        ticket_changes_summary.append(
                            f"• {ticket['key']}: {', '.join(change_details)}"
                        )

            # Create time tracking summary (with Epic grouping)
            time_summary = []
            if activity.time_entries:
                # Group by issue for summary, tracking Epic info
                issue_hours = {}
                for entry in activity.time_entries:
                    key = entry.get("issue_key", "Unknown")
                    if key not in issue_hours:
                        issue_hours[key] = {
                            "hours": 0,
                            "summary": entry.get("issue_summary", "No summary"),
                            "epic": entry.get("epic"),  # Include Epic info
                        }
                    issue_hours[key]["hours"] += entry.get("hours", 0)

                for key, data in list(issue_hours.items())[:5]:  # Top 5 issues by time
                    # Include Epic context if available
                    epic_context = (
                        f" [Epic: {data['epic']}]" if data.get("epic") else ""
                    )
                    time_summary.append(
                        f"• {key} ({data['hours']}h): {data['summary'][:50]}...{epic_context}"
                    )

            # Format GitHub PR summaries
            merged_prs_summary = []
            for pr in activity.github_prs_merged[:10]:  # Top 10 merged
                author = pr.get("author", "Unknown")
                merged_prs_summary.append(
                    f"• #{pr.get('number')} - {pr.get('title')} (by {author})"
                )

            in_review_prs_summary = []
            for pr in activity.github_prs_in_review[:10]:  # Top 10 in review
                author = pr.get("author", "Unknown")
                in_review_prs_summary.append(
                    f"• #{pr.get('number')} - {pr.get('title')} (by {author})"
                )

            open_prs_summary = []
            for pr in activity.github_prs_open[:10]:  # Top 10 open
                author = pr.get("author", "Unknown")
                open_prs_summary.append(
                    f"• #{pr.get('number')} - {pr.get('title')} (by {author})"
                )

            # Format historical context if included
            historical_context_summary = ""
            if include_context and activity.historical_context:
                context_items = []
                for item in activity.historical_context[:5]:  # Top 5 most relevant
                    date_str = item.get("date", "Unknown date")
                    source = item.get("source", "Unknown source")
                    title = item.get("title", "No title")
                    content_preview = item.get("content", "")[:200]
                    relevance = item.get("relevance_score", 0)
                    context_items.append(
                        f"• [{date_str}] {title} (from {source}, relevance: {relevance:.2f})\n  {content_preview}..."
                    )
                historical_context_summary = chr(10).join(context_items)
                logger.info(
                    f"Formatted {len(context_items)} historical context items for AI prompt"
                )

            # Format detailed meeting topics for AI analysis
            detailed_meeting_summaries = []
            for meeting in activity.meetings[:5]:  # Include top 5 most recent meetings
                meeting_title = meeting.get("title", "Untitled Meeting")
                meeting_date = meeting.get("date", "")[:10]  # Just the date part
                topics = meeting.get("topics", [])

                if topics:
                    meeting_details = [f"**{meeting_title}** ({meeting_date})"]
                    for topic in topics[:3]:  # Top 3 topics per meeting
                        topic_title = topic.get("title", "No title")
                        content_items = topic.get("content_items", [])
                        if content_items:
                            # Join content items as bullet points
                            content_str = chr(10).join(
                                f"  - {item}" for item in content_items[:5]
                            )
                            meeting_details.append(f"  • {topic_title}:")
                            meeting_details.append(content_str)
                    detailed_meeting_summaries.append(chr(10).join(meeting_details))

            meeting_details_text = (
                chr(10).join(detailed_meeting_summaries)
                if detailed_meeting_summaries
                else "- No recent meetings with detailed analysis"
            )
            logger.info(
                f"Formatted {len(detailed_meeting_summaries)} meetings with detailed topics for AI prompt"
            )

            # Format last meeting follow-up
            last_meeting_text = "- No recent meetings with action items"
            last_meeting_title = "N/A"
            last_meeting_date = "N/A"

            if activity.last_meeting_followup:
                followup = activity.last_meeting_followup
                last_meeting_title = followup.get("meeting_title", "Recent Meeting")
                last_meeting_date = followup.get("meeting_date", "N/A")

                topic_sections = []
                for topic in followup["topics"]:
                    topic_lines = [f"**{topic['title']}**"]

                    if not topic["has_activity"]:
                        topic_lines.append("  - No activity this week")
                    else:
                        if topic["tickets"]:
                            tickets_str = ", ".join(
                                [
                                    f"{t['key']} ({t['status']})"
                                    for t in topic["tickets"]
                                ]
                            )
                            topic_lines.append(f"  - Tickets: {tickets_str}")
                        if topic["prs"]:
                            prs_str = ", ".join(
                                [f"#{p['number']} ({p['state']})" for p in topic["prs"]]
                            )
                            topic_lines.append(f"  - PRs: {prs_str}")
                        if topic["slack_messages"]:
                            topic_lines.append(
                                f"  - Slack: {len(topic['slack_messages'])} messages"
                            )
                        if topic["time_logged"] > 0:
                            topic_lines.append(
                                f"  - Time logged: {topic['time_logged']}h"
                            )

                    topic_sections.append(chr(10).join(topic_lines))

                last_meeting_text = chr(10).join(topic_sections)
                logger.info(
                    f"Formatted follow-up for {len(followup['topics'])} topics from last meeting"
                )

            # Format the insights prompt from configuration
            insights_prompt = self.prompt_manager.format_prompt(
                "digest_generation",
                "insights_prompt_template",
                project_name=activity.project_name,
                project_key=activity.project_key,
                start_date=activity.start_date,
                end_date=activity.end_date,
                num_meetings=len(activity.meetings),
                num_discussions=len(activity.slack_messages),
                total_hours=activity.total_hours,
                meeting_summaries=meeting_details_text,  # Use detailed meeting topics instead of brief summaries
                decisions=chr(10).join(
                    f"- {decision}" for decision in all_decisions[:3]
                )
                or "- No major decisions recorded",
                slack_discussions=(
                    chr(10).join(
                        f"- {discussion}" for discussion in activity.key_discussions[:5]
                    )
                    if activity.key_discussions
                    else "- No significant Slack discussions"
                ),
                completed_tickets=chr(10).join(
                    f'- {ticket.get("key", "Unknown")}: {ticket.get("summary", "No summary")}'
                    f'{" [Epic: " + ticket.get("epic", {}).get("key", "") + ": " + ticket.get("epic", {}).get("summary", "") + "]" if ticket.get("epic") else ""}'
                    for ticket in activity.completed_tickets[:5]
                )
                or "- No tickets completed",
                time_summary=chr(10).join(time_summary)
                or "- No time tracking data available",
                blockers=chr(10).join(f"- {blocker}" for blocker in all_blockers[:3])
                or "- No blockers identified",
                merged_prs=chr(10).join(merged_prs_summary)
                or "- No PRs merged this week",
                in_review_prs=chr(10).join(in_review_prs_summary)
                or "- No PRs currently in review",
                open_prs=chr(10).join(open_prs_summary) or "- No open PRs",
                historical_context=historical_context_summary
                or "- No historical context available",
                last_meeting_title=last_meeting_title,
                last_meeting_date=last_meeting_date,
                last_meeting_followup=last_meeting_text,
            )

            # Use the LLM directly instead of the non-existent generate_insights method
            from langchain_core.messages import HumanMessage, SystemMessage

            # Get system message from configuration with project-specific context
            default_system_message = (
                f"You are a project management assistant generating a Weekly Recap for the {activity.project_key} project. "
                f"CRITICAL: You must ONLY reference Jira tickets that start with '{activity.project_key}-'. "
                f"DO NOT reference or invent tickets from other projects (e.g., SUBS-, SATG-, KBNT-, etc. unless that IS the project key). "
                f"Generate concise, accurate insights using ONLY the data provided in the prompt."
            )
            system_message = self.prompt_manager.get_prompt(
                "digest_generation", "system_message", default=default_system_message
            )

            messages = [
                SystemMessage(content=system_message),
                HumanMessage(content=insights_prompt),
            ]

            # Check if we have an async invoke method
            try:
                response = await self.analyzer.llm.ainvoke(messages)
            except AttributeError:
                # Fallback to sync version
                response = self.analyzer.llm.invoke(messages)
            insights = response.content

            logger.info(
                f"AI insights generated - length: {len(insights) if insights else 0}"
            )
            if insights:
                logger.info(f"AI insights content preview: {insights[:200]}...")

            if insights:
                try:
                    # Strip markdown code fences if present (```json ... ``` or ``` ... ```)
                    insights_clean = insights.strip()
                    if insights_clean.startswith("```"):
                        # Remove opening fence (```json or ```)
                        lines = insights_clean.split("\n")
                        if lines[0].startswith("```"):
                            lines = lines[1:]
                        # Remove closing fence
                        if lines and lines[-1].strip() == "```":
                            lines = lines[:-1]
                        insights_clean = "\n".join(lines).strip()

                    parsed_insights = json.loads(insights_clean)

                    # Validate ticket references to prevent AI hallucination
                    import re

                    def validate_tickets_for_project(
                        text: str, project_key: str
                    ) -> str:
                        """Find all ticket references and check they match the project."""
                        if not text:
                            return text

                        # Find all ticket patterns (e.g., SUBS-123, SATG-456)
                        ticket_pattern = r"\b([A-Z]+-\d+)\b"
                        matches = re.findall(ticket_pattern, text)

                        if not matches:
                            return text

                        wrong_project_tickets = [
                            t for t in matches if not t.startswith(f"{project_key}-")
                        ]

                        if wrong_project_tickets:
                            logger.error(
                                f"🚨 AI HALLUCINATION DETECTED: Found tickets from wrong projects: {wrong_project_tickets}"
                            )
                            logger.error(f"   Expected project: {project_key}")
                            logger.error(f"   Full text: {text[:200]}...")
                            # Remove wrong tickets from text
                            for wrong_ticket in wrong_project_tickets:
                                text = text.replace(
                                    wrong_ticket + ":", "[INVALID-TICKET]:"
                                )
                                text = text.replace(wrong_ticket, "[INVALID-TICKET]")

                        return text

                    # Check if this is V2 format or original format
                    is_v2_response = "project_pulse" in parsed_insights

                    if is_v2_response:
                        # Store V2 Strategic Synthesis format with validation
                        activity.project_pulse = validate_tickets_for_project(
                            parsed_insights.get("project_pulse", ""),
                            activity.project_key,
                        )
                        activity.story_of_the_week = validate_tickets_for_project(
                            parsed_insights.get("story_of_the_week", ""),
                            activity.project_key,
                        )
                        activity.looking_ahead_agenda = validate_tickets_for_project(
                            parsed_insights.get("looking_ahead_agenda", ""),
                            activity.project_key,
                        )
                        activity.internal_pm_notes = validate_tickets_for_project(
                            parsed_insights.get("internal_pm_notes", ""),
                            activity.project_key,
                        )

                        logger.info("Parsed V2 Strategic Synthesis format response")

                    else:
                        # Store new 7-section Weekly Recap format with validation
                        activity.executive_summary = validate_tickets_for_project(
                            parsed_insights.get("executive_summary", ""),
                            activity.project_key,
                        )
                        activity.followup_on_meeting = validate_tickets_for_project(
                            parsed_insights.get("followup_on_meeting", ""),
                            activity.project_key,
                        )
                        activity.achievements = validate_tickets_for_project(
                            parsed_insights.get("achievements", ""),
                            activity.project_key,
                        )
                        activity.active_work = validate_tickets_for_project(
                            parsed_insights.get("active_work", ""), activity.project_key
                        )
                        activity.blockers_and_asks = validate_tickets_for_project(
                            parsed_insights.get("blockers_and_asks", ""),
                            activity.project_key,
                        )
                        activity.proposed_agenda = validate_tickets_for_project(
                            parsed_insights.get("proposed_agenda", ""),
                            activity.project_key,
                        )
                        activity.progress_notes = validate_tickets_for_project(
                            parsed_insights.get("progress_notes", ""),
                            activity.project_key,
                        )

                        logger.info("Parsed original Weekly Recap format response")

                    # Also populate legacy format for backward compatibility
                    activity.noteworthy_discussions = activity.executive_summary
                    activity.work_completed = activity.achievements
                    activity.topics_for_discussion = activity.proposed_agenda
                    activity.attention_required = activity.blockers_and_asks

                    # Map to very old format fields
                    activity.progress_summary = (
                        activity.progress_notes or f"{activity.achievements[:100]}..."
                        if activity.achievements
                        else ""
                    )
                    activity.key_achievements = (
                        [activity.achievements] if activity.achievements else []
                    )
                    activity.blockers_risks = (
                        [activity.blockers_and_asks]
                        if activity.blockers_and_asks
                        else []
                    )
                    activity.next_steps = (
                        [activity.active_work] if activity.active_work else []
                    )

                    # Also store the raw action items and blockers for additional context
                    max_action_items = self.prompt_manager.get_setting(
                        "max_action_items_in_digest", 10
                    )
                    max_blockers = self.prompt_manager.get_setting(
                        "max_blockers_in_digest", 5
                    )
                    activity.meeting_action_items = all_action_items[
                        :max_action_items
                    ]  # Store top action items
                    activity.meeting_blockers = all_blockers[
                        :max_blockers
                    ]  # Store top blockers

                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse AI insights as JSON: {e}")
                    logger.warning(f"Raw AI response: {insights[:1000]}...")

                    # Try to extract content manually if it's not proper JSON
                    activity.progress_summary = insights[:500]  # Truncate if too long

                    # Set the new structure fields to fallback content
                    activity.noteworthy_discussions = (
                        "Unable to parse AI insights - see raw progress summary"
                    )
                    activity.work_completed = f"Generated fallback: {len(activity.completed_tickets)} tickets completed"
                    activity.topics_for_discussion = (
                        "Review meeting notes for detailed topics"
                    )
                    activity.attention_required = ""

                    # Extract key information from stored meeting data as fallback
                    activity.key_achievements = [
                        item.get("title", "") for item in all_action_items[:3]
                    ]
                    activity.blockers_risks = all_blockers[:3]
                    activity.next_steps = [
                        "Follow up on meeting action items",
                        "Address identified blockers",
                    ]

        except Exception as e:
            import traceback

            error_details = traceback.format_exc()
            logger.error(f"Error generating insights: {e}")
            logger.error(f"Full traceback:\n{error_details}")
            logger.error(f"AI Provider: {self.analyzer.llm.__class__.__name__}")
            logger.error(f"Meeting count: {len(activity.meetings)}")
            logger.error(f"Ticket count: {len(activity.completed_tickets)}")

            # Provide basic insights even if AI processing fails
            activity.progress_summary = f"Project {activity.project_name} had {len(activity.meetings)} meetings and {len(activity.completed_tickets)} completed tickets in the past week."

            # Set the new structure fields to fallback content with error info
            error_msg = str(e) if str(e) else repr(e)
            error_info = (
                f"{type(e).__name__}: {error_msg[:100]}"
                if error_msg
                else type(e).__name__
            )
            activity.noteworthy_discussions = f"Error generating AI insights ({error_info}) - {len(activity.meetings)} meetings were held"
            activity.work_completed = f"Generated fallback: {len(activity.completed_tickets)} tickets completed this period"
            activity.topics_for_discussion = (
                "Review meeting notes for detailed discussion topics"
            )
            activity.attention_required = ""

            activity.key_achievements = [
                ticket["summary"] for ticket in activity.completed_tickets[:3]
            ]
            activity.blockers_risks = ["Review meeting notes for detailed blockers"]
            activity.next_steps = [
                "Continue current development",
                "Address any blockers identified in meetings",
            ]

    def _is_meeting_relevant(self, meeting: Dict[str, Any], project_key: str) -> bool:
        """Check if a meeting is relevant to the specified project."""
        # Check title
        title = meeting.get("title", "").lower()
        if project_key.lower() in title:
            return True

        # Check transcript for project mentions
        transcript = meeting.get("transcript", "")
        if isinstance(transcript, str) and project_key.lower() in transcript.lower():
            return True

        # Check if transcript is a list of sentences
        if isinstance(transcript, list):
            for sentence in transcript:
                if isinstance(sentence, dict) and "text" in sentence:
                    if project_key.lower() in sentence["text"].lower():
                        return True

        return False

    def _format_section_content(self, content, default_message: str) -> str:
        """Format section content, handling both strings and lists."""
        if not content:
            return f"* {default_message}"

        # If it's a list, check for character breakdown issue
        if isinstance(content, list):
            # Check if we have a character breakdown issue (many single-character items)
            single_char_items = [
                item
                for item in content
                if isinstance(item, str) and len(item.strip()) == 1
            ]
            if (
                len(single_char_items) > len(content) * 0.3
            ):  # More than 30% single characters (more aggressive)
                # This appears to be a character breakdown - try to reconstruct
                logger.warning(
                    f"Detected character breakdown in AI content ({len(single_char_items)}/{len(content)} single chars), attempting to reconstruct"
                )
                reconstructed = "".join(
                    str(item).strip() for item in content if str(item).strip()
                )
                # Try to split into meaningful bullet points
                if (
                    reconstructed and len(reconstructed) > 10
                ):  # Only if we have meaningful content
                    # Split on common delimiters and clean up
                    parts = []
                    for sep in [". - ", ". ", "- ", "\n"]:
                        if sep in reconstructed:
                            parts = [
                                p.strip()
                                for p in reconstructed.split(sep)
                                if p.strip() and len(p.strip()) > 3
                            ]
                            break
                    if not parts:
                        # Try to find sentences ending with period
                        import re

                        sentence_pattern = r"[^.]+\."
                        matches = re.findall(sentence_pattern, reconstructed)
                        if matches:
                            parts = [m.strip() for m in matches if len(m.strip()) > 10]
                        else:
                            parts = [reconstructed]

                    formatted_items = []
                    for part in parts:
                        if part and len(part) > 5:  # Only meaningful content
                            # Clean up any remaining character artifacts
                            cleaned_part = (
                                part.replace("* ", "").replace("- ", "").strip()
                            )
                            if cleaned_part:
                                formatted_items.append(f"* {cleaned_part}")

                    if formatted_items:
                        logger.info(
                            f"Successfully reconstructed {len(formatted_items)} items from character breakdown"
                        )
                        return "\n".join(formatted_items)
                    else:
                        logger.warning(
                            "Failed to reconstruct meaningful content from character breakdown"
                        )
                        return f"* {default_message}"

            # Normal list processing
            formatted_items = []
            for item in content:
                # Skip single characters unless they're meaningful
                item_str = str(item).strip()
                if len(item_str) == 1 and item_str not in ["*", "-", "•"]:
                    continue

                # Clean up ONLY the specific pattern "* *" which is incorrect bullet formatting
                clean_item = item_str.replace("* *", "*").strip()
                if not clean_item:
                    continue

                # Ensure it starts with a single asterisk for bullet points
                if not clean_item.startswith("*"):
                    clean_item = f"* {clean_item}"
                elif clean_item.startswith("* ") and not clean_item.startswith("* *"):
                    pass  # Already correctly formatted
                else:
                    clean_item = f'* {clean_item.lstrip("* ")}'
                formatted_items.append(clean_item)
            return (
                "\n".join(formatted_items)
                if formatted_items
                else f"* {default_message}"
            )

        # If it's a string, clean up ONLY the specific pattern "* *" which is incorrect bullet formatting
        if isinstance(content, str):
            # Fix only the specific "* *" pattern, preserve valid markdown bold formatting like **text**
            cleaned_content = content.replace("* *", "*").strip()
            return cleaned_content

        return str(content)

    async def _get_ticket_summary(self, issue_key: str) -> str:
        """Fetch ticket summary using Jira MCP."""
        try:
            from src.integrations.jira_mcp import JiraMCP

            jira_client = JiraMCP()
            issue_data = await jira_client.get_issue(issue_key, fields="summary")
            if issue_data and "summary" in issue_data.get("fields", {}):
                return issue_data["fields"]["summary"]
        except Exception as e:
            logger.warning(f"Failed to fetch summary for {issue_key}: {e}")
        return "Unknown"

    def format_client_agenda(
        self, activity: ProjectActivity, project_name: str = None
    ) -> str:
        """
        Format the aggregated activity into a client-ready agenda.

        Supports both old (6-section) and new (v2 strategic synthesis) formats.
        Detects format based on presence of v2-specific fields.
        """
        days = (
            datetime.fromisoformat(activity.end_date)
            - datetime.fromisoformat(activity.start_date)
        ).days

        # Detect if this is v2 format (has project_pulse instead of executive_summary)
        is_v2_format = hasattr(activity, "project_pulse") and activity.project_pulse

        if is_v2_format:
            # V2 FORMAT: Strategic Synthesis (4 sections)
            return self._format_v2_digest(
                activity, project_name or activity.project_name, days
            )

        # ORIGINAL FORMAT: Weekly Recap (6 sections)
        # Format attention section with highlighted background
        attention_section = ""
        if activity.attention_required:
            # Handle both string and list formats
            attention_content = activity.attention_required
            if isinstance(attention_content, str) and attention_content.strip():
                attention_section = f"""
## 🚨 Attention Required
> **Important items that need immediate attention:**

{self._format_section_content(activity.attention_required, "No urgent items requiring attention")}
"""
            elif isinstance(attention_content, list) and attention_content:
                attention_section = f"""
## 🚨 Attention Required
> **Important items that need immediate attention:**

{self._format_section_content(activity.attention_required, "No urgent items requiring attention")}
"""

        # Format detailed Jira ticket changes
        ticket_changes_section = ""
        if activity.jira_ticket_changes:
            changes_by_ticket = {}
            for change in activity.jira_ticket_changes:
                ticket_key = change.get("ticket_key", "Unknown")
                if ticket_key not in changes_by_ticket:
                    changes_by_ticket[ticket_key] = {
                        "summary": change.get("ticket_summary", "Unknown"),
                        "changes": [],
                    }
                change_desc = f"{change['field']}: {change['from_value']} → {change['to_value']} ({change['changed_by']})"
                changes_by_ticket[ticket_key]["changes"].append(change_desc)

            if changes_by_ticket:
                ticket_changes_section = "\n## 🔄 Ticket Updates\n"
                for ticket_key, ticket_info in list(changes_by_ticket.items())[:5]:
                    ticket_changes_section += (
                        f"* **{ticket_key}** - {ticket_info['summary']}\n"
                    )
                    for change in ticket_info["changes"][:3]:
                        ticket_changes_section += f"  - {change}\n"

        # Format time tracking section with per-ticket details and names
        time_section = ""
        if activity.total_hours > 0:
            time_section = f"\n## ⏱️ Time Tracking\n* **Total Time Logged:** {activity.total_hours:.1f} hours\n"

            # Group time entries by ticket
            if activity.time_entries:
                ticket_hours = {}
                ticket_summaries = {}

                # Collect hours and get summaries from ticket changes if available
                for entry in activity.time_entries:
                    ticket_key = entry.get("issue_key", "Unknown")
                    hours = entry.get("hours", 0)
                    if ticket_key not in ticket_hours:
                        ticket_hours[ticket_key] = 0
                    ticket_hours[ticket_key] += hours

                # Try to get summaries from existing jira_ticket_changes first
                if activity.jira_ticket_changes:
                    for change in activity.jira_ticket_changes:
                        change_ticket_key = change.get("ticket_key")
                        if (
                            change_ticket_key in ticket_hours
                            and change_ticket_key not in ticket_summaries
                        ):
                            # Try multiple fields for the summary
                            summary = (
                                change.get("ticket_summary")
                                or change.get("summary")
                                or change.get("title")
                                or change.get("subject")
                            )
                            if summary and summary != "Unknown":
                                ticket_summaries[change_ticket_key] = summary

                # For tickets without summaries, try to get them from completed tickets
                if activity.completed_tickets:
                    for ticket in activity.completed_tickets:
                        ticket_key = ticket.get("key", "")
                        if (
                            ticket_key in ticket_hours
                            and ticket_key not in ticket_summaries
                        ):
                            # Try multiple fields for the summary
                            summary = (
                                ticket.get("summary")
                                or ticket.get("title")
                                or ticket.get("subject")
                                or ticket.get("fields", {}).get("summary")
                            )
                            if summary and summary != "Unknown":
                                ticket_summaries[ticket_key] = summary

                # Also check time entries themselves for any embedded summary info
                for entry in activity.time_entries:
                    ticket_key = entry.get("issue_key", "Unknown")
                    if (
                        ticket_key in ticket_hours
                        and ticket_key not in ticket_summaries
                    ):
                        # Try to get summary from the time entry itself
                        summary = (
                            entry.get("issue_summary")
                            or entry.get("summary")
                            or entry.get("description")
                        )
                        if summary and summary != "Unknown":
                            ticket_summaries[ticket_key] = summary

                # Show top tickets by time logged with full names
                sorted_tickets = sorted(
                    ticket_hours.items(), key=lambda x: x[1], reverse=True
                )
                time_section += "\n**Time by Ticket:**\n"
                for ticket_key, hours in sorted_tickets[:8]:  # Show top 8 tickets
                    summary = ticket_summaries.get(
                        ticket_key, ""
                    )  # Get summary if available
                    if summary and summary != "Unknown":
                        time_section += (
                            f"* **{ticket_key}** - {summary}: {hours:.1f}h\n"
                        )
                    else:
                        time_section += f"* **{ticket_key}:** {hours:.1f}h\n"

        # Format new tickets section
        new_tickets_section = ""
        if activity.new_tickets:
            new_tickets_section = "\n## 🆕 New Tickets Created\n"
            for ticket in activity.new_tickets[:10]:  # Show up to 10 new tickets
                ticket_key = ticket.get("key", "Unknown")
                summary = ticket.get("summary", "No summary")
                assignee = ticket.get("assignee", "Unassigned")
                new_tickets_section += f"* **{ticket_key}** - {summary}"
                if assignee != "Unassigned":
                    new_tickets_section += f" (Assigned to: {assignee})"
                new_tickets_section += "\n"

        # Build GitHub PR section
        github_section = ""
        total_prs = (
            len(activity.github_prs_merged)
            + len(activity.github_prs_in_review)
            + len(activity.github_prs_open)
        )
        if total_prs > 0:
            github_section = "\n## 🔀 GitHub Activity\n"
            if activity.github_prs_merged:
                github_section += (
                    f"\n**Merged PRs ({len(activity.github_prs_merged)}):**\n"
                )
                for pr in activity.github_prs_merged[:5]:
                    github_section += f"* #{pr.get('number')} - {pr.get('title')} (by {pr.get('author', 'Unknown')})\n"
            if activity.github_prs_in_review:
                github_section += (
                    f"\n**In Code Review ({len(activity.github_prs_in_review)}):**\n"
                )
                for pr in activity.github_prs_in_review[:5]:
                    github_section += f"* #{pr.get('number')} - {pr.get('title')} (by {pr.get('author', 'Unknown')})\n"

        # Format blockers section (conditional)
        blockers_section = ""
        if activity.blockers_and_asks:
            # Handle both string and list formats
            blockers_content = activity.blockers_and_asks
            if isinstance(blockers_content, str) and blockers_content.strip():
                blockers_section = f"""
## 🚨 Blockers & Client Action Items
{self._format_section_content(activity.blockers_and_asks, "")}
"""

        # Format follow-up section (conditional)
        followup_section = ""
        if activity.followup_on_meeting:
            followup_content = activity.followup_on_meeting
            if isinstance(followup_content, str) and followup_content.strip():
                followup_section = f"""
## 📋 Follow-up on Last Meeting
{self._format_section_content(activity.followup_on_meeting, "")}
"""

        # Updated 5-section Weekly Recap format (removed Achievements and Progress Notes)
        agenda = f"""
# Weekly Recap: {activity.project_name}
**Period:** {activity.start_date[:10]} to {activity.end_date[:10]} ({days} days)

## 📊 Executive Summary
{self._format_section_content(activity.executive_summary, "No summary available")}
{followup_section}
## 🔄 Active Work & Next Week
{self._format_section_content(activity.active_work, "No active work tracked")}
{blockers_section}
## 📋 Proposed Agenda for Upcoming Call
{self._format_section_content(activity.proposed_agenda, "No agenda items identified")}
{github_section}{time_section}
---

**Team Activity:** {len(activity.meetings)} meetings • {activity.total_hours:.1f}h logged • {len(activity.completed_tickets)} tickets completed

*Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}*
"""
        return agenda.strip()

    def _format_v2_digest(
        self, activity: ProjectActivity, project_name: str, days: int
    ) -> str:
        """Format the V2 Strategic Synthesis digest (4 sections)."""

        # Build GitHub PR section for appendix
        github_section = ""
        total_prs = (
            len(activity.github_prs_merged)
            + len(activity.github_prs_in_review)
            + len(activity.github_prs_open)
        )
        if total_prs > 0:
            github_section = "\n## 🔀 GitHub Activity\n"
            if activity.github_prs_merged:
                github_section += (
                    f"\n**Merged PRs ({len(activity.github_prs_merged)}):**\n"
                )
                for pr in activity.github_prs_merged[:5]:
                    github_section += f"* #{pr.get('number')} - {pr.get('title')} (by {pr.get('author', 'Unknown')})\n"
            if activity.github_prs_in_review:
                github_section += (
                    f"\n**In Code Review ({len(activity.github_prs_in_review)}):**\n"
                )
                for pr in activity.github_prs_in_review[:5]:
                    github_section += f"* #{pr.get('number')} - {pr.get('title')} (by {pr.get('author', 'Unknown')})\n"

        # Build time tracking section for appendix
        time_section = ""
        if activity.total_hours > 0:
            time_section = f"\n## ⏱️ Time Tracking\n* **Total Time Logged:** {activity.total_hours:.1f} hours\n"

            # Group time entries by ticket
            if activity.time_entries:
                ticket_hours = {}
                ticket_summaries = {}

                # Collect hours
                for entry in activity.time_entries:
                    ticket_key = entry.get("issue_key", "Unknown")
                    hours = entry.get("hours", 0)
                    if ticket_key not in ticket_hours:
                        ticket_hours[ticket_key] = 0
                    ticket_hours[ticket_key] += hours

                # Get summaries from various sources
                if activity.jira_ticket_changes:
                    for change in activity.jira_ticket_changes:
                        change_ticket_key = change.get("ticket_key")
                        if (
                            change_ticket_key in ticket_hours
                            and change_ticket_key not in ticket_summaries
                        ):
                            summary = (
                                change.get("ticket_summary")
                                or change.get("summary")
                                or change.get("title")
                                or change.get("subject")
                            )
                            if summary and summary != "Unknown":
                                ticket_summaries[change_ticket_key] = summary

                if activity.completed_tickets:
                    for ticket in activity.completed_tickets:
                        ticket_key = ticket.get("key", "")
                        if (
                            ticket_key in ticket_hours
                            and ticket_key not in ticket_summaries
                        ):
                            summary = (
                                ticket.get("summary")
                                or ticket.get("title")
                                or ticket.get("subject")
                                or ticket.get("fields", {}).get("summary")
                            )
                            if summary and summary != "Unknown":
                                ticket_summaries[ticket_key] = summary

                for entry in activity.time_entries:
                    ticket_key = entry.get("issue_key", "Unknown")
                    if (
                        ticket_key in ticket_hours
                        and ticket_key not in ticket_summaries
                    ):
                        summary = (
                            entry.get("issue_summary")
                            or entry.get("summary")
                            or entry.get("description")
                        )
                        if summary and summary != "Unknown":
                            ticket_summaries[ticket_key] = summary

                # Show top tickets by time logged
                sorted_tickets = sorted(
                    ticket_hours.items(), key=lambda x: x[1], reverse=True
                )
                time_section += "\n**Time by Ticket:**\n"
                for ticket_key, hours in sorted_tickets[:8]:
                    summary = ticket_summaries.get(ticket_key, "")
                    if summary and summary != "Unknown":
                        time_section += (
                            f"* **{ticket_key}** - {summary}: {hours:.1f}h\n"
                        )
                    else:
                        time_section += f"* **{ticket_key}:** {hours:.1f}h\n"

        # Build V2 digest
        digest = f"""
# Weekly Digest: {project_name}
**Period:** {activity.start_date[:10]} to {activity.end_date[:10]} ({days} days)

## 🎯 Project Pulse
{activity.project_pulse or "No project pulse available"}

## 📖 The Story of This Week
{activity.story_of_the_week or "No story available"}

## 🔮 Looking Ahead: Decisions & Discussion Topics
{activity.looking_ahead_agenda or "No agenda items identified"}

## 🗒️ Internal PM Notes
{activity.internal_pm_notes or "No internal notes"}

---

## Appendix: Detailed Metrics
{github_section}{time_section}
---

**Team Activity:** {len(activity.meetings)} meetings • {activity.total_hours:.1f}h logged • {len(activity.completed_tickets)} tickets completed

*Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}*
"""
        return digest.strip()
