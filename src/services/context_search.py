"""Context search service for finding information across all integrated sources."""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """A single search result from any source."""
    source: str  # 'slack', 'fireflies', 'jira'
    title: str
    content: str
    date: datetime
    url: Optional[str] = None
    author: Optional[str] = None
    relevance_score: float = 0.0


@dataclass
class ContextSearchResults:
    """Aggregated search results across all sources."""
    query: str
    results: List[SearchResult]
    summary: Optional[str] = None
    key_people: List[str] = None
    timeline: List[Dict[str, Any]] = None


class ContextSearchService:
    """Service for searching across Slack, Fireflies, and Jira."""

    def __init__(self):
        """Initialize the context search service."""
        self.logger = logging.getLogger(__name__)

    async def search(
        self,
        query: str,
        days_back: int = 90,
        sources: List[str] = None,
        user_id: Optional[int] = None
    ) -> ContextSearchResults:
        """Search for context across all sources.

        Args:
            query: Search query/topic
            days_back: How many days back to search
            sources: List of sources to search ('slack', 'fireflies', 'jira')
            user_id: User ID for accessing user-specific credentials

        Returns:
            ContextSearchResults with aggregated results
        """
        if sources is None:
            sources = ['fireflies', 'jira']  # Slack and Notion disabled due to API/deployment limitations

        all_results = []

        # Search each source
        if 'slack' in sources:
            slack_results = await self._search_slack(query, days_back)
            all_results.extend(slack_results)

        if 'fireflies' in sources:
            fireflies_results = await self._search_fireflies(query, days_back, user_id)
            all_results.extend(fireflies_results)

        if 'jira' in sources:
            jira_results = await self._search_jira(query, days_back)
            all_results.extend(jira_results)

        if 'notion' in sources:
            notion_results = await self._search_notion(query, days_back, user_id)
            all_results.extend(notion_results)

        # Sort by date (most recent first)
        all_results.sort(key=lambda x: x.date, reverse=True)

        # Generate AI summary and insights
        summary, key_people, timeline = await self._generate_insights(query, all_results)

        return ContextSearchResults(
            query=query,
            results=all_results,
            summary=summary,
            key_people=key_people,
            timeline=timeline
        )

    async def _search_slack(self, query: str, days_back: int) -> List[SearchResult]:
        """Search Slack messages across channels.

        Note: Bot tokens cannot use search.messages API. This requires a user token
        with search:read scope. For now, we skip Slack search.
        """
        self.logger.warning(
            "Slack search requires a user token with search:read scope. "
            "Bot tokens cannot use the search.messages API. Skipping Slack search."
        )
        return []

    async def _search_fireflies(self, query: str, days_back: int, user_id: Optional[int] = None) -> List[SearchResult]:
        """Search Fireflies meeting transcripts."""
        try:
            from src.integrations.fireflies import FirefliesClient
            from config.settings import settings

            # Get user's Fireflies API key if user_id provided
            api_key = None
            if user_id:
                from src.models.user import User
                from src.utils.database import session_scope

                with session_scope() as db_session:
                    user = db_session.query(User).filter_by(id=user_id).first()
                    if user and user.has_fireflies_api_key():
                        api_key = user.get_fireflies_api_key()

            # Fall back to global API key if no user key
            if not api_key:
                api_key = settings.fireflies.api_key

            if not api_key:
                self.logger.warning("No Fireflies API key available")
                return []

            client = FirefliesClient(api_key)

            # Get recent meetings
            meetings = client.get_recent_meetings(days_back=days_back)

            results = []
            query_lower = query.lower()

            for meeting in meetings:
                # Get full transcript
                transcript = client.get_meeting_transcript(meeting['id'])
                if not transcript:
                    continue

                # Search in transcript
                transcript_text = transcript.transcript.lower()
                if query_lower in transcript_text or query_lower in meeting.get('title', '').lower():
                    # Extract relevant snippet
                    snippet = self._extract_snippet(transcript.transcript, query, max_length=300)

                    results.append(SearchResult(
                        source='fireflies',
                        title=meeting.get('title', 'Untitled Meeting'),
                        content=snippet,
                        date=transcript.date,
                        author=', '.join(transcript.attendees[:3]) if transcript.attendees else None,
                        relevance_score=0.9  # Meeting transcripts are very valuable
                    ))

            self.logger.info(f"Found {len(results)} Fireflies meetings for query: {query}")
            return results

        except Exception as e:
            self.logger.error(f"Error searching Fireflies: {e}")
            return []

    async def _search_jira(self, query: str, days_back: int) -> List[SearchResult]:
        """Search Jira issues and comments."""
        try:
            from src.integrations.jira_mcp import JiraMCPClient
            from config.settings import settings

            jira_client = JiraMCPClient(
                url=settings.jira.url,
                username=settings.jira.username,
                api_token=settings.jira.api_token
            )

            # Calculate date filter
            cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')

            # JQL query to search summary, description, and comments
            jql = f'text ~ "{query}" AND updated >= {cutoff_date} ORDER BY updated DESC'

            # Search issues
            issues = jira_client.search_issues(jql, max_results=50)

            results = []
            for issue in issues.get('issues', []):
                fields = issue.get('fields', {})

                # Parse updated date
                updated_str = fields.get('updated', '')
                updated_date = datetime.fromisoformat(updated_str.replace('Z', '+00:00')) if updated_str else datetime.now()

                # Create snippet from summary + description
                summary = fields.get('summary', '')
                description = fields.get('description', '')
                snippet = f"{summary}\n{description[:200]}..." if description else summary

                results.append(SearchResult(
                    source='jira',
                    title=f"{issue['key']}: {summary}",
                    content=snippet,
                    date=updated_date,
                    url=f"{settings.jira.url}/browse/{issue['key']}",
                    author=fields.get('reporter', {}).get('displayName', 'Unknown'),
                    relevance_score=0.85
                ))

            self.logger.info(f"Found {len(results)} Jira issues for query: {query}")
            return results

        except Exception as e:
            self.logger.error(f"Error searching Jira: {e}")
            return []

    async def _search_notion(self, query: str, days_back: int, user_id: Optional[int] = None) -> List[SearchResult]:
        """Search Notion pages and databases.

        Note: Notion integration requires Node.js/npx to be installed in the backend
        environment for the MCP server. This is not currently available in production.
        For now, we skip Notion search.
        """
        self.logger.warning(
            "Notion search requires Node.js/npx in the backend environment. "
            "This is not available in the current deployment. Skipping Notion search."
        )
        return []

    def _extract_snippet(self, text: str, query: str, max_length: int = 300) -> str:
        """Extract a relevant snippet from text around the query."""
        query_lower = query.lower()
        text_lower = text.lower()

        # Find query position
        pos = text_lower.find(query_lower)
        if pos == -1:
            # Query not found, return beginning
            return text[:max_length] + ('...' if len(text) > max_length else '')

        # Extract context around query
        start = max(0, pos - max_length // 2)
        end = min(len(text), pos + max_length // 2)

        snippet = text[start:end]
        if start > 0:
            snippet = '...' + snippet
        if end < len(text):
            snippet = snippet + '...'

        return snippet

    async def _generate_insights(
        self,
        query: str,
        results: List[SearchResult]
    ) -> tuple[Optional[str], List[str], List[Dict[str, Any]]]:
        """Generate AI-powered insights from search results."""
        try:
            from langchain_openai import ChatOpenAI
            from config.settings import settings

            if not results:
                return None, [], []

            # Prepare context for LLM
            context_parts = []
            for i, result in enumerate(results[:15], 1):  # Limit to top 15 results
                context_parts.append(
                    f"{i}. [{result.source.upper()}] {result.title}\n"
                    f"   Date: {result.date.strftime('%Y-%m-%d')}\n"
                    f"   Author: {result.author or 'Unknown'}\n"
                    f"   Content: {result.content[:200]}...\n"
                )

            context = "\n".join(context_parts)

            # Generate summary
            llm = ChatOpenAI(
                model=settings.ai.model,
                temperature=0.3,
                api_key=settings.ai.api_key
            )

            prompt = f"""Based on the following search results for "{query}", provide:

1. A 2-3 sentence summary of what was discussed/decided
2. Key people involved (just names, comma-separated)
3. A brief timeline (3-5 key events with dates)

Search Results:
{context}

Format your response as:
SUMMARY: <your summary>
PEOPLE: <comma-separated names>
TIMELINE:
- YYYY-MM-DD: <event>
- YYYY-MM-DD: <event>
"""

            response = llm.invoke(prompt)
            response_text = response.content if hasattr(response, 'content') else str(response)

            # Parse response
            summary = None
            key_people = []
            timeline = []

            lines = response_text.strip().split('\n')
            current_section = None

            for line in lines:
                line = line.strip()
                if line.startswith('SUMMARY:'):
                    summary = line.replace('SUMMARY:', '').strip()
                    current_section = 'summary'
                elif line.startswith('PEOPLE:'):
                    people_str = line.replace('PEOPLE:', '').strip()
                    key_people = [p.strip() for p in people_str.split(',') if p.strip()]
                    current_section = 'people'
                elif line.startswith('TIMELINE:'):
                    current_section = 'timeline'
                elif current_section == 'timeline' and line.startswith('-'):
                    # Parse timeline entry
                    parts = line[1:].split(':', 1)
                    if len(parts) == 2:
                        date_str, event = parts[0].strip(), parts[1].strip()
                        timeline.append({'date': date_str, 'event': event})
                elif current_section == 'summary' and line and not line.startswith('PEOPLE:'):
                    summary = (summary + ' ' + line) if summary else line

            return summary, key_people[:5], timeline[:5]  # Limit to top 5

        except Exception as e:
            self.logger.error(f"Error generating insights: {e}")
            return None, [], []
