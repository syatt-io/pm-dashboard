"""Slack conversational chat service with AI-powered context search."""

import logging
import time
import hashlib
import json
import re
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from openai import AsyncOpenAI
from slack_sdk import WebClient

from config.settings import settings
from src.services.context_search import ContextSearchService

logger = logging.getLogger(__name__)


@dataclass
class ConversationTurn:
    """A single turn in a conversation."""

    question: str
    answer: str
    timestamp: float
    search_results: Optional[List[str]] = None  # List of result titles for context


@dataclass
class QueryContext:
    """Extracted context from a query."""

    original_query: str
    project_key: Optional[str] = None
    jira_ticket: Optional[str] = None
    time_range_days: Optional[int] = None
    time_description: Optional[str] = None
    keywords: List[str] = None
    is_follow_up: bool = False
    detail_level: Optional[str] = (
        None  # Optional override for detail level (brief, normal, detailed, slack)
    )

    def __post_init__(self):
        if self.keywords is None:
            self.keywords = []


class ConversationContextManager:
    """Manages conversation history per Slack thread."""

    def __init__(self, storage_backend: str = "memory"):
        """Initialize conversation context manager.

        Args:
            storage_backend: "redis" or "memory" (default: memory)
        """
        self.storage_backend = storage_backend
        self._memory_storage: Dict[str, List[ConversationTurn]] = {}
        self._redis_client = None
        self._context_ttl = (
            86400  # 24 hours (increased from 1 hour to support longer conversations)
        )

        if storage_backend == "redis":
            import redis
            import os

            # Use REDIS_URL environment variable (Upstash Redis in production)
            self._redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

            # Create connection pool for better connection management
            try:
                self._redis_pool = redis.ConnectionPool.from_url(
                    self._redis_url,
                    decode_responses=True,
                    max_connections=10,  # Pool size for multi-worker env
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    socket_keepalive=True,  # Keep connections alive
                    socket_keepalive_options={},
                    retry_on_timeout=True,
                    health_check_interval=30,
                )

                # Initialize client from pool
                self._redis_client = redis.Redis(connection_pool=self._redis_pool)
                self._redis_client.ping()

                # Mask password in log message
                masked_url = self._mask_redis_url(self._redis_url)
                logger.info(f"✅ Using Redis for conversation context: {masked_url}")
            except Exception as e:
                # CRITICAL: Do NOT fall back to in-memory storage in multi-worker environments!
                # In-memory storage is process-local and will break conversation context across workers.
                # If Redis is required but unavailable, fail loudly to surface the issue.
                logger.error(
                    f"❌ CRITICAL: Redis connection required but failed! Multi-worker app cannot use in-memory fallback. Error: {e}"
                )
                raise RuntimeError(
                    f"Redis connection failed: {e}. "
                    "Conversation context requires Redis in multi-worker environment. "
                    "Check REDIS_URL environment variable and Redis connectivity."
                )

    def _mask_redis_url(self, url: str) -> str:
        """Mask password in Redis URL for logging.

        Args:
            url: Redis URL (e.g., redis://user:password@host:port)

        Returns:
            Masked URL with password replaced by ***
        """
        if "@" in url and "://" in url:
            protocol, rest = url.split("://", 1)
            if "@" in rest:
                auth, host = rest.rsplit("@", 1)
                return f"{protocol}://***@{host}"
        return url

    def _get_thread_key(self, channel_id: str, thread_ts: Optional[str]) -> str:
        """Generate unique key for thread."""
        if thread_ts:
            return f"slack_conv:{channel_id}:{thread_ts}"
        else:
            return f"slack_conv:{channel_id}:dm"

    def _execute_with_retry(self, operation, *args, max_retries=2, **kwargs):
        """Execute Redis operation with automatic reconnection on connection errors.

        Args:
            operation: Redis operation function to execute
            *args: Arguments to pass to the operation
            max_retries: Maximum number of retry attempts (default: 2)
            **kwargs: Keyword arguments to pass to the operation

        Returns:
            Result of the operation

        Raises:
            RuntimeError: If operation fails after all retries
        """
        import redis

        for attempt in range(max_retries + 1):
            try:
                return operation(*args, **kwargs)
            except (redis.ConnectionError, ConnectionError, BrokenPipeError) as e:
                if attempt < max_retries:
                    logger.warning(
                        f"⚠️  Redis connection error (attempt {attempt + 1}/{max_retries + 1}): {e}. Retrying..."
                    )
                    # Reconnect by creating new client from pool
                    try:
                        self._redis_client = redis.Redis(
                            connection_pool=self._redis_pool
                        )
                        self._redis_client.ping()
                        logger.info("✅ Redis reconnection successful")
                    except Exception as reconnect_error:
                        logger.error(f"❌ Redis reconnection failed: {reconnect_error}")
                        if attempt == max_retries:
                            raise RuntimeError(
                                f"Redis operation failed after {max_retries + 1} attempts: {e}"
                            )
                else:
                    logger.error(
                        f"❌ CRITICAL: Redis operation failed after {max_retries + 1} attempts: {e}"
                    )
                    raise RuntimeError(
                        f"Redis connection failed: {e}. Check Redis connectivity."
                    )
            except Exception as e:
                # Other errors - don't retry
                logger.error(
                    f"❌ CRITICAL: Redis operation failed with non-connection error: {e}"
                )
                raise RuntimeError(f"Redis operation failed: {e}")

    def get_conversation_history(
        self, channel_id: str, thread_ts: Optional[str], max_turns: int = 5
    ) -> List[ConversationTurn]:
        """Get conversation history for a thread.

        Args:
            channel_id: Slack channel ID
            thread_ts: Thread timestamp (None for DMs)
            max_turns: Maximum number of turns to retrieve

        Returns:
            List of conversation turns (most recent first)
        """
        thread_key = self._get_thread_key(channel_id, thread_ts)

        if self.storage_backend == "redis" and self._redis_client:

            def _redis_get_history():
                """Inner function for retry wrapper."""
                self._redis_client.ping()  # Health check
                history_json = self._redis_client.get(thread_key)
                if history_json:
                    history_data = json.loads(history_json)
                    turns = [
                        ConversationTurn(**turn) for turn in history_data[-max_turns:]
                    ]
                    logger.info(
                        f"✅ Retrieved {len(turns)} turns from Redis: {thread_key}"
                    )
                    return turns
                else:
                    logger.info(f"⚠️  No history found in Redis for key: {thread_key}")
                    return []

            # Use retry wrapper to handle connection errors
            return self._execute_with_retry(_redis_get_history)
        else:
            # In-memory storage
            if thread_key in self._memory_storage:
                logger.info(
                    f"✅ Retrieved {len(self._memory_storage[thread_key][-max_turns:])} turns from memory: {thread_key}"
                )
                return self._memory_storage[thread_key][-max_turns:]
            else:
                logger.info(f"⚠️  No history found in memory for key: {thread_key}")
                return []

    def add_conversation_turn(
        self,
        channel_id: str,
        thread_ts: Optional[str],
        question: str,
        answer: str,
        search_results: Optional[List[str]] = None,
    ):
        """Add a conversation turn to history.

        Args:
            channel_id: Slack channel ID
            thread_ts: Thread timestamp (None for DMs)
            question: User's question
            answer: Bot's answer
            search_results: List of search result titles
        """
        thread_key = self._get_thread_key(channel_id, thread_ts)
        turn = ConversationTurn(
            question=question,
            answer=answer,
            timestamp=time.time(),
            search_results=search_results,
        )

        if self.storage_backend == "redis" and self._redis_client:

            def _redis_save_turn():
                """Inner function for retry wrapper."""
                self._redis_client.ping()  # Health check

                # Get existing history
                history_json = self._redis_client.get(thread_key)
                if history_json:
                    history_data = json.loads(history_json)
                else:
                    history_data = []

                # Append new turn
                history_data.append(asdict(turn))

                # Keep only last 10 turns
                history_data = history_data[-10:]

                # Save back to Redis with TTL
                self._redis_client.setex(
                    thread_key, self._context_ttl, json.dumps(history_data)
                )

                logger.info(
                    f"✅ Saved conversation turn to Redis: {thread_key} (total turns: {len(history_data)}, TTL: {self._context_ttl}s)"
                )

            # Use retry wrapper to handle connection errors
            self._execute_with_retry(_redis_save_turn)
        else:
            # In-memory storage
            if thread_key not in self._memory_storage:
                self._memory_storage[thread_key] = []

            self._memory_storage[thread_key].append(turn)

            # Keep only last 10 turns
            self._memory_storage[thread_key] = self._memory_storage[thread_key][-10:]


