"""Slack conversational chat service with AI-powered context search."""

import logging
import time
import hashlib
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from openai import AsyncOpenAI
from slack_sdk import WebClient

from config.settings import settings
from src.services.context_search import ContextSearchService

logger = logging.getLogger(__name__)


class RateLimiter:
    """Simple in-memory rate limiter for Slack users."""

    def __init__(self, soft_limit: int = 15, hard_limit: int = 30, window_hours: int = 1):
        """Initialize rate limiter.

        Args:
            soft_limit: Soft limit (warn user but allow)
            hard_limit: Hard limit (block request)
            window_hours: Time window in hours
        """
        self.soft_limit = soft_limit
        self.hard_limit = hard_limit
        self.window_seconds = window_hours * 3600
        self._requests: Dict[str, List[float]] = {}  # user_id -> timestamps

    def check_rate_limit(self, user_id: str) -> tuple[bool, bool, int]:
        """Check if user has exceeded rate limits.

        Args:
            user_id: Slack user ID

        Returns:
            Tuple of (is_allowed, is_soft_limit_exceeded, remaining_requests)
        """
        now = time.time()
        cutoff = now - self.window_seconds

        # Get user's request history
        if user_id not in self._requests:
            self._requests[user_id] = []

        # Remove old requests outside window
        self._requests[user_id] = [ts for ts in self._requests[user_id] if ts > cutoff]

        request_count = len(self._requests[user_id])

        # Check hard limit
        if request_count >= self.hard_limit:
            return False, True, 0

        # Check soft limit
        is_soft_exceeded = request_count >= self.soft_limit
        remaining = self.hard_limit - request_count

        # Record this request
        self._requests[user_id].append(now)

        return True, is_soft_exceeded, remaining


