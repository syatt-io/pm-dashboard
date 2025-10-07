"""Context search service for finding information across all integrated sources."""

import logging
import re
import hashlib
from typing import List, Dict, Any, Optional, Set, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import numpy as np

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
        self._embedding_cache = {}  # Cache embeddings: hash(text) -> (embedding, timestamp)
        self._embedding_cache_ttl = 3600  # 1 hour cache TTL

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

    def _get_text_hash(self, text: str) -> str:
        """Generate a hash for text to use as cache key."""
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    def _get_embedding(self, text: str) -> Optional[List[float]]:
        """Get embedding for text with caching.

        Args:
            text: Text to embed

        Returns:
            Embedding vector or None if error
        """
        if not text or not text.strip():
            return None

        # Truncate long text to ~8000 chars (OpenAI limit is ~8191 tokens)
        text = text[:8000]

        # Check cache
        text_hash = self._get_text_hash(text)
        if text_hash in self._embedding_cache:
            cached_embedding, cached_time = self._embedding_cache[text_hash]
            # Check if cache is still valid
            if (datetime.now() - cached_time).total_seconds() < self._embedding_cache_ttl:
                return cached_embedding
            else:
                # Remove stale cache entry
                del self._embedding_cache[text_hash]

        try:
            from openai import OpenAI
            from config.settings import settings

            client = OpenAI(api_key=settings.ai.api_key)

            response = client.embeddings.create(
                model="text-embedding-3-small",  # Fast, cheap, good quality
                input=text
            )

            embedding = response.data[0].embedding

            # Cache the embedding
            self._embedding_cache[text_hash] = (embedding, datetime.now())

            return embedding

        except Exception as e:
            self.logger.error(f"Error getting embedding: {e}")
            return None

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Similarity score between -1 and 1 (higher is more similar)
        """
        try:
            v1 = np.array(vec1)
            v2 = np.array(vec2)

            dot_product = np.dot(v1, v2)
            norm1 = np.linalg.norm(v1)
            norm2 = np.linalg.norm(v2)

            if norm1 == 0 or norm2 == 0:
                return 0.0

            return float(dot_product / (norm1 * norm2))

        except Exception as e:
            self.logger.error(f"Error calculating cosine similarity: {e}")
            return 0.0

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into words for BM25.

        Args:
            text: Text to tokenize

        Returns:
            List of lowercase tokens (words with length > 2)
        """
        import re
        # Lowercase and split on non-alphanumeric characters, filter short words
        return [word for word in re.findall(r'\b\w+\b', text.lower()) if len(word) > 2]

    def _bm25_score(
        self,
        query_tokens: List[str],
        doc_tokens: List[str],
        avg_doc_length: float,
        total_docs: int,
        term_doc_freq: Dict[str, int],
        k1: float = 1.5,
        b: float = 0.75
    ) -> float:
        """Calculate BM25 score for a document given a query.

        BM25 is a probabilistic retrieval function that ranks documents based on
        the query terms appearing in each document.

        Args:
            query_tokens: Tokenized query terms
            doc_tokens: Tokenized document terms
            avg_doc_length: Average length of all documents in the corpus
            total_docs: Total number of documents in the corpus
            term_doc_freq: Dictionary mapping terms to document frequency
            k1: Term frequency saturation parameter (default: 1.5)
            b: Length normalization parameter (default: 0.75)

        Returns:
            BM25 score (higher is better)
        """
        score = 0.0
        doc_length = len(doc_tokens)

        # Count term frequencies in document
        doc_term_freq = {}
        for token in doc_tokens:
            doc_term_freq[token] = doc_term_freq.get(token, 0) + 1

        # Calculate IDF and term scores for each query term
        for query_term in query_tokens:
            if query_term not in doc_term_freq:
                continue

            # Term frequency in document
            tf = doc_term_freq[query_term]

            # Document frequency (how many docs contain this term)
            df = term_doc_freq.get(query_term, 0)

            # IDF: Inverse document frequency
            idf = np.log((total_docs - df + 0.5) / (df + 0.5) + 1.0)

            # BM25 formula for this term
            numerator = tf * (k1 + 1)
            denominator = tf + k1 * (1 - b + b * (doc_length / avg_doc_length))

            score += idf * (numerator / denominator)

        return score

    def _reciprocal_rank_fusion(
        self,
        rankings: List[List[Tuple[Any, float]]],
        k: int = 60
    ) -> List[Tuple[Any, float]]:
        """Combine multiple ranking lists using Reciprocal Rank Fusion (RRF).

        RRF is a simple but effective method for combining multiple rankings.
        It assigns a score to each item based on its rank in each list.

        Args:
            rankings: List of ranking lists, each is list of (item, score) tuples
            k: Constant for RRF formula (default: 60, as in original paper)

        Returns:
            Combined ranking as list of (item, rrf_score) tuples, sorted descending
        """
        # Collect all unique items
        all_items = set()
        for ranking in rankings:
            for item, _ in ranking:
                all_items.add(item)

        # Calculate RRF score for each item
        rrf_scores = {}
        for item in all_items:
            rrf_score = 0.0

            # For each ranking list
            for ranking in rankings:
                # Find rank of item in this list (1-indexed)
                rank = None
                for i, (ranked_item, _) in enumerate(ranking, start=1):
                    if ranked_item == item:
                        rank = i
                        break

                # Add RRF score: 1 / (k + rank)
                if rank is not None:
                    rrf_score += 1.0 / (k + rank)

            rrf_scores[item] = rrf_score

        # Sort by RRF score descending
        sorted_items = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

        return sorted_items

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

    def _score_text_match_semantic(
        self,
        text: str,
        query: str,
        project_keywords: Set[str],
        topic_keywords: Set[str],
        debug: bool = False
    ) -> Tuple[int, float, float, bool]:
        """Hybrid scoring: keyword matching for project, semantic similarity for topic.

        Args:
            text: Text to score
            query: Original query string (for embedding)
            project_keywords: Project-related keywords
            topic_keywords: Topic keywords (used to build topic query for embedding)
            debug: Enable debug logging for scoring

        Returns:
            Tuple of (project_matches, semantic_similarity, relevance_score, passes_threshold)
        """
        text_lower = text.lower()
        text_preview = text[:200] + "..." if len(text) > 200 else text

        # 1. Project keyword matching (optional bonus)
        project_matches = sum(1 for kw in project_keywords if kw in text_lower)

        # 2. Semantic similarity for topic (understands meaning)
        # Build topic query from topic keywords
        topic_query = ' '.join(topic_keywords) if topic_keywords else query

        # Get embeddings
        query_embedding = self._get_embedding(topic_query)
        text_embedding = self._get_embedding(text)

        if query_embedding is None or text_embedding is None:
            # Fallback to keyword matching if embedding fails
            self.logger.warning("Embedding failed, falling back to keyword matching")
            topic_matches = sum(1 for kw in topic_keywords if kw in text_lower)

            # If no matches at all, reject
            if topic_matches == 0 and project_matches == 0:
                if debug:
                    self.logger.info(f"❌ REJECTED (no keywords): {text_preview}")
                return project_matches, 0.0, 0.0, False

            # Keyword-based scoring as fallback
            total_keywords = len(project_keywords) + len(topic_keywords) * 3
            weighted_matches = project_matches + (topic_matches * 3)
            relevance_score = weighted_matches / total_keywords if total_keywords > 0 else 0.0
            passes_threshold = relevance_score >= 0.25  # Lowered from 0.3

            if debug:
                self.logger.info(
                    f"{'✅ PASSED' if passes_threshold else '❌ REJECTED'} (keyword fallback): "
                    f"score={relevance_score:.3f}, proj={project_matches}, topic={topic_matches} | {text_preview}"
                )

            return project_matches, 0.0, relevance_score, passes_threshold

        # Calculate semantic similarity (0-1, where 1 is identical)
        semantic_similarity = self._cosine_similarity(query_embedding, text_embedding)

        # Normalize to 0-1 range (cosine similarity is -1 to 1, but usually 0-1 for text)
        semantic_similarity = max(0.0, semantic_similarity)

        # 3. Calculate BM25 score for keyword quality
        # Tokenize query and text for BM25
        query_tokens = self._tokenize(topic_query)
        doc_tokens = self._tokenize(text)

        # Use approximate corpus statistics (good enough for relative ranking)
        avg_doc_length = 500.0  # Approximate average document length
        total_docs = 1000  # Approximate corpus size

        # Estimate term document frequency (how many docs contain each term)
        # For simplicity, assume common terms appear in 10% of docs
        term_doc_freq = {token: 100 for token in set(query_tokens + doc_tokens)}

        # Calculate BM25 score
        bm25_raw = self._bm25_score(
            query_tokens=query_tokens,
            doc_tokens=doc_tokens,
            avg_doc_length=avg_doc_length,
            total_docs=total_docs,
            term_doc_freq=term_doc_freq
        )

        # Normalize BM25 score to 0-1 range (typical BM25 scores are 0-10+)
        # Using sigmoid-like normalization: score / (score + 5)
        bm25_score = bm25_raw / (bm25_raw + 5.0) if bm25_raw > 0 else 0.0

        # 4. Combined scoring with triple signals
        # Project match: optional bonus - weight 0.10 (reduced from 0.15)
        # Semantic similarity: continuous 0-1 - weight 0.65 (increased from 0.60)
        # BM25 keyword quality: continuous 0-1 - weight 0.25
        project_signal = 0.10 if project_matches > 0 else 0.0
        semantic_signal = 0.65 * semantic_similarity
        bm25_signal = 0.25 * bm25_score

        relevance_score = project_signal + semantic_signal + bm25_signal

        # LOWERED THRESHOLDS: Passes if semantic >= 0.20 OR BM25 >= 0.20 OR (project match AND semantic >= 0.15)
        # This allows semantic matching to work even without project keywords
        passes_threshold = (
            semantic_similarity >= 0.20 or  # Lowered from 0.30 - allows more semantic matches
            bm25_score >= 0.20 or  # Lowered from 0.25 - allows more keyword matches
            (project_matches > 0 and semantic_similarity >= 0.15)  # Project bonus with lower threshold
        )

        if debug:
            self.logger.info(
                f"{'✅ PASSED' if passes_threshold else '❌ REJECTED'}: "
                f"score={relevance_score:.3f} (sem={semantic_similarity:.3f}, bm25={bm25_score:.3f}, proj={project_matches}) | {text_preview}"
            )

        return project_matches, semantic_similarity, relevance_score, passes_threshold

    async def search(
        self,
        query: str,
        days_back: int = 90,
        sources: List[str] = None,
        user_id: Optional[int] = None,
        debug: bool = True  # Enable debug logging by default for now
    ) -> ContextSearchResults:
        """Search for context across all sources.

        Args:
            query: Search query/topic
            days_back: How many days back to search
            sources: List of sources to search ('slack', 'fireflies', 'jira', 'notion')
            user_id: User ID for accessing user-specific credentials
            debug: Enable debug logging for scoring

        Returns:
            ContextSearchResults with aggregated results
        """
        if sources is None:
            sources = ['slack', 'fireflies', 'jira', 'notion']

        # Detect project and expand query with keywords (two-tier: project + topic)
        detected_project, project_keywords, topic_keywords = self._detect_project_and_expand_query(query)

        self.logger.info(f"🔍 SEARCH DEBUG: query='{query}', project={detected_project}")
        self.logger.info(f"  Project keywords: {project_keywords}")
        self.logger.info(f"  Topic keywords: {topic_keywords}")

        all_results = []

        # Search each source with hybrid semantic + keyword matching
        if 'slack' in sources:
            slack_results = await self._search_slack(query, days_back, user_id, project_keywords, topic_keywords, debug)
            all_results.extend(slack_results)

        if 'fireflies' in sources:
            fireflies_results = await self._search_fireflies(query, days_back, user_id, project_keywords, topic_keywords, debug)
            all_results.extend(fireflies_results)

        if 'jira' in sources:
            jira_results = await self._search_jira(query, days_back, detected_project, project_keywords, topic_keywords, debug)
            all_results.extend(jira_results)

        if 'notion' in sources:
            notion_results = await self._search_notion(query, days_back, user_id, project_keywords, topic_keywords, debug)
            all_results.extend(notion_results)

        # Sort by relevance score first, then by date
        all_results.sort(key=lambda x: (x.relevance_score, x.date), reverse=True)

        # Build project context for AI summarization
        project_context = None
        if detected_project and project_keywords:
            project_context = {
                'project_key': detected_project,
                'keywords': list(project_keywords)
            }

        # Generate AI summary and insights with project context
        summary, key_people, timeline = await self._generate_insights(query, all_results, project_context)

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
    , debug: bool = False) -> List[SearchResult]:
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
    , debug: bool = False) -> List[SearchResult]:
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

                    # Score message with hybrid semantic matching
                    proj_matches, semantic_sim, relevance_score, passes = self._score_text_match_semantic(message_text, query, project_keywords, topic_keywords, debug)

                    # Skip messages that don't pass threshold
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

            self.logger.info(f"Found {len(results)} Slack messages via user token (semantic match)")
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
    , debug: bool = False) -> List[SearchResult]:
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

                        # Score message with hybrid semantic matching
                        proj_matches, semantic_sim, relevance_score, passes = self._score_text_match_semantic(message_text, query, project_keywords, topic_keywords, debug)

                        # Skip messages that don't pass threshold
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

            self.logger.info(f"Found {len(results)} Slack messages with semantic matching")
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
    , debug: bool = False) -> List[SearchResult]:
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

                # Search in transcript with hybrid semantic matching
                meeting_title = meeting.get('title', '')
                combined_text = f"{meeting_title} {transcript.transcript}"

                # Score with hybrid semantic matching (keywords for project, embeddings for topic)
                proj_matches, semantic_sim, relevance_score, passes = self._score_text_match_semantic(combined_text, query, project_keywords, topic_keywords, debug)

                # Skip meetings that don't pass threshold
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

            self.logger.info(f"Found {len(results)} Fireflies meetings with semantic matching")
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
    , debug: bool = False) -> List[SearchResult]:
        """Search Jira issues and comments with project filtering and two-tier matching."""
        if project_keywords is None:
            project_keywords = set()
        if topic_keywords is None:
            topic_keywords = set(query.lower().split())

        try:
            from src.integrations.jira_mcp import JiraMCPClient
            from config.settings import settings

            jira_client = JiraMCPClient(
                jira_url=settings.jira.url,
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

            # Search issues with comments expanded
            issues = await jira_client.search_issues(jql, max_results=50, expand_comments=True)

            results = []
            for issue in issues.get('issues', []):
                fields = issue.get('fields', {})

                # Parse updated date
                updated_str = fields.get('updated', '')
                updated_date = datetime.fromisoformat(updated_str.replace('Z', '+00:00')) if updated_str else datetime.now()

                # Create snippet from summary + description + comments
                summary = fields.get('summary', '')
                description = fields.get('description', '')

                # Extract and combine comment bodies
                comments = fields.get('comments', [])
                comment_text = ""
                if comments:
                    comment_bodies = []
                    for comment in comments[:10]:  # Limit to 10 most recent comments to avoid token explosion
                        body = comment.get('body', '')
                        if isinstance(body, dict):
                            # Handle ADF (Atlassian Document Format) - extract text content
                            body = self._extract_text_from_adf(body)
                        comment_bodies.append(body)
                    comment_text = " ".join(comment_bodies)

                combined_text = f"{summary} {description} {comment_text}"

                # Score with hybrid semantic matching
                proj_matches, semantic_sim, relevance_score, passes = self._score_text_match_semantic(combined_text, query, project_keywords, topic_keywords, debug)

                # Skip issues that don't pass threshold
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
            self.logger.info(f"Found {len(results)} Jira issues{project_msg} with semantic matching")
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
    , debug: bool = False) -> List[SearchResult]:
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

            # Calculate date filter (timezone-aware for Notion API)
            from datetime import timezone
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)

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

                # Score with hybrid semantic matching
                # For now, just use title since fetching full content requires separate API call
                proj_matches, semantic_sim, relevance_score, passes = self._score_text_match_semantic(title, query, project_keywords, topic_keywords, debug)

                # Skip pages that don't pass threshold
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

            self.logger.info(f"Found {len(results)} Notion pages with semantic matching")
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

    def _extract_text_from_adf(self, adf_content: Dict[str, Any]) -> str:
        """Extract plain text from Atlassian Document Format (ADF) JSON.

        Args:
            adf_content: ADF JSON structure

        Returns:
            Plain text extracted from ADF content
        """
        if not isinstance(adf_content, dict):
            return str(adf_content)

        text_parts = []

        # Handle different ADF node types
        node_type = adf_content.get('type', '')

        # Direct text nodes
        if node_type == 'text':
            text_parts.append(adf_content.get('text', ''))

        # Recurse into content array
        if 'content' in adf_content and isinstance(adf_content['content'], list):
            for child in adf_content['content']:
                text_parts.append(self._extract_text_from_adf(child))

        # Join with spaces and clean up
        text = ' '.join(filter(None, text_parts))
        return text.strip()

    async def _generate_insights(
        self,
        query: str,
        results: List[SearchResult],
        project_context: Optional[Dict[str, Any]] = None
    ) -> tuple[Optional[str], List[str], List[Dict[str, Any]]]:
        """Generate AI-powered insights from search results using ContextSummarizer."""
        try:
            from src.services.context_summarizer import ContextSummarizer

            if not results:
                return None, [], []

            # Use the new AI summarizer with project context
            summarizer = ContextSummarizer()
            summarized = await summarizer.summarize(query, results[:20], debug=True, project_context=project_context)

            # Convert timeline format to match expected format
            timeline = [
                {"date": item["date"], "event": item["event"]}
                for item in summarized.timeline
            ] if summarized.timeline else []

            self.logger.info(f"✅ Generated AI summary with {len(summarized.citations)} citations")

            return summarized.summary, summarized.key_people, timeline

        except Exception as e:
            self.logger.error(f"Error generating insights: {e}")
            # Fallback to no summary if AI fails
            return None, [], []

    async def _generate_insights_old(
        self,
        query: str,
        results: List[SearchResult]
    ) -> tuple[Optional[str], List[str], List[Dict[str, Any]]]:
        """OLD METHOD - Generate AI-powered insights from search results."""
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
