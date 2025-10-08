"""Service for intelligently linking Fireflies meetings to Jira projects."""

import asyncio
import logging
import re
import uuid
from typing import List, Dict, Any, Optional, Set, Tuple
from datetime import datetime, timedelta
from collections import defaultdict

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config.settings import settings
from src.integrations.fireflies import FirefliesClient
from src.integrations.jira_mcp import JiraMCPClient
from src.processors.transcript_analyzer import TranscriptAnalyzer


logger = logging.getLogger(__name__)


class MeetingProjectLinker:
    """Service for linking meetings to Jira projects based on content analysis."""

    def __init__(self):
        """Initialize the linker service."""
        self.fireflies_client = FirefliesClient(settings.fireflies.api_key)
        self.jira_client = JiraMCPClient(
            jira_url=settings.jira.url,
            username=settings.jira.username,
            api_token=settings.jira.api_token
        )
        self.analyzer = TranscriptAnalyzer()

        # Database setup
        from src.utils.database import get_engine
        self.engine = get_engine()  # Use centralized engine with proper pool settings
        self.Session = sessionmaker(bind=self.engine)

    def _save_meeting_project_connections(self, meeting_id: str, meeting_title: str, meeting_date: datetime,
                                        project_relevance: List[Dict[str, Any]]) -> None:
        """Save meeting-project connections to database."""
        try:
            from main import MeetingProjectConnection

            session = self.Session()

            # Remove existing connections for this meeting
            session.query(MeetingProjectConnection).filter_by(meeting_id=meeting_id).delete()

            # Save new connections (only those with relevance score > 5.0)
            for project_data in project_relevance:
                relevance_score = project_data.get('relevance_score', 0)
                if relevance_score > 5.0:  # Only save meaningful connections
                    connection = MeetingProjectConnection(
                        id=str(uuid.uuid4()),
                        meeting_id=meeting_id,
                        meeting_title=meeting_title,
                        meeting_date=meeting_date,
                        project_key=project_data.get('project_key'),
                        project_name=project_data.get('project_name'),
                        relevance_score=str(relevance_score),
                        confidence=str(project_data.get('confidence', 0)),
                        matching_factors=project_data.get('matching_factors', []),
                        created_at=datetime.now(),
                        is_verified=False
                    )
                    session.add(connection)

            session.commit()
            session.close()
            logger.info(f"Saved {len([p for p in project_relevance if p.get('relevance_score', 0) > 1.0])} connections for meeting {meeting_id}")

        except Exception as e:
            logger.error(f"Error saving meeting-project connections: {e}")
            if 'session' in locals():
                session.rollback()
                session.close()

    async def analyze_meeting_project_relevance(self, meeting_id: str) -> Dict[str, Any]:
        """Analyze a meeting and determine relevant Jira projects."""
        try:
            # Get meeting transcript
            transcript = self.fireflies_client.get_meeting_transcript(meeting_id)
            if not transcript:
                return {"error": "Could not fetch meeting transcript"}

            # Get all available Jira projects
            async with self.jira_client as client:
                projects = await client.get_projects()

            if not projects:
                return {"error": "Could not fetch Jira projects"}

            # Since we're now using title-only matching, create a minimal analysis object
            # to avoid OpenAI API calls and quota issues
            from dataclasses import dataclass
            from typing import List

            @dataclass
            class MinimalActionItem:
                title: str = ""
                description: str = ""

            @dataclass
            class MinimalAnalysis:
                summary: str = ""
                action_items: List[MinimalActionItem] = None

                def __post_init__(self):
                    if self.action_items is None:
                        self.action_items = []

            # Create minimal analysis for title-only matching
            analysis = MinimalAnalysis()

            # Extract project-relevant information from transcript
            project_relevance = await self._calculate_project_relevance(
                transcript, analysis, projects
            )

            # Save meeting-project connections to database
            self._save_meeting_project_connections(
                meeting_id, transcript.title, transcript.date, project_relevance
            )

            return {
                "meeting_id": meeting_id,
                "meeting_title": transcript.title,
                "meeting_date": transcript.date.isoformat(),
                "relevant_projects": project_relevance,
                "analysis_summary": analysis.summary,
                "action_items_count": len(analysis.action_items),
                "suggested_projects": self._get_top_suggestions(project_relevance, 3)
            }

        except Exception as e:
            logger.error(f"Error analyzing meeting {meeting_id}: {e}")
            return {"error": str(e)}

    async def _calculate_project_relevance(self, transcript, analysis, projects) -> List[Dict[str, Any]]:
        """Calculate relevance score for each project based on meeting content."""
        project_scores = []

        for project in projects:
            score = await self._score_project_relevance(
                project, transcript, analysis
            )

            if score > 0:  # Only include projects with some relevance
                project_scores.append({
                    "project_key": project.get("key"),
                    "project_name": project.get("name"),
                    "relevance_score": score,
                    "matching_factors": score,  # Will be replaced with actual factors
                    "confidence": min(score / 10.0, 1.0)  # Normalize to 0-1
                })

        # Sort by relevance score
        project_scores.sort(key=lambda x: x["relevance_score"], reverse=True)
        return project_scores

    async def _score_project_relevance(self, project, transcript, analysis) -> float:
        """Calculate relevance score for a specific project based on TITLE ONLY."""
        score = 0.0
        matching_factors = []

        project_key = project.get("key", "").lower()
        project_name = project.get("name", "").lower()

        # Focus ONLY on meeting title for relevance
        title_lower = transcript.title.lower()

        # Direct project key in title gets very high score
        if project_key in title_lower:
            score += 50.0  # Increased from 10.0
            matching_factors.append(f"Project key '{project_key}' in meeting title")

        # Project name words in title (be more selective about common words)
        name_words = project_name.split()
        title_project_words = 0

        # Skip very common words that appear in many project names
        common_words = {'shopify', 'project', 'team', 'development', 'system', 'platform', 'service'}

        for word in name_words:
            if len(word) > 3 and word in title_lower and word not in common_words:
                title_project_words += 1
                score += 30.0  # Increased from 6.0
                matching_factors.append(f"Project name word '{word}' in meeting title")
            elif len(word) > 3 and word in title_lower and word in common_words:
                # Give much lower score for common words
                score += 2.0
                matching_factors.append(f"Common word '{word}' in meeting title (low confidence)")

        # Bonus for multiple project words in title
        if title_project_words > 1:
            score += 20.0  # Increased from 5.0
            matching_factors.append("Multiple project words in meeting title")

        # Smart title patterns for common meeting types
        additional_score, additional_factors = self._check_title_patterns(title_lower, project_key, project_name)
        score += additional_score
        matching_factors.extend(additional_factors)

        # Store matching factors for later use
        return score

    def _check_title_patterns(self, title_lower: str, project_key: str, project_name: str) -> Tuple[float, List[str]]:
        """Check for common meeting title patterns that indicate project relevance."""
        score = 0.0
        matching_factors = []

        # Common meeting patterns that suggest strong project connection
        strong_patterns = [
            f"{project_key} standup",
            f"{project_key} sync",
            f"{project_key} planning",
            f"{project_key} retrospective",
            f"{project_key} review",
            f"{project_key} demo",
            f"{project_key} kick off",
            f"{project_key} kickoff",
            f"{project_name.lower()} standup",
            f"{project_name.lower()} sync",
            f"{project_name.lower()} planning",
            f"{project_name.lower()} retrospective",
            f"{project_name.lower()} review",
            f"{project_name.lower()} demo",
        ]

        # Moderate patterns
        moderate_patterns = [
            f"{project_key} discussion",
            f"{project_key} meeting",
            f"{project_key} update",
            f"{project_name.lower()} discussion",
            f"{project_name.lower()} meeting",
            f"{project_name.lower()} update",
        ]

        # Check for strong patterns
        for pattern in strong_patterns:
            if pattern in title_lower:
                score += 8.0
                matching_factors.append(f"Strong title pattern: '{pattern}'")
                return score, matching_factors  # Only apply one strong pattern bonus

        # Check for moderate patterns
        for pattern in moderate_patterns:
            if pattern in title_lower:
                score += 4.0
                matching_factors.append(f"Moderate title pattern: '{pattern}'")
                return score, matching_factors  # Only apply one moderate pattern bonus

        # Check for general project-related meeting types
        meeting_types = ["standup", "sync", "scrum", "planning", "review", "retrospective", "demo"]
        for meeting_type in meeting_types:
            if meeting_type in title_lower and (project_key in title_lower or any(word in title_lower for word in project_name.lower().split() if len(word) > 3)):
                score += 3.0
                matching_factors.append(f"Project-related meeting type: '{meeting_type}'")
                break

        return score, matching_factors

    def _get_top_suggestions(self, project_relevance: List[Dict[str, Any]], limit: int = 3) -> List[Dict[str, Any]]:
        """Get top project suggestions based on relevance."""
        return project_relevance[:limit]

    async def get_meetings_for_projects(self, project_keys: List[str], days_back: int = 30) -> Dict[str, List[Dict[str, Any]]]:
        """Get meetings that are relevant to specific projects."""
        try:
            from main import MeetingProjectConnection
            from datetime import datetime, timedelta

            # First, try to get cached connections from database
            session = self.Session()
            cutoff_date = datetime.now() - timedelta(days=days_back)

            try:
                cached_connections = session.query(MeetingProjectConnection).filter(
                    MeetingProjectConnection.project_key.in_(project_keys),
                    MeetingProjectConnection.meeting_date >= cutoff_date
                ).all()

                # Filter by relevance score in Python since it's stored as string
                cached_connections = [
                    conn for conn in cached_connections
                    if conn.relevance_score and float(conn.relevance_score) > 5.0
                ]

                logger.info(f"Found {len(cached_connections)} cached connections for projects {project_keys}")

                # Get all recent meetings from Fireflies to check for missing ones
                meetings = self.fireflies_client.get_recent_meetings(days_back=days_back)

                # Find meetings that aren't cached yet
                cached_meeting_ids = {conn.meeting_id for conn in cached_connections}
                missing_meetings = [m for m in meetings if m.get("id") not in cached_meeting_ids]

                logger.info(f"Found {len(missing_meetings)} meetings not yet analyzed")

                # Start with cached results
                results = defaultdict(list)
                for conn in cached_connections:
                    meeting_summary = {
                        "meeting_id": conn.meeting_id,
                        "title": conn.meeting_title,
                        "date": int(conn.meeting_date.timestamp() * 1000),  # Convert to milliseconds
                        "relevance_score": float(conn.relevance_score),
                        "confidence": float(conn.confidence),
                        "action_items_count": 0  # We don't store this in connections
                    }
                    results[conn.project_key].append(meeting_summary)

                # Analyze missing meetings
                if missing_meetings:
                    logger.info(f"Analyzing {len(missing_meetings)} missing meetings...")
                    for meeting in missing_meetings:
                        meeting_id = meeting.get("id")
                        if not meeting_id:
                            continue

                        try:
                            # Get transcript and analyze
                            transcript = self.fireflies_client.get_meeting_transcript(meeting_id)
                            if not transcript or not transcript.transcript:
                                continue

                            # Since we're now using title-only matching, create a minimal analysis object
                            # to avoid OpenAI API calls and quota issues
                            from dataclasses import dataclass
                            from typing import List

                            @dataclass
                            class MinimalActionItem:
                                title: str = ""
                                description: str = ""

                            @dataclass
                            class MinimalAnalysis:
                                summary: str = ""
                                action_items: List[MinimalActionItem] = None

                                def __post_init__(self):
                                    if self.action_items is None:
                                        self.action_items = []

                            # Create minimal analysis for title-only matching
                            analysis = MinimalAnalysis()

                            # Calculate project relevance
                            project_relevance = []
                            projects = await self.jira_client.get_projects()

                            # Filter projects to only requested ones
                            filtered_projects = [p for p in projects if p["key"] in project_keys]

                            # Calculate relevance for all filtered projects at once
                            project_relevance = await self._calculate_project_relevance(transcript, analysis, filtered_projects)

                            # Save to database for future caching
                            if project_relevance:
                                meeting_date = datetime.fromtimestamp(meeting.get("date", 0) / 1000)
                                self._save_meeting_project_connections(
                                    meeting_id, transcript.title, meeting_date, project_relevance
                                )

                                # Add to results (only if relevance score > 5.0)
                                for proj_data in project_relevance:
                                    if proj_data["project_key"] in project_keys and proj_data["relevance_score"] > 5.0:
                                        meeting_summary = {
                                            "meeting_id": meeting_id,
                                            "title": transcript.title,
                                            "date": meeting.get("date", 0),
                                            "relevance_score": proj_data["relevance_score"],
                                            "confidence": proj_data["confidence"],
                                            "action_items_count": len(analysis.action_items)
                                        }
                                        results[proj_data["project_key"]].append(meeting_summary)

                        except Exception as meeting_error:
                            logger.warning(f"Error analyzing meeting {meeting_id}: {meeting_error}")
                            continue

                # Sort meetings by relevance score within each project
                for project_key in results:
                    results[project_key].sort(key=lambda x: x["relevance_score"], reverse=True)

                session.close()
                return dict(results)

            except Exception as db_error:
                logger.warning(f"Error with database, returning empty results: {db_error}")
                session.close()
                return {}

        except Exception as e:
            logger.error(f"Error getting meetings for projects: {e}")
            return {}

    async def suggest_project_actions(self, project_key: str, days_back: int = 30) -> Dict[str, Any]:
        """Suggest actions for a project based on recent meeting discussions."""
        try:
            # Get meetings related to this project
            project_meetings = await self.get_meetings_for_projects([project_key], days_back)
            meetings = project_meetings.get(project_key, [])

            if not meetings:
                return {
                    "project_key": project_key,
                    "suggestions": [],
                    "recent_meetings": [],
                    "message": "No recent meetings found discussing this project"
                }

            # Analyze meetings for action suggestions
            suggestions = []
            recent_discussions = []

            for meeting in meetings[:5]:  # Analyze top 5 most relevant meetings
                meeting_id = meeting["meeting_id"]

                # Get detailed analysis
                transcript = self.fireflies_client.get_meeting_transcript(meeting_id)
                if transcript:
                    # Since we're now using title-only matching, create a minimal analysis object
                    # to avoid OpenAI API calls and quota issues
                    from dataclasses import dataclass
                    from typing import List

                    @dataclass
                    class MinimalActionItem:
                        title: str = ""
                        description: str = ""

                    @dataclass
                    class MinimalAnalysis:
                        summary: str = ""
                        action_items: List[MinimalActionItem] = None

                        def __post_init__(self):
                            if self.action_items is None:
                                self.action_items = []

                    # Create minimal analysis for title-only matching
                    analysis = MinimalAnalysis()

                    # Extract project-specific action items
                    project_actions = [
                        action for action in analysis.action_items
                        if project_key.lower() in f"{action.title} {action.description}".lower()
                    ]

                    if project_actions:
                        suggestions.extend([{
                            "title": action.title,
                            "description": action.description,
                            "assignee": action.assignee,
                            "priority": action.priority,
                            "from_meeting": transcript.title,
                            "meeting_date": transcript.date.strftime("%Y-%m-%d")
                        } for action in project_actions])

                    recent_discussions.append({
                        "meeting_title": transcript.title,
                        "meeting_date": transcript.date.strftime("%Y-%m-%d"),
                        "summary": analysis.summary[:200] + "..." if len(analysis.summary) > 200 else analysis.summary,
                        "relevance_score": meeting["relevance_score"]
                    })

            return {
                "project_key": project_key,
                "suggestions": suggestions[:10],  # Limit to top 10 suggestions
                "recent_meetings": recent_discussions,
                "total_meetings_analyzed": len(meetings),
                "suggestion_count": len(suggestions)
            }

        except Exception as e:
            logger.error(f"Error suggesting actions for project {project_key}: {e}")
            return {"error": str(e)}

    async def create_project_meeting_dashboard_data(self, project_keys: List[str], days_back: int = 7) -> Dict[str, Any]:
        """Create dashboard data showing meeting-project relationships."""
        try:
            # Get meetings for all projects
            project_meetings = await self.get_meetings_for_projects(project_keys, days_back=days_back)

            # Calculate summary statistics
            total_meetings = sum(len(meetings) for meetings in project_meetings.values())
            projects_with_meetings = len([k for k, v in project_meetings.items() if v])

            # Get recent cross-project meetings (meetings relevant to multiple projects)
            cross_project_meetings = []
            all_meeting_ids = set()
            meeting_project_map = defaultdict(list)

            for project_key, meetings in project_meetings.items():
                for meeting in meetings:
                    meeting_id = meeting["meeting_id"]
                    all_meeting_ids.add(meeting_id)
                    meeting_project_map[meeting_id].append({
                        "project_key": project_key,
                        "relevance_score": meeting["relevance_score"]
                    })

            # Find meetings that appear in multiple projects
            for meeting_id, projects in meeting_project_map.items():
                if len(projects) > 1:
                    # Get meeting details
                    for project_key, meetings in project_meetings.items():
                        meeting_data = next((m for m in meetings if m["meeting_id"] == meeting_id), None)
                        if meeting_data:
                            cross_project_meetings.append({
                                "meeting_id": meeting_id,
                                "title": meeting_data["title"],
                                "date": meeting_data["date"],
                                "relevant_projects": projects,
                                "total_relevance": sum(p["relevance_score"] for p in projects)
                            })
                            break

            # Sort cross-project meetings by total relevance
            cross_project_meetings.sort(key=lambda x: x["total_relevance"], reverse=True)

            return {
                "summary": {
                    "total_meetings": total_meetings,
                    "projects_with_meetings": projects_with_meetings,
                    "cross_project_meetings": len(cross_project_meetings)
                },
                "project_meetings": project_meetings,
                "cross_project_meetings": cross_project_meetings[:10],  # Top 10
                "generated_at": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error creating dashboard data: {e}")
            return {"error": str(e)}