class SlackChatService:
    """Conversational AI chat service for Slack."""

    def __init__(self):
        """Initialize chat service."""
        self.context_search = ContextSearchService()
        self.openai_client = AsyncOpenAI(api_key=settings.ai.api_key)
        self.slack_client = WebClient(token=settings.notifications.slack_bot_token)
        self.rate_limiter = RateLimiter(soft_limit=15, hard_limit=30, window_hours=1)

        # Response cache: hash(query) -> (response, timestamp)
        self._response_cache: Dict[str, tuple[str, float]] = {}
        self._cache_ttl = 3600  # 1 hour

        logger.info("SlackChatService initialized")

    def _get_cache_key(self, query: str, user_id: str) -> str:
        """Generate cache key for query."""
        # Include user_id to respect permissions
        return hashlib.md5(f"{query}:{user_id}".encode()).hexdigest()

    def _get_cached_response(self, query: str, user_id: str) -> Optional[str]:
        """Get cached response if available and fresh."""
        cache_key = self._get_cache_key(query, user_id)

        if cache_key in self._response_cache:
            response, timestamp = self._response_cache[cache_key]
            if (time.time() - timestamp) < self._cache_ttl:
                logger.info(f"Cache hit for query: {query[:50]}...")
                return response
            else:
                # Remove stale cache entry
                del self._response_cache[cache_key]

        return None

    def _cache_response(self, query: str, user_id: str, response: str):
        """Cache response."""
        cache_key = self._get_cache_key(query, user_id)
        self._response_cache[cache_key] = (response, time.time())

    async def handle_question(
        self,
        user_id: str,
        question: str,
        channel_id: str,
        thread_ts: Optional[str] = None
    ) -> None:
        """Handle a conversational question from Slack.

        Args:
            user_id: Slack user ID
            question: User's question
            channel_id: Slack channel ID
            thread_ts: Thread timestamp (for replies)
        """
        try:
            # Check rate limit
            is_allowed, is_soft_exceeded, remaining = self.rate_limiter.check_rate_limit(user_id)

            if not is_allowed:
                # Hard limit exceeded
                self.slack_client.chat_postMessage(
                    channel=channel_id,
                    thread_ts=thread_ts,
                    text="🚫 Rate limit exceeded. You've used all 30 questions this hour. Please wait a bit and try again."
                )
                return

            # Check cache first
            cached_response = self._get_cached_response(question, user_id)
            if cached_response:
                # Post cached response
                self.slack_client.chat_postMessage(
                    channel=channel_id,
                    thread_ts=thread_ts,
                    text=f"{cached_response}\n\n_[Cached response]_"
                )
                return

            # Map Slack user to app user for permission filtering
            app_user_id = self._map_slack_user_to_app_user(user_id)

            # Post "searching" message
            searching_msg = self.slack_client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                text=f"🔍 Searching for: *{question}*\n_This may take a moment..._"
            )

            search_ts = searching_msg['ts']

            # Add soft limit warning if needed
            if is_soft_exceeded:
                warning_text = f"\n\n⚠️ _You have {remaining} questions remaining this hour (soft limit: 15, hard limit: 30)_"
            else:
                warning_text = ""

            # Perform context search
            results = await self.context_search.search(
                query=question,
                days_back=90,  # Default 90 days
                user_id=app_user_id,
                detail_level="brief",  # Concise for chat
                project=None  # Could extract from question in V2
            )

            if not results.results:
                # No results found
                self.slack_client.chat_update(
                    channel=channel_id,
                    ts=search_ts,
                    text=f"🔍 No results found for: *{question}*\n\nTry different keywords or expanding the time window.{warning_text}"
                )
                return

            # Stream AI response
            await self._stream_response(
                channel_id=channel_id,
                message_ts=search_ts,
                query=question,
                results=results,
                warning_text=warning_text,
                user_id=user_id
            )

        except Exception as e:
            logger.error(f"Error handling question: {e}")
            self.slack_client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                text=f"❌ Sorry, I encountered an error: {str(e)}\n\nPlease try again or contact support."
            )

    async def _stream_response(
        self,
        channel_id: str,
        message_ts: str,
        query: str,
        results: Any,
        warning_text: str,
        user_id: str
    ) -> None:
        """Stream AI response with progressive updates.

        Args:
            channel_id: Slack channel ID
            message_ts: Message timestamp to update
            query: Original query
            results: Context search results
            warning_text: Rate limit warning text
            user_id: Slack user ID for caching
        """
        try:
            # Build context for AI
            context_blocks = []
            for i, result in enumerate(results.results[:12], 1):  # Limit to top 12
                context_blocks.append(
                    f"[{i}] {result.source.upper()} - {result.title}\n"
                    f"Date: {result.date.strftime('%Y-%m-%d')}\n"
                    f"Author: {result.author or 'Unknown'}\n"
                    f"Content: {result.content[:300]}...\n"
                )

            context_text = "\n\n".join(context_blocks)

            # Build system prompt
            system_message = (
                "You are a helpful AI assistant that answers questions based on context from "
                "Slack messages, meeting transcripts, Jira tickets, GitHub PRs, and Notion pages. "
                "Provide concise, accurate answers with inline citations [1], [2], etc. "
                "Keep responses under 250 words. Be direct and factual."
            )

            # Build user prompt
            user_prompt = f"""Query: "{query}"

CONTEXT:
{context_text}

Answer the query based on the context above. Include inline citations [1], [2], etc. to reference sources.
Keep it concise (under 250 words) and focus on answering the question directly."""

            # Stream response from OpenAI
            full_response = ""
            update_interval = 2  # Update every 2 seconds
            last_update = time.time()

            # Use configured model (gpt-5)
            api_params = {
                "model": settings.ai.model,
                "messages": [
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_prompt}
                ],
                "stream": True
            }

            # Only add temperature for models that support it
            if not settings.ai.model.startswith('o1') and not settings.ai.model.startswith('gpt-5'):
                api_params["temperature"] = 0.3

            stream = await self.openai_client.chat.completions.create(**api_params)

            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    full_response += chunk.choices[0].delta.content

                    # Update message every 2 seconds
                    now = time.time()
                    if (now - last_update) >= update_interval:
                        # Format with citations
                        formatted_response = self._format_response(full_response, results)

                        self.slack_client.chat_update(
                            channel=channel_id,
                            ts=message_ts,
                            text=formatted_response + "\n\n_Generating..._" + warning_text
                        )
                        last_update = now

            # Final update with complete response
            formatted_response = self._format_response(full_response, results)

            self.slack_client.chat_update(
                channel=channel_id,
                ts=message_ts,
                text=formatted_response + warning_text
            )

            # Cache the response
            self._cache_response(query, user_id, formatted_response)

        except Exception as e:
            logger.error(f"Error streaming response: {e}")
            self.slack_client.chat_update(
                channel=channel_id,
                ts=message_ts,
                text=f"❌ Error generating response: {str(e)}"
            )

    def _format_response(self, ai_response: str, results: Any) -> str:
        """Format AI response with source citations.

        Args:
            ai_response: Raw AI response
            results: Context search results

        Returns:
            Formatted response text
        """
        # Simple formatting - just add source list at the end
        formatted = ai_response.strip()

        # Extract unique citation numbers used in response
        import re
        citations_used = set(re.findall(r'\[(\d+)\]', ai_response))

        # Build sources section
        if citations_used and results.citations:
            formatted += "\n\n*Sources:*"
            for citation in results.citations:
                if str(citation.id) in citations_used:
                    source_emoji = {
                        'slack': '💬',
                        'fireflies': '🎙️',
                        'jira': '📋',
                        'github': '💻',
                        'notion': '📝'
                    }.get(citation.source, '📄')

                    source_line = f"\n[{citation.id}] {source_emoji} {citation.title}"
                    if citation.url:
                        source_line += f" - <{citation.url}|View>"

                    formatted += source_line

        return formatted

    def _map_slack_user_to_app_user(self, slack_user_id: str) -> Optional[int]:
        """Map Slack user to app user for permission filtering.

        Args:
            slack_user_id: Slack user ID

        Returns:
            App user ID if found, None otherwise
        """
        try:
            from src.models.user import User
            from src.utils.database import get_engine
            from sqlalchemy.orm import sessionmaker

            engine = get_engine()
            Session = sessionmaker(bind=engine)
            session = Session()

            try:
                user = session.query(User).filter(User.slack_user_id == slack_user_id).first()
                if user:
                    logger.info(f"Mapped Slack user {slack_user_id} to app user {user.id}")
                    return user.id
                else:
                    logger.info(f"No app user found for Slack user {slack_user_id}")
                    return None
            finally:
                session.close()

        except Exception as e:
            logger.error(f"Error mapping Slack user to app user: {e}")
            return None
