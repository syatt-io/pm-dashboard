"""Context search service for finding information across all integrated sources."""

import logging
import re
from typing import List, Dict, Any, Optional, Set, Tuple
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
        self._project_keywords_cache = None
        self._project_keywords_cache_time = None

    def _get_project_keywords(self) -> Dict[str, List[str]]:
        """Get project keywords from database with caching.

        Returns:
            Dict mapping project_key to list of keywords
        """
        # Cache for 5 minutes
        if (self._project_keywords_cache and self._project_keywords_cache_time and
            (datetime.now() - self._project_keywords_cache_time).total_seconds() < 300):
            return self._project_keywords_cache

        try:
            from src.utils.database import get_engine
            from sqlalchemy import text

            engine = get_engine()
            project_keywords = {}

            with engine.connect() as conn:
                result = conn.execute(text("SELECT project_key, keyword FROM project_keywords"))
                for row in result:
                    project_key = row[0]
                    keyword = row[1]
                    if project_key not in project_keywords:
                        project_keywords[project_key] = []
                    project_keywords[project_key].append(keyword.lower())

            self._project_keywords_cache = project_keywords
            self._project_keywords_cache_time = datetime.now()
            self.logger.info(f"Loaded {len(project_keywords)} project keyword mappings")
            return project_keywords

        except Exception as e:
            self.logger.error(f"Error loading project keywords: {e}")
            return {}

    def _detect_project_and_expand_query(self, query: str) -> Tuple[Optional[str], Set[str], Set[str]]:
        """Detect project key in query and expand with related keywords.

        Args:
            query: Original search query

        Returns:
            Tuple of (detected_project_key, project_keywords_set, topic_keywords_set)
        """
        project_keywords_map = self._get_project_keywords()

        # Extract potential project keys (uppercase words 2-5 chars)
        potential_keys = re.findall(r'\b[A-Z]{2,5}\b', query.upper())

        detected_project = None
        project_keywords = set()

        # Check if any potential key exists in our mapping
        for key in potential_keys:
            if key in project_keywords_map:
                detected_project = key
                # Add project key and all related keywords
                project_keywords.add(key.lower())
                project_keywords.update(project_keywords_map[key])
                self.logger.info(f"Detected project {key} with {len(project_keywords_map[key])} related keywords")
                break

        # Tokenize the query into topic keywords (min 3 chars, exclude common words and project terms)
        query_words = re.findall(r'\b\w{3,}\b', query.lower())
        stop_words = {'the', 'and', 'for', 'from', 'with', 'about', 'that', 'this', 'have', 'has'}

        # Topic keywords are query words that are NOT project keywords
        topic_keywords = {w for w in query_words if w not in stop_words and w not in project_keywords}

        self.logger.info(f"Query '{query}' → Project keywords: {list(project_keywords)[:5]}, Topic keywords: {list(topic_keywords)}")
        return detected_project, project_keywords, topic_keywords

    def _score_text_match(self, text: str, keywords: Set[str]) -> Tuple[int, float]:
        """Score how well text matches the keywords.

        Args:
            text: Text to score
            keywords: Set of keywords to match

        Returns:
            Tuple of (match_count, relevance_score)
        """
        text_lower = text.lower()
        matches = sum(1 for keyword in keywords if keyword in text_lower)

        # Score is percentage of keywords matched
        relevance_score = matches / len(keywords) if keywords else 0.0

        return matches, relevance_score

    def _score_text_match_two_tier(
        self,
        text: str,
        project_keywords: Set[str],
        topic_keywords: Set[str]
    ) -> Tuple[int, int, float, bool]:
        """Score text with separate project and topic keyword matching.

        Args:
            text: Text to score
            project_keywords: Project-related keywords (e.g., SUBS, bugz, snugglebugz)
            topic_keywords: Topic keywords from query (e.g., site, design, changes)

        Returns:
            Tuple of (project_matches, topic_matches, relevance_score, passes_threshold)
        """
        text_lower = text.lower()

        # Count matches for each tier
        project_matches = sum(1 for kw in project_keywords if kw in text_lower)
        topic_matches = sum(1 for kw in topic_keywords if kw in text_lower)

        # Calculate weighted score: topic keywords count 3x more
        # Must have at least 1 project match AND 1 topic match
        if project_matches == 0 or topic_matches == 0:
            return project_matches, topic_matches, 0.0, False

        # Weighted scoring: topic keywords are 3x more important
        total_keywords = len(project_keywords) + len(topic_keywords) * 3
        weighted_matches = project_matches + (topic_matches * 3)
        relevance_score = weighted_matches / total_keywords if total_keywords > 0 else 0.0

        # Passes threshold if score >= 30% AND has both project + topic matches
        passes_threshold = relevance_score >= 0.3

        return project_matches, topic_matches, relevance_score, passes_threshold

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
            sources: List of sources to search ('slack', 'fireflies', 'jira', 'notion')
            user_id: User ID for accessing user-specific credentials

        Returns:
            ContextSearchResults with aggregated results
        """
        if sources is None:
            sources = ['slack', 'fireflies', 'jira', 'notion']

        # Detect project and expand query with keywords (two-tier: project + topic)
        detected_project, project_keywords, topic_keywords = self._detect_project_and_expand_query(query)

        all_results = []

        # Search each source with two-tier keyword matching
        if 'slack' in sources:
            slack_results = await self._search_slack(query, days_back, user_id, project_keywords, topic_keywords)
            all_results.extend(slack_results)

        if 'fireflies' in sources:
            fireflies_results = await self._search_fireflies(query, days_back, user_id, project_keywords, topic_keywords)
            all_results.extend(fireflies_results)

        if 'jira' in sources:
            jira_results = await self._search_jira(query, days_back, detected_project, project_keywords, topic_keywords)
            all_results.extend(jira_results)

        if 'notion' in sources:
            notion_results = await self._search_notion(query, days_back, user_id, project_keywords, topic_keywords)
            all_results.extend(notion_results)

        # Sort by relevance score first, then by date
        all_results.sort(key=lambda x: (x.relevance_score, x.date), reverse=True)

        # Generate AI summary and insights
        summary, key_people, timeline = await self._generate_insights(query, all_results)

        return ContextSearchResults(
            query=query,
            results=all_results,
            summary=summary,
            key_people=key_people,
            timeline=timeline
        )

    async def _search_slack(
        self,
        query: str,
        days_back: int,
        user_id: Optional[int] = None,
        project_keywords: Set[str] = None,
        topic_keywords: Set[str] = None
    ) -> List[SearchResult]:
        """Search Slack messages across channels with two-tier keyword matching.

        If user has OAuth token, use search.messages API for better results.
        Otherwise fall back to conversations.history with bot token.
        """
        if project_keywords is None:
            project_keywords = set()
        if topic_keywords is None:
            topic_keywords = set(query.lower().split())

        # Try to use user's Slack OAuth token first
        if user_id:
            try:
                from src.models.user import User
                from src.utils.database import session_scope

                with session_scope() as db_session:
                    user = db_session.query(User).filter_by(id=user_id).first()
                    if user and user.has_slack_user_token():
                        token_data = user.get_slack_user_token()
                        user_token = token_data.get('access_token')

                        if user_token:
                            # Use search.messages API with user token
                            return await self._search_slack_with_user_token(query, days_back, user_token, project_keywords, topic_keywords)
            except Exception as e:
                self.logger.warning(f"Failed to use user Slack token, falling back to bot token: {e}")

        # Fall back to bot token with conversations.history
        return await self._search_slack_with_bot_token(query, days_back, project_keywords, topic_keywords)

    async def _search_slack_with_user_token(
        self,
        query: str,
        days_back: int,
        user_token: str,
        project_keywords: Set[str],
        topic_keywords: Set[str]
    ) -> List[SearchResult]:
        """Search Slack using user token and search.messages API with two-tier matching."""
        try:
            from slack_sdk import WebClient

            client = WebClient(token=user_token)

            # Calculate timestamp for X days ago
            cutoff_date = datetime.now() - timedelta(days=days_back)
            oldest_timestamp = cutoff_date.timestamp()

            # Build query using keyword OR logic for better recall
            # Combine project and topic keywords with OR
            all_keywords = list(project_keywords | topic_keywords)
            if all_keywords:
                # Use OR logic: match any keyword
                keyword_query = ' OR '.join(all_keywords[:10])  # Limit to 10 keywords
            else:
                keyword_query = query

            # Use Slack's search API (user token only)
            response = client.search_messages(
                query=keyword_query,
                sort='timestamp',
                sort_dir='desc',
                count=100
            )

            results = []
            if response.get('messages'):
                for match in response['messages']['matches']:
                    # Parse timestamp
                    ts = float(match.get('ts', 0))
                    message_date = datetime.fromtimestamp(ts)

                    # Skip if too old
                    if ts < oldest_timestamp:
                        continue

                    # Get channel name
                    channel_name = match.get('channel', {}).get('name', 'unknown')
                    message_text = match.get('text', '')

                    # Score message with two-tier matching
                    proj_matches, topic_matches, relevance_score, passes = self._score_text_match_two_tier(
                        message_text, project_keywords, topic_keywords
                    )

                    # Skip messages that don't pass threshold (must have both project AND topic match)
                    if not passes:
                        continue

                    # Build permalink
                    permalink = match.get('permalink', '')

                    results.append(SearchResult(
                        source='slack',
                        title=f"#{channel_name}",
                        content=message_text,
                        date=message_date,
                        url=permalink,
                        author=match.get('username', 'Unknown'),
                        relevance_score=relevance_score + 0.1  # Boost for OAuth search
                    ))

            self.logger.info(f"Found {len(results)} Slack messages via user token (two-tier match)")
            return results

        except Exception as e:
            self.logger.error(f"Error searching Slack with user token: {e}")
            return []

    async def _search_slack_with_bot_token(
        self,
        query: str,
        days_back: int,
        project_keywords: Set[str],
        topic_keywords: Set[str]
    ) -> List[SearchResult]:
        """Search Slack using bot token and conversations.history with two-tier matching.

        Note: Bot tokens cannot use search.messages API, so we use conversations.history
        to search through channels the bot is a member of.
        """
        try:
            from config.settings import settings
            from slack_sdk import WebClient

            client = WebClient(token=settings.notifications.slack_bot_token)

            # Calculate timestamp for X days ago
            cutoff_date = datetime.now() - timedelta(days=days_back)
            oldest_timestamp = str(int(cutoff_date.timestamp()))

            results = []

            # Get list of channels the bot is in
            channels_response = client.conversations_list(
                exclude_archived=True,
                types="public_channel,private_channel",
                limit=200  # Increased from 100 to get more coverage
            )

            if not channels_response.get('ok'):
                self.logger.error(f"Failed to list Slack channels: {channels_response.get('error')}")
                return []

            channels = channels_response.get('channels', [])
            self.logger.info(f"Searching {len(channels)} Slack channels with two-tier matching")

            # Search through ALL channels the bot has access to (removed 20 channel limit)
            for channel in channels:
                channel_id = channel['id']
                channel_name = channel['name']

                try:
                    # Get message history
                    history = client.conversations_history(
                        channel=channel_id,
                        oldest=oldest_timestamp,
                        limit=100  # Limit messages per channel
                    )

                    if not history.get('ok'):
                        continue

                    messages = history.get('messages', [])

                    # Filter messages by two-tier keyword matching
                    for message in messages:
                        message_text = message.get('text', '')

                        # Score message with two-tier matching
                        proj_matches, topic_matches, relevance_score, passes = self._score_text_match_two_tier(
                            message_text, project_keywords, topic_keywords
                        )

                        # Skip messages that don't pass threshold (must have both project AND topic match)
                        if not passes:
                            continue

                        # Parse timestamp
                        ts = float(message.get('ts', 0))
                        message_date = datetime.fromtimestamp(ts)

                        # Get user info
                        user_id = message.get('user', 'Unknown')

                        # Build permalink
                        try:
                            permalink_response = client.chat_getPermalink(
                                channel=channel_id,
                                message_ts=message.get('ts')
                            )
                            permalink = permalink_response.get('permalink', '') if permalink_response.get('ok') else ''
                        except Exception:
                            permalink = ''

                        results.append(SearchResult(
                            source='slack',
                            title=f"#{channel_name}",
                            content=message_text,
                            date=message_date,
                            url=permalink,
                            author=user_id,
                            relevance_score=relevance_score
                        ))

                except Exception as e:
                    self.logger.warning(f"Error searching channel {channel_name}: {e}")
                    continue

            self.logger.info(f"Found {len(results)} Slack messages with two-tier matching")
            return results

        except Exception as e:
            self.logger.error(f"Error searching Slack: {e}")
            return []

    async def _search_fireflies(
        self,
        query: str,
        days_back: int,
        user_id: Optional[int] = None,
        project_keywords: Set[str] = None,
        topic_keywords: Set[str] = None
    ) -> List[SearchResult]:
        """Search Fireflies meeting transcripts with two-tier matching."""
        if project_keywords is None:
            project_keywords = set()
        if topic_keywords is None:
            topic_keywords = set(query.lower().split())

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

            for meeting in meetings:
                # Get full transcript
                transcript = client.get_meeting_transcript(meeting['id'])
                if not transcript:
                    continue

                # Search in transcript with two-tier keyword matching
                meeting_title = meeting.get('title', '')
                combined_text = f"{meeting_title} {transcript.transcript}"

                # Score with two-tier matching
                proj_matches, topic_matches, relevance_score, passes = self._score_text_match_two_tier(
                    combined_text, project_keywords, topic_keywords
                )

                # Skip meetings that don't pass threshold (must have both project AND topic match)
                if not passes:
                    continue

                # Extract relevant snippet around topic keywords (more important)
                snippet_query = ' '.join(topic_keywords) if topic_keywords else ' '.join(project_keywords)
                snippet = self._extract_snippet(transcript.transcript, snippet_query, max_length=300)

                results.append(SearchResult(
                    source='fireflies',
                    title=meeting_title or 'Untitled Meeting',
                    content=snippet,
                    date=transcript.date,
                    author=', '.join(transcript.attendees[:3]) if transcript.attendees else None,
                    relevance_score=relevance_score + 0.1  # Meeting transcripts are valuable
                ))

            self.logger.info(f"Found {len(results)} Fireflies meetings with two-tier matching")
            return results

        except Exception as e:
            self.logger.error(f"Error searching Fireflies: {e}")
            return []

    async def _search_jira(
        self,
        query: str,
        days_back: int,
        project_key: Optional[str] = None,
        project_keywords: Set[str] = None,
        topic_keywords: Set[str] = None
    ) -> List[SearchResult]:
        """Search Jira issues and comments with project filtering and two-tier matching."""
        if project_keywords is None:
            project_keywords = set()
        if topic_keywords is None:
            topic_keywords = set(query.lower().split())

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

            # Build JQL query with keyword OR logic for better recall
            # Combine all keywords for JQL search
            all_keywords = list(project_keywords | topic_keywords)
            if all_keywords:
                keyword_queries = [f'text ~ "{kw}"' for kw in all_keywords[:10]]  # Limit to 10 keywords
                keyword_jql = ' OR '.join(keyword_queries)
            else:
                keyword_jql = f'text ~ "{query}"'

            # Add project filter if project key detected
            project_filter = f' AND project = {project_key}' if project_key else ''

            jql = f'({keyword_jql}){project_filter} AND updated >= {cutoff_date} ORDER BY updated DESC'

            self.logger.info(f"Jira search JQL: {jql}")

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
                combined_text = f"{summary} {description}"

                # Score with two-tier matching
                proj_matches, topic_matches, relevance_score, passes = self._score_text_match_two_tier(
                    combined_text, project_keywords, topic_keywords
                )

                # Skip issues that don't pass threshold (must have both project AND topic match)
                if not passes:
                    continue

                snippet = f"{summary}\n{description[:200]}..." if description else summary

                results.append(SearchResult(
                    source='jira',
                    title=f"{issue['key']}: {summary}",
                    content=snippet,
                    date=updated_date,
                    url=f"{settings.jira.url}/browse/{issue['key']}",
                    author=fields.get('reporter', {}).get('displayName', 'Unknown'),
                    relevance_score=relevance_score
                ))

            project_msg = f" in project {project_key}" if project_key else ""
            self.logger.info(f"Found {len(results)} Jira issues{project_msg} with two-tier matching")
            return results

        except Exception as e:
            self.logger.error(f"Error searching Jira: {e}")
            return []

    async def _search_notion(
        self,
        query: str,
        days_back: int,
        user_id: Optional[int] = None,
        project_keywords: Set[str] = None,
        topic_keywords: Set[str] = None
    ) -> List[SearchResult]:
        """Search Notion pages and databases using the Notion API with two-tier matching."""
        if project_keywords is None:
            project_keywords = set()
        if topic_keywords is None:
            topic_keywords = set(query.lower().split())

        try:
            # Get user's Notion API key
            if not user_id:
                self.logger.info("No user_id provided for Notion search, skipping")
                return []

            from src.models.user import User
            from src.utils.database import session_scope

            api_key = None
            with session_scope() as db_session:
                user = db_session.query(User).filter_by(id=user_id).first()
                if user and user.has_notion_api_key():
                    api_key = user.get_notion_api_key()

            if not api_key:
                self.logger.info("No Notion API key found for user, skipping Notion search")
                return []

            # Use Notion API to search
            import requests

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json"
            }

            # Calculate date filter
            cutoff_date = datetime.now() - timedelta(days=days_back)

            # Search Notion with query
            search_payload = {
                "query": query,
                "filter": {
                    "value": "page",
                    "property": "object"
                },
                "sort": {
                    "direction": "descending",
                    "timestamp": "last_edited_time"
                }
            }

            response = requests.post(
                "https://api.notion.com/v1/search",
                headers=headers,
                json=search_payload,
                timeout=10
            )

            if not response.ok:
                self.logger.error(f"Notion API error: {response.status_code} - {response.text}")
                return []

            data = response.json()
            results = []

            for page in data.get('results', []):
                # Get last edited time
                last_edited = page.get('last_edited_time', '')
                if last_edited:
                    page_date = datetime.fromisoformat(last_edited.replace('Z', '+00:00'))

                    # Skip if too old
                    if page_date < cutoff_date:
                        continue
                else:
                    page_date = datetime.now()

                # Get page title
                title_property = page.get('properties', {}).get('title', {})
                title_content = title_property.get('title', [])
                title = title_content[0].get('plain_text', 'Untitled') if title_content else 'Untitled'

                # Get page URL
                url = page.get('url', '')

                # Score with two-tier matching
                # For now, just use title since fetching full content requires separate API call
                proj_matches, topic_matches, relevance_score, passes = self._score_text_match_two_tier(
                    title, project_keywords, topic_keywords
                )

                # Skip pages that don't pass threshold (must have both project AND topic match)
                if not passes:
                    continue

                results.append(SearchResult(
                    source='notion',
                    title=title,
                    content=f"Notion page: {title}",
                    date=page_date,
                    url=url,
                    author=None,
                    relevance_score=relevance_score
                ))

            self.logger.info(f"Found {len(results)} Notion pages with two-tier matching")
            return results

        except Exception as e:
            self.logger.error(f"Error searching Notion: {e}")
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