class QueryUnderstandingService:
    """Extracts context and intent from user queries."""

    # Common project patterns
    PROJECT_PATTERNS = [
        r"\b([A-Z]{2,6})-\d+\b",  # Jira ticket format (e.g., PROJ-123)
        r"\b([A-Z]{2,6})\s+project\b",  # "PROJ project"
        r"\bproject\s+([A-Z]{2,6})(?:\s|$)",  # "project PROJ" (must be followed by space or end)
    ]

    # Common English words to exclude from project extraction
    EXCLUDED_WORDS = {
        "FOR",
        "THE",
        "AND",
        "ARE",
        "WAS",
        "NOT",
        "BUT",
        "CAN",
        "WILL",
        "FROM",
        "WITH",
        "ABOUT",
    }

    # Time range patterns
    TIME_PATTERNS = {
        r"\b(?:today|now)\b": 1,
        r"\byesterday\b": 2,
        r"\bthis\s+week\b": 7,
        r"\blast\s+week\b": 14,
        r"\bpast\s+week\b": 7,
        r"\bthis\s+month\b": 30,
        r"\blast\s+month\b": 60,
        r"\bpast\s+month\b": 30,
        r"\bthis\s+quarter\b": 90,
        r"\blast\s+(\d+)\s+days?\b": lambda m: int(m.group(1)),
        r"\bpast\s+(\d+)\s+days?\b": lambda m: int(m.group(1)),
    }

    # Follow-up indicators
    FOLLOW_UP_PATTERNS = [
        r"\b(?:what|how)\s+about\b",
        r"\b(?:and|also)\b",
        r"\btell\s+me\s+more\b",
        r"\bwhat\s+else\b",
        r"\bcan\s+you\s+(?:explain|elaborate)\b",
        r"\b(?:that|this|it)\b",  # Pronouns referring to previous context
    ]

    # Verbosity hint patterns for natural language detection
    VERBOSITY_PATTERNS = {
        "brief": [
            r"\bbrief\b",
            r"\bquick\b",
            r"\btldr\b",
            r"\btl;dr\b",
            r"\bsummary\b",
            r"\bsummarize\b",
            r"\bconcise\b",
            r"\bshort\b",
            r"\bin a nutshell\b",
            r"\bbottom line\b",
        ],
        "detailed": [
            r"\bdetail\b",
            r"\bdetailed\b",
            r"\bthorough\b",
            r"\bthoroughly\b",
            r"\bcomprehensive\b",
            r"\bexplain\b",
            r"\bin-?depth\b",
            r"\belaborate\b",
            r"\bwhy\b",  # "why" questions often need more detail
            r"\bhow does .+ work\b",  # "how does X work" implies detailed explanation
        ],
    }

    def understand_query(
        self, query: str, conversation_history: List[ConversationTurn]
    ) -> QueryContext:
        """Extract context and intent from query.

        Args:
            query: User's query
            conversation_history: Previous conversation turns

        Returns:
            QueryContext with extracted information
        """
        context = QueryContext(original_query=query)

        # Extract optional parameters (--detail, --project) and clean query
        cleaned_query, extracted_params = self._extract_parameters(query)

        # Store extracted parameters in context
        if "detail_level" in extracted_params:
            context.detail_level = extracted_params["detail_level"]
        if "project" in extracted_params:
            # Override with explicit --project parameter if provided
            context.project_key = extracted_params["project"]

        # Detect natural language verbosity hints (only if --detail not explicitly set)
        if "detail_level" not in extracted_params:
            detected_verbosity = self._detect_verbosity_hint(cleaned_query)
            if detected_verbosity:
                context.detail_level = detected_verbosity

        # Use cleaned query (without parameters) for further extraction
        query_for_extraction = cleaned_query

        # Extract project/ticket reference (only if not already set by --project)
        if not context.project_key:
            context.project_key, context.jira_ticket = self._extract_project_info(
                query_for_extraction
            )
        else:
            # Still extract ticket if present
            _, context.jira_ticket = self._extract_project_info(query_for_extraction)

        # Extract time range
        context.time_range_days, context.time_description = self._extract_time_range(
            query_for_extraction
        )

        # Check if follow-up question
        context.is_follow_up = self._is_follow_up(
            query_for_extraction, conversation_history
        )

        # Extract keywords
        context.keywords = self._extract_keywords(query_for_extraction)

        return context

    def _extract_project_info(self, query: str) -> Tuple[Optional[str], Optional[str]]:
        """Extract project key and Jira ticket from query."""
        for pattern in self.PROJECT_PATTERNS:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                project_ref = match.group(1).upper()

                # Skip common English words
                if project_ref in self.EXCLUDED_WORDS:
                    continue

                # Check if it's a full Jira ticket
                full_match = re.search(r"\b([A-Z]{2,6}-\d+)\b", query)
                if full_match:
                    return project_ref, full_match.group(1)
                return project_ref, None
        return None, None

    def _extract_time_range(self, query: str) -> Tuple[Optional[int], Optional[str]]:
        """Extract time range from query."""
        for pattern, days in self.TIME_PATTERNS.items():
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                if callable(days):
                    days_value = days(match)
                else:
                    days_value = days
                return days_value, match.group(0)
        return None, None

    def _is_follow_up(
        self, query: str, conversation_history: List[ConversationTurn]
    ) -> bool:
        """Determine if query is a follow-up question."""
        if not conversation_history:
            return False

        # Check for follow-up indicators
        for pattern in self.FOLLOW_UP_PATTERNS:
            if re.search(pattern, query, re.IGNORECASE):
                return True

        # Short queries are likely follow-ups
        if len(query.split()) <= 3:
            return True

        return False

    def _detect_verbosity_hint(self, query: str) -> Optional[str]:
        """Detect natural language hints about desired verbosity level.

        Args:
            query: User's query

        Returns:
            'brief' or 'detailed' if hints detected, None otherwise
        """
        query_lower = query.lower()

        # Check for "brief" hints
        for pattern in self.VERBOSITY_PATTERNS["brief"]:
            if re.search(pattern, query_lower, re.IGNORECASE):
                return "brief"

        # Check for "detailed" hints
        for pattern in self.VERBOSITY_PATTERNS["detailed"]:
            if re.search(pattern, query_lower, re.IGNORECASE):
                return "detailed"

        # No hints detected - let AI use adaptive "normal" behavior
        return None

    def _extract_parameters(self, query: str) -> Tuple[str, Dict[str, str]]:
        """Extract optional parameters from query (--detail, --project).

        Args:
            query: User's query potentially with parameters

        Returns:
            Tuple of (cleaned_query, extracted_params_dict)

        Examples:
            "what's the status --detail=normal" -> ("what's the status", {"detail_level": "normal"})
            "searchspring --project=SUBS" -> ("searchspring", {"project": "SUBS"})
            "what's happening --detail=brief --project=BC" -> ("what's happening", {"detail_level": "brief", "project": "BC"})
        """
        params = {}
        cleaned_query = query

        # Valid detail levels
        valid_detail_levels = {"brief", "normal", "detailed", "slack"}

        # Extract --detail=VALUE or --detail VALUE
        detail_patterns = [r"--detail[=\s]+([a-z]+)", r"--detail-level[=\s]+([a-z]+)"]
        for pattern in detail_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                detail_value = match.group(1).lower()
                if detail_value in valid_detail_levels:
                    params["detail_level"] = detail_value
                    # Remove parameter from query
                    cleaned_query = re.sub(
                        pattern, "", cleaned_query, flags=re.IGNORECASE
                    ).strip()
                    break

        # Extract --project=VALUE or --project VALUE
        project_patterns = [r"--project[=\s]+([A-Z]{2,6})", r"--proj[=\s]+([A-Z]{2,6})"]
        for pattern in project_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                params["project"] = match.group(1).upper()
                # Remove parameter from query
                cleaned_query = re.sub(
                    pattern, "", cleaned_query, flags=re.IGNORECASE
                ).strip()
                break

        # Clean up any double spaces
        cleaned_query = re.sub(r"\s+", " ", cleaned_query).strip()

        return cleaned_query, params

    def _extract_keywords(self, query: str) -> List[str]:
        """Extract important keywords from query."""
        # Remove common stop words
        stop_words = {
            "what",
            "when",
            "where",
            "who",
            "why",
            "how",
            "is",
            "are",
            "was",
            "were",
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
            "by",
            "from",
            "about",
            "can",
            "you",
            "tell",
            "me",
        }

        # Extract words
        words = re.findall(r"\b\w+\b", query.lower())

        # Filter stop words and short words
        keywords = [word for word in words if word not in stop_words and len(word) > 2]

        return keywords[:10]  # Limit to 10 keywords


class RateLimiter:
    """Simple in-memory rate limiter for Slack users."""

    def __init__(
        self, soft_limit: int = 15, hard_limit: int = 30, window_hours: int = 1
    ):
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

        # Conversation context manager (tries Redis, falls back to memory)
        self.conversation_manager = ConversationContextManager(storage_backend="redis")

        # Query understanding service
        self.query_understanding = QueryUnderstandingService()

        # Search context storage for feedback: message_ts -> search_metadata
        self._search_context: Dict[str, Dict[str, Any]] = {}

        logger.info("SlackChatService initialized with conversation context")

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
        thread_ts: Optional[str] = None,
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
            is_allowed, is_soft_exceeded, remaining = (
                self.rate_limiter.check_rate_limit(user_id)
            )

            if not is_allowed:
                # Hard limit exceeded
                self.slack_client.chat_postMessage(
                    channel=channel_id,
                    thread_ts=thread_ts,
                    text="🚫 Rate limit exceeded. You've used all 30 questions this hour. Please wait a bit and try again.",
                )
                return

            # Get conversation history
            conversation_history = self.conversation_manager.get_conversation_history(
                channel_id=channel_id, thread_ts=thread_ts, max_turns=5
            )

            # Debug logging for conversation history
            logger.info(
                f"💬 Conversation history lookup: channel={channel_id}, thread_ts={thread_ts}, found {len(conversation_history)} turns"
            )
            if conversation_history:
                for i, turn in enumerate(conversation_history):
                    logger.info(
                        f"  Turn {i+1}: Q='{turn.question[:50]}...', A='{turn.answer[:50]}...'"
                    )

            # Understand the query (extract project, time range, keywords, etc.)
            query_context = self.query_understanding.understand_query(
                query=question, conversation_history=conversation_history
            )

            logger.info(
                f"🧠 Query context: project={query_context.project_key}, "
                f"time={query_context.time_description}, "
                f"detail_level={query_context.detail_level or 'normal (default)'}, "
                f"follow_up={query_context.is_follow_up}, "
                f"keywords={query_context.keywords[:3]}"
            )

            # Check cache first (only for non-follow-up questions)
            if not query_context.is_follow_up:
                cached_response = self._get_cached_response(question, user_id)
                if cached_response:
                    # Post cached response
                    self.slack_client.chat_postMessage(
                        channel=channel_id,
                        thread_ts=thread_ts,
                        text=f"{cached_response}\n\n_[Cached response]_",
                    )
                    return

            # Map Slack user to app user for permission filtering
            app_user_id = self._map_slack_user_to_app_user(user_id)

            # Build search message with context awareness
            search_msg = self._build_search_message(question, query_context)

            # Post "searching" message
            searching_msg = self.slack_client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,  # This ensures we reply in the correct thread
                text=search_msg,
            )

            search_ts = searching_msg["ts"]

            # CRITICAL: Ensure we use the correct thread_ts for conversation context
            # If thread_ts was None, the bot's message creates a new thread
            # We need to use the bot's message ts as the thread parent for future lookups
            # BUT - we should have already received the correct thread_ts from slack_bot.py
            # This is a safety check to ensure consistency
            if thread_ts is None:
                logger.warning(
                    f"⚠️  thread_ts was None when posting message. This shouldn't happen!"
                )
                thread_ts = search_ts  # Fallback: use bot's message as thread parent

            # Add soft limit warning if needed
            if is_soft_exceeded:
                warning_text = f"\n\n⚠️ _You have {remaining} questions remaining this hour (soft limit: 15, hard limit: 30)_"
            else:
                warning_text = ""

            # Determine time range for search (use extracted time or default 90 days)
            days_back = query_context.time_range_days or 90

            # Determine detail level (use extracted or default to "normal")
            detail_level = query_context.detail_level or "normal"

            # Convert conversation history to format expected by summarizer
            conversation_history_for_ai = []
            if conversation_history:
                for turn in conversation_history:
                    conversation_history_for_ai.append(
                        {"role": "user", "content": turn.question}
                    )
                    conversation_history_for_ai.append(
                        {"role": "assistant", "content": turn.answer}
                    )

            # Perform context search with extracted context and conversation history
            results = await self.context_search.search(
                query=question,
                days_back=days_back,
                user_id=app_user_id,
                detail_level=detail_level,  # Use extracted detail level or default to normal
                project=query_context.project_key,  # Use extracted or auto-detected project
                conversation_history=(
                    conversation_history_for_ai if conversation_history else None
                ),
            )

            if not results.results:
                # No results found
                self.slack_client.chat_update(
                    channel=channel_id,
                    ts=search_ts,
                    text=f"🔍 No results found for: *{question}*\n\nTry different keywords or expanding the time window.{warning_text}",
                )
                return

            # Use the AI-generated summary from ContextSearchService (already uses conversational prompts)
            if results.summary:
                # Format summary with citations
                formatted_response = self._format_response(results.summary, results)

                self.slack_client.chat_update(
                    channel=channel_id,
                    ts=search_ts,
                    text=formatted_response + warning_text,
                )

                # Add feedback reactions (👍/👎) to message
                self._add_feedback_reactions(channel_id, search_ts)

                # Store search context for feedback handling
                self._search_context[search_ts] = {
                    "query": question,
                    "user_id": user_id,
                    "app_user_id": app_user_id,
                    "slack_user_id": user_id,
                    "result_count": len(results.results),
                    "result_sources": list(set([r.source for r in results.results])),
                    "top_result_source": (
                        results.results[0].source if results.results else None
                    ),
                    "detail_level": detail_level,
                    "project_key": query_context.project_key,
                    "timestamp": time.time(),
                }

                # Cache the response (only for non-follow-up questions)
                if query_context and not query_context.is_follow_up:
                    self._cache_response(question, user_id, formatted_response)

                # Save conversation turn
                result_titles = [
                    r.title for r in results.results[:5]
                ]  # Top 5 result titles
                self.conversation_manager.add_conversation_turn(
                    channel_id=channel_id,
                    thread_ts=thread_ts,
                    question=question,
                    answer=results.summary,  # Store raw summary
                    search_results=result_titles,
                )

                logger.info(
                    f"💬 Conversation turn saved for thread {thread_ts or 'DM'}"
                )
            else:
                # Fallback: Stream AI response if no summary (shouldn't happen but safety net)
                await self._stream_response(
                    channel_id=channel_id,
                    message_ts=search_ts,
                    query=question,
                    results=results,
                    warning_text=warning_text,
                    user_id=user_id,
                    thread_ts=thread_ts,
                    conversation_history=conversation_history,
                    query_context=query_context,
                )

        except Exception as e:
            logger.error(f"Error handling question: {e}")
            self.slack_client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                text=f"❌ Sorry, I encountered an error: {str(e)}\n\nPlease try again or contact support.",
            )

    def _build_search_message(self, question: str, query_context: QueryContext) -> str:
        """Build a context-aware search message.

        Args:
            question: User's question
            query_context: Extracted query context

        Returns:
            Formatted search message
        """
        msg_parts = ["🔍 Searching for: *{question}*"]

        if query_context.is_follow_up:
            msg_parts.append("_(following up on previous conversation)_")

        context_hints = []
        if query_context.project_key:
            context_hints.append(f"project: {query_context.project_key}")
        if query_context.time_description:
            context_hints.append(f"time: {query_context.time_description}")

        if context_hints:
            msg_parts.append(f"Context: {', '.join(context_hints)}")

        msg_parts.append("_This may take a moment..._")

        return "\n".join(msg_parts).format(question=question)

    async def _stream_response(
        self,
        channel_id: str,
        message_ts: str,
        query: str,
        results: Any,
        warning_text: str,
        user_id: str,
        thread_ts: Optional[str] = None,
        conversation_history: Optional[List[ConversationTurn]] = None,
        query_context: Optional[QueryContext] = None,
    ) -> None:
        """Stream AI response with progressive updates.

        Args:
            channel_id: Slack channel ID
            message_ts: Message timestamp to update
            query: Original query
            results: Context search results
            warning_text: Rate limit warning text
            user_id: Slack user ID for caching
            thread_ts: Thread timestamp (for saving conversation)
            conversation_history: Previous conversation turns
            query_context: Extracted query context
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

            # Build conversation history for AI (if available)
            conversation_context = ""
            if conversation_history:
                history_lines = []
                for turn in conversation_history[-3:]:  # Last 3 turns
                    history_lines.append(f"User: {turn.question}")
                    history_lines.append(
                        f"Assistant: {turn.answer[:200]}..."
                    )  # Truncate answer
                conversation_context = "\n\nCONVERSATION HISTORY:\n" + "\n".join(
                    history_lines
                )

            # Build system prompt with conversation awareness
            system_message = (
                "You are a helpful AI assistant that answers questions based on context from "
                "Slack messages, meeting transcripts, Jira tickets, GitHub PRs, and Notion pages. "
                "Provide concise, accurate answers with inline citations [1], [2], etc. "
                "Keep responses under 250 words. Be direct and factual. "
                "If this is a follow-up question, use the conversation history to provide context-aware answers."
            )

            # Build user prompt with conversation history
            user_prompt = f"""Query: "{query}"{conversation_context}

SEARCH RESULTS:
{context_text}

Answer the query based on the search results above. Include inline citations [1], [2], etc. to reference sources.
Keep it concise (under 250 words) and focus on answering the question directly."""

            # Stream response from OpenAI
            full_response = ""
            update_interval = 2  # Update every 2 seconds
            last_update = time.time()

            # Determine if streaming is supported (o1 and gpt-5 models don't support streaming for unverified orgs)
            supports_streaming = not (
                settings.ai.model.startswith("o1")
                or settings.ai.model.startswith("gpt-5")
            )

            # Use configured model
            api_params = {
                "model": settings.ai.model,
                "messages": [
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_prompt},
                ],
            }

            # Only add stream parameter and temperature for models that support it
            if supports_streaming:
                api_params["stream"] = True
                api_params["temperature"] = 0.3

            response = await self.openai_client.chat.completions.create(**api_params)

            if supports_streaming:
                # Streaming: iterate over chunks
                async for chunk in response:
                    if chunk.choices[0].delta.content:
                        full_response += chunk.choices[0].delta.content

                        # Update message every 2 seconds
                        now = time.time()
                        if (now - last_update) >= update_interval:
                            # Format with citations
                            formatted_response = self._format_response(
                                full_response, results
                            )

                            self.slack_client.chat_update(
                                channel=channel_id,
                                ts=message_ts,
                                text=formatted_response
                                + "\n\n_Generating..._"
                                + warning_text,
                            )
                            last_update = now
            else:
                # Non-streaming: get complete response at once
                full_response = response.choices[0].message.content

            # Final update with complete response
            formatted_response = self._format_response(full_response, results)

            self.slack_client.chat_update(
                channel=channel_id,
                ts=message_ts,
                text=formatted_response + warning_text,
            )

            # Cache the response (only for non-follow-up questions)
            if query_context and not query_context.is_follow_up:
                self._cache_response(query, user_id, formatted_response)

            # Save conversation turn
            result_titles = [
                r.title for r in results.results[:5]
            ]  # Top 5 result titles
            self.conversation_manager.add_conversation_turn(
                channel_id=channel_id,
                thread_ts=thread_ts,
                question=query,
                answer=full_response,  # Store raw answer (without citations)
                search_results=result_titles,
            )

            logger.info(f"💬 Conversation turn saved for thread {thread_ts or 'DM'}")

        except Exception as e:
            logger.error(f"Error streaming response: {e}")
            self.slack_client.chat_update(
                channel=channel_id,
                ts=message_ts,
                text=f"❌ Error generating response: {str(e)}",
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

        citations_used = set(re.findall(r"\[(\d+)\]", ai_response))

        # Build sources section
        if citations_used and results.citations:
            formatted += "\n\n*Sources:*"
            for citation in results.citations:
                if str(citation.id) in citations_used:
                    source_emoji = {
                        "slack": "💬",
                        "fireflies": "🎙️",
                        "jira": "📋",
                        "github": "💻",
                        "notion": "📝",
                    }.get(citation.source, "📄")

                    source_line = f"\n[{citation.id}] {source_emoji} {citation.title}"
                    if citation.url:
                        source_line += f" - <{citation.url}|View>"

                    formatted += source_line

        return formatted

    def _add_feedback_reactions(self, channel_id: str, message_ts: str):
        """Add thumbs up/down reactions to a message for feedback.

        Args:
            channel_id: Slack channel ID
            message_ts: Message timestamp
        """
        try:
            # Add 👍 reaction
            self.slack_client.reactions_add(
                channel=channel_id, timestamp=message_ts, name="+1"
            )

            # Add 👎 reaction
            self.slack_client.reactions_add(
                channel=channel_id, timestamp=message_ts, name="-1"
            )

            logger.debug(f"Added feedback reactions to message {message_ts}")

        except Exception as e:
            logger.error(f"Error adding reactions: {e}")

    async def handle_reaction_event(
        self, user_id: str, reaction: str, channel_id: str, message_ts: str
    ):
        """Handle user reaction to a search response.

        Args:
            user_id: Slack user ID who reacted
            reaction: Reaction name (e.g., '+1', '-1')
            channel_id: Slack channel ID
            message_ts: Message timestamp
        """
        try:
            # Only handle thumbs up/down reactions
            if reaction not in ["+1", "-1"]:
                return

            # Get search context for this message
            search_context = self._search_context.get(message_ts)
            if not search_context:
                logger.warning(f"No search context found for message {message_ts}")
                return

            # Convert reaction to rating (2 = thumbs up, 1 = thumbs down)
            rating = 2 if reaction == "+1" else 1

            # Record feedback
            from src.services.feedback_service import FeedbackService

            feedback_service = FeedbackService()
            feedback_id = await feedback_service.record_feedback(
                query=search_context["query"],
                rating=rating,
                user_id=search_context.get("app_user_id"),
                slack_user_id=user_id,
                result_count=search_context.get("result_count"),
                result_sources=search_context.get("result_sources"),
                top_result_source=search_context.get("top_result_source"),
                detail_level=search_context.get("detail_level"),
                project_key=search_context.get("project_key"),
            )

            rating_emoji = "👍" if rating == 2 else "👎"
            logger.info(
                f"Recorded feedback {rating_emoji} from user {user_id} (feedback_id={feedback_id})"
            )

            # TODO: Add structured follow-up for negative feedback (next task)

        except Exception as e:
            logger.error(f"Error handling reaction event: {e}")

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
                user = (
                    session.query(User)
                    .filter(User.slack_user_id == slack_user_id)
                    .first()
                )
                if user:
                    logger.info(
                        f"Mapped Slack user {slack_user_id} to app user {user.id}"
                    )
                    return user.id
                else:
                    logger.info(f"No app user found for Slack user {slack_user_id}")
                    return None
            finally:
                session.close()

        except Exception as e:
            logger.error(f"Error mapping Slack user to app user: {e}")
            return None
