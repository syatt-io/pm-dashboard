"""Vector search service using Pinecone for hybrid semantic + keyword search."""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

from src.services.context_search import SearchResult

logger = logging.getLogger(__name__)


@dataclass
class VectorSearchResult:
    """Search result from Pinecone with score."""

    id: str
    score: float  # Similarity score (0-1)
    metadata: Dict[str, Any]


class VectorSearchService:
    """Service for hybrid vector + keyword search using Pinecone."""

    def __init__(self):
        """Initialize vector search service.

        Note: Vector embeddings always use OpenAI regardless of the configured
        AI provider for LLM operations, since Anthropic and Google don't offer
        comparable embedding models.
        """
        import os
        from config.settings import settings
        from openai import OpenAI

        self.settings = settings

        # Always use OpenAI for embeddings (get from env, not from dynamic AI config)
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            logger.warning(
                "OPENAI_API_KEY not set - vector search embeddings will fail"
            )
            logger.warning(
                "Vector search requires OpenAI for embeddings regardless of LLM provider"
            )

        self.openai_client = OpenAI(api_key=openai_api_key) if openai_api_key else None
        self.pinecone_index = None
        self._init_pinecone()

    def _init_pinecone(self):
        """Initialize Pinecone client."""
        try:
            from pinecone import Pinecone

            if not self.settings.pinecone.api_key:
                logger.warning("Pinecone not configured - vector search disabled")
                return

            pc = Pinecone(api_key=self.settings.pinecone.api_key)
            self.pinecone_index = pc.Index(self.settings.pinecone.index_name)
            logger.info(
                f"✅ Connected to Pinecone index: {self.settings.pinecone.index_name}"
            )

        except Exception as e:
            logger.error(f"Failed to initialize Pinecone: {e}")
            self.pinecone_index = None

    def is_available(self) -> bool:
        """Check if vector search is available."""
        return self.pinecone_index is not None

    def get_embedding(self, text: str) -> Optional[List[float]]:
        """Get OpenAI embedding for query text.

        Note: Always uses OpenAI for embeddings regardless of configured LLM provider.
        """
        if not self.openai_client:
            logger.error("OpenAI client not initialized - cannot generate embeddings")
            logger.error("Set OPENAI_API_KEY environment variable for vector search")
            return None

        try:
            response = self.openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=text[:8000],  # Truncate to token limit
            )
            return response.data[0].embedding

        except Exception as e:
            logger.error(f"Error getting query embedding: {e}")
            return None

    def search(
        self,
        query: str,
        top_k: int = 20,
        days_back: int = 90,
        sources: Optional[List[str]] = None,
        user_email: Optional[str] = None,
        project_key: Optional[str] = None,
        epic_key: Optional[str] = None,
    ) -> List[SearchResult]:
        """Perform hybrid vector + metadata search.

        Args:
            query: Search query
            top_k: Number of results to return
            days_back: Days to search back
            sources: Filter by sources (slack, fireflies, jira)
            user_email: User email for Fireflies permission filtering
            project_key: Filter by project key (e.g., 'SUBS', 'BC')
            epic_key: Filter by epic key (e.g., 'SUBS-617') for Jira tickets

        Returns:
            List of SearchResult objects
        """
        if not self.pinecone_index:
            logger.warning("Pinecone not available - falling back to keyword search")
            return []

        # Get query embedding
        query_embedding = self.get_embedding(query)
        if not query_embedding:
            logger.error("Failed to generate query embedding")
            return []

        # Build metadata filter
        filter_conditions = self._build_filter(
            days_back, sources, user_email, project_key, epic_key
        )

        # Debug: Log the actual Pinecone filter being applied
        logger.info(f"🔍 Pinecone filter conditions: {filter_conditions}")

        try:
            # Query Pinecone with hybrid search
            results = self.pinecone_index.query(
                vector=query_embedding,
                top_k=top_k * 2,  # Get extra for reranking
                filter=filter_conditions,
                include_metadata=True,
            )

            # Convert to SearchResult objects and apply title boost
            search_results = []
            for match in results.get("matches", []):
                metadata = match.get("metadata", {})

                # Parse date
                date_str = metadata.get("timestamp", "")
                try:
                    result_date = (
                        datetime.fromisoformat(date_str) if date_str else datetime.now()
                    )
                except:
                    result_date = datetime.now()

                # Get base relevance score
                base_score = float(match.get("score", 0.0))

                # Apply multiple boost types (multiplicative)
                title = metadata.get("title", "Untitled")
                source = metadata.get("source", "unknown")

                # 1. Apply title boost for Fireflies meetings with project keywords
                score = self._apply_title_boost(
                    base_score=base_score,
                    title=title,
                    source=source,
                    query=query,
                    project_key=project_key,
                )

                # 2. Apply entity boost for exact ticket keys and project names
                score = self._apply_entity_boost(
                    base_score=score, query=query, metadata=metadata, source=source
                )

                # 3. Apply recency boost for recently updated Jira tickets
                score = self._apply_recency_boost(
                    base_score=score, source=source, updated_at=result_date
                )

                boosted_score = score

                # Create SearchResult with source-specific metadata
                source = metadata.get("source", "unknown")
                search_result = SearchResult(
                    source=source,
                    title=title,
                    content=metadata.get("content_preview", ""),
                    date=result_date,
                    url=metadata.get("url") or metadata.get("permalink"),
                    author=metadata.get("assignee")
                    or metadata.get("user_id", "Unknown"),
                    relevance_score=boosted_score,
                    # Jira-specific metadata (only populated for Jira sources)
                    status=metadata.get("status") if source == "jira" else None,
                    issue_key=metadata.get("issue_key") if source == "jira" else None,
                    priority=metadata.get("priority") if source == "jira" else None,
                    issue_type=metadata.get("issue_type") if source == "jira" else None,
                    project_key=(
                        metadata.get("project_key") if source == "jira" else None
                    ),
                    assignee_name=(
                        metadata.get("assignee_name") if source == "jira" else None
                    ),
                )

                search_results.append(search_result)

            # Sort by boosted relevance score
            search_results.sort(key=lambda x: x.relevance_score, reverse=True)

            # Enrich with hierarchically related Jira issues (subtasks, linked issues)
            enriched_results = self._enrich_with_related_issues(
                search_results, top_n_candidates=5
            )

            # Re-sort after enrichment (new related issues might have high hierarchical scores)
            enriched_results.sort(key=lambda x: x.relevance_score, reverse=True)

            # Apply source diversification to ensure balanced results
            diversified_results = self._diversify_sources(enriched_results, top_k)

            # Debug: Log results by source for troubleshooting
            source_counts = {}
            for result in diversified_results:
                source_counts[result.source] = source_counts.get(result.source, 0) + 1

            logger.info(
                f"✅ Vector search found {len(diversified_results)} results for: {query}"
            )
            if source_counts:
                source_breakdown = ", ".join(
                    [f"{src}: {count}" for src, count in source_counts.items()]
                )
                logger.info(
                    f"   📊 Results by source (after diversification): {source_breakdown}"
                )

            return diversified_results

        except Exception as e:
            logger.error(f"Error during vector search: {e}")
            return []

    def _build_filter(
        self,
        days_back: int,
        sources: Optional[List[str]] = None,
        user_email: Optional[str] = None,
        project_key: Optional[str] = None,
        epic_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build Pinecone metadata filter.

        Args:
            days_back: Days to search back
            sources: Filter by sources
            user_email: User email for Fireflies permissions
            project_key: Filter by project key (Jira only)
            epic_key: Filter by epic key (Jira only, e.g., 'SUBS-617')

        Returns:
            Pinecone filter dict
        """
        conditions = []

        # Date filter - use numeric timestamp_epoch for Pinecone $gte operator
        cutoff_date = datetime.now() - timedelta(days=days_back)
        conditions.append({"timestamp_epoch": {"$gte": int(cutoff_date.timestamp())}})

        # Project filter - applies across all data sources using resource mappings
        if project_key:
            # Get project resource mappings from database
            logger.info(f"🔍 Building project filter for: {project_key.upper()}")
            project_filters = self._get_project_resource_filters(project_key.upper())

            if project_filters:
                logger.info(
                    f"✅ Applied project filter with {len(project_filters.get('$or', []))} resource types"
                )
                logger.info(f"📋 Filter conditions: {project_filters}")
                conditions.append(project_filters)
            else:
                # If project couldn't be resolved, return empty results
                logger.warning(
                    f"⚠️  Could not find project '{project_key}' - returning no results"
                )
                # Return a filter that matches nothing
                conditions.append({"project_key": "__NONEXISTENT__"})

        # Epic filter - for Jira tickets belonging to a specific epic
        if epic_key:
            logger.info(f"🎯 Applying epic filter: epic_key={epic_key}")
            conditions.append(
                {
                    "$or": [
                        {"epic_key": epic_key},  # Child tickets of the epic
                        {"issue_key": epic_key},  # The epic itself
                    ]
                }
            )

        # Source filter
        if sources:
            conditions.append({"source": {"$in": sources}})

        # Permission filters
        # For Slack and Jira: access_type = 'all' (all users have access)
        # For Fireflies: check access_list or is_public
        if user_email:
            # User can see:
            # 1. All Slack/Jira content (access_type = 'all')
            # 2. Fireflies meetings where they're in access_list OR is_public = true
            permission_filter = {
                "$or": [
                    # All Slack/Jira content
                    {"access_type": "all"},
                    # Fireflies public meetings
                    {"is_public": True},
                    # Fireflies shared meetings where user is in access_list
                    {"access_list": {"$in": [user_email]}},
                ]
            }
            conditions.append(permission_filter)
        else:
            # No user email - only show public/all content
            conditions.append({"$or": [{"access_type": "all"}, {"is_public": True}]})

        # Combine all conditions with AND
        if len(conditions) == 1:
            return conditions[0]
        else:
            return {"$and": conditions}

    def hybrid_search(
        self,
        query: str,
        top_k: int = 20,
        days_back: int = 90,
        sources: Optional[List[str]] = None,
        user_email: Optional[str] = None,
        alpha: float = 0.7,  # Weight for vector vs keyword (1.0 = pure vector, 0.0 = pure keyword)
    ) -> List[SearchResult]:
        """Perform hybrid search combining vector similarity and keyword matching.

        Args:
            query: Search query
            top_k: Number of results
            days_back: Days to search back
            sources: Filter by sources
            user_email: User email for permissions
            alpha: Weight for vector search (0.7 = 70% vector, 30% keyword)

        Returns:
            List of search results ranked by combined score
        """
        # For Phase 1, just use pure vector search
        # In Phase 2, we can add sparse vector support or BM25 for hybrid
        return self.search(query, top_k, days_back, sources, user_email)

    def _resolve_project_key(self, project_input: str) -> Optional[str]:
        """Resolve project name or key to canonical project key.

        Args:
            project_input: User input (could be project key like "BRNS" or name like "Berns")

        Returns:
            Canonical project key if found, None otherwise
        """
        try:
            from src.utils.database import get_engine
            from sqlalchemy import text

            engine = get_engine()
            with engine.connect() as conn:
                # Try exact match on key first
                result = conn.execute(
                    text("SELECT key FROM projects WHERE key = :key"),
                    {"key": project_input.upper()},
                )
                row = result.fetchone()
                if row:
                    return row[0]

                # Try case-insensitive match on name
                result = conn.execute(
                    text("SELECT key FROM projects WHERE LOWER(name) = LOWER(:name)"),
                    {"name": project_input},
                )
                row = result.fetchone()
                if row:
                    return row[0]

                # Try partial match on name (e.g., "berns" matches "Berns Garden Center")
                result = conn.execute(
                    text(
                        "SELECT key FROM projects WHERE LOWER(name) LIKE LOWER(:name)"
                    ),
                    {"name": f"%{project_input}%"},
                )
                row = result.fetchone()
                if row:
                    return row[0]

                return None

        except Exception as e:
            logger.error(f"Error resolving project key: {e}")
            return None

    def _get_project_resource_filters(
        self, project_key: str
    ) -> Optional[Dict[str, Any]]:
        """Build Pinecone filter for project using resource mappings from database.

        Args:
            project_key: Project key or name to get mappings for

        Returns:
            Pinecone filter dict with $or conditions for all mapped resources,
            or None if no mappings found
        """
        try:
            from src.utils.database import get_engine
            from sqlalchemy import text
            import json

            # Resolve project name/key to canonical key
            canonical_key = self._resolve_project_key(project_key)
            if not canonical_key:
                logger.warning(
                    f"⚠️  Could not resolve project '{project_key}' to a valid project key"
                )
                return None

            logger.info(f"📋 Resolved '{project_key}' to project key: {canonical_key}")

            engine = get_engine()
            with engine.connect() as conn:
                result = conn.execute(
                    text(
                        "SELECT slack_channel_ids, notion_page_ids, github_repos, jira_project_keys FROM project_resource_mappings WHERE project_key = :key"
                    ),
                    {"key": canonical_key},
                )
                row = result.fetchone()

                if not row:
                    return None

                slack_channel_ids, notion_page_ids, github_repos, jira_project_keys = (
                    row
                )

                # Parse JSON arrays
                slack_channels = (
                    json.loads(slack_channel_ids) if slack_channel_ids else []
                )
                notion_pages = json.loads(notion_page_ids) if notion_page_ids else []
                github_repo_list = json.loads(github_repos) if github_repos else []
                jira_projects = (
                    json.loads(jira_project_keys) if jira_project_keys else []
                )

                # Build $or filter combining all resource types
                or_conditions = []

                # Jira: Match by project_key from mappings (if configured), otherwise use the canonical key
                if jira_projects:
                    or_conditions.append({"project_key": {"$in": jira_projects}})
                else:
                    # Fallback: use the canonical key for Jira filtering
                    or_conditions.append({"project_key": canonical_key})

                # Slack: Match by channel_id
                if slack_channels:
                    or_conditions.append({"channel_id": {"$in": slack_channels}})

                # Notion: Match by parent_id (includes all child pages automatically)
                # If a parent page/database is mapped, this will match:
                # 1. The parent page itself (page_id matches)
                # 2. All child pages (parent_id matches)
                if notion_pages:
                    or_conditions.append(
                        {
                            "$or": [
                                {
                                    "page_id": {"$in": notion_pages}
                                },  # Match parent pages directly
                                {
                                    "parent_id": {"$in": notion_pages}
                                },  # Match all child pages
                            ]
                        }
                    )

                # GitHub: Match by repo name (stored in metadata during ingestion)
                if github_repo_list:
                    # Metadata field would be 'repo' or 'repository_name' depending on ingestion
                    or_conditions.append({"repo": {"$in": github_repo_list}})

                # Fireflies: Use project_tags field for filtering
                # Meetings are tagged with project keys during ingestion based on keyword matching
                fireflies_filter = {
                    "$and": [
                        {"source": "fireflies"},
                        {"project_tags": {"$in": [canonical_key]}},
                    ]
                }

                or_conditions.append(fireflies_filter)
                logger.info(
                    f"📝 Added Fireflies filter for project tag: {canonical_key}"
                )

                if not or_conditions:
                    return None

                logger.info(
                    f"Project {project_key} filter: {len(or_conditions)} resource types"
                )
                return {"$or": or_conditions}

        except Exception as e:
            logger.error(f"Error building project resource filters: {e}")
            return None

    def _apply_title_boost(
        self,
        base_score: float,
        title: str,
        source: str,
        query: str,
        project_key: Optional[str] = None,
    ) -> float:
        """Apply title boost to meetings with project keywords in title.

        Args:
            base_score: Base similarity score from Pinecone
            title: Meeting title
            source: Data source (fireflies, slack, jira, etc.)
            query: User's search query
            project_key: Project key to check for in title

        Returns:
            Boosted score if project keyword found in title, otherwise base score
        """
        # Only boost Fireflies meetings
        if source != "fireflies":
            return base_score

        # Get project keywords to check for in title
        keywords_to_check = []

        # If project_key is provided, use it
        if project_key:
            # Resolve to canonical key
            canonical_key = self._resolve_project_key(project_key)
            if canonical_key:
                keywords_to_check.append(canonical_key.lower())

                # Also get the project name
                try:
                    from src.utils.database import get_engine
                    from sqlalchemy import text

                    engine = get_engine()
                    with engine.connect() as conn:
                        result = conn.execute(
                            text("SELECT name FROM projects WHERE key = :key"),
                            {"key": canonical_key},
                        )
                        row = result.fetchone()
                        if row:
                            project_name = row[0]
                            keywords_to_check.append(project_name.lower())
                            # Also check for common variations (e.g., "Beauchamp" from "Beauchamp Garden Center")
                            name_parts = project_name.lower().split()
                            keywords_to_check.extend(name_parts)
                except Exception as e:
                    logger.debug(
                        f"Could not fetch project name for {canonical_key}: {e}"
                    )

        # Also extract potential project names from the query
        # Common patterns: "Beauchamp", "Berns", etc.
        query_words = query.lower().split()
        for word in query_words:
            # Filter out common stop words
            if len(word) > 3 and word not in [
                "what",
                "when",
                "where",
                "which",
                "been",
                "focused",
                "working",
                "last",
                "weeks",
                "days",
            ]:
                keywords_to_check.append(word)

        # Check if any keywords appear in title
        title_lower = title.lower()
        boost_applied = False

        for keyword in keywords_to_check:
            if keyword in title_lower:
                boost_applied = True
                logger.debug(f"📈 Title boost applied: '{title}' contains '{keyword}'")
                break

        # Apply 30% boost if project keyword found in title
        if boost_applied:
            boosted_score = base_score * 1.3
            logger.debug(
                f"   Base score: {base_score:.3f} → Boosted: {boosted_score:.3f}"
            )
            return boosted_score

        return base_score

    def _apply_entity_boost(
        self, base_score: float, query: str, metadata: dict, source: str
    ) -> float:
        """Apply strong boost for exact entity matches (ticket keys, project names).

        Args:
            base_score: Original relevance score
            query: Search query text
            metadata: Result metadata with issue_key, project_key, title
            source: Result source type

        Returns:
            Boosted score if entities match
        """
        query_upper = query.upper()
        boost_applied = False
        multiplier = 1.0

        # Check for exact ticket key match (SUBS-123, PROJ-456)
        if source == "jira":
            issue_key = metadata.get("issue_key", "")
            if issue_key and issue_key in query_upper:
                multiplier = 2.0  # 100% boost for exact ticket match
                logger.debug(f"🎯 Exact ticket match: {issue_key} → 2.0x boost")
                boost_applied = True

        # Check for project key match (SUBS, PROJ)
        if not boost_applied and source == "jira":
            project_key = metadata.get("project_key", "")
            if project_key and project_key in query_upper:
                multiplier = 1.5  # 50% boost for project match
                logger.debug(f"📁 Project match: {project_key} → 1.5x boost")
                boost_applied = True

        # Check for project/client name in title or content
        # Extract multi-word entities like "SearchSpring", "Snuggle Bugz"
        if not boost_applied:
            query_words = query.lower().split()
            title_content = (
                metadata.get("title", "") + " " + metadata.get("summary", "")
            ).lower()

            # Check for 2-3 word phrases
            for i in range(len(query_words) - 1):
                phrase = " ".join(query_words[i : i + 3])
                if len(phrase) > 8 and phrase in title_content:
                    multiplier = 1.4  # 40% boost for multi-word entity match
                    logger.debug(f"🔍 Entity phrase match: '{phrase}' → 1.4x boost")
                    boost_applied = True
                    break

        return base_score * multiplier

    def _apply_recency_boost(
        self, base_score: float, source: str, updated_at: Optional[datetime]
    ) -> float:
        """Apply recency boost to Jira tickets based on update time.

        Args:
            base_score: Original relevance score
            source: Result source type
            updated_at: Last update timestamp

        Returns:
            Boosted score with recency multiplier
        """
        # Only boost Jira tickets with valid timestamps
        if source != "jira" or not updated_at:
            return base_score

        # Calculate days since update
        # Handle both timezone-aware and timezone-naive datetimes
        now = datetime.now(updated_at.tzinfo) if updated_at.tzinfo else datetime.now()
        days_old = (now - updated_at).days

        # Apply graduated boost
        if days_old <= 7:
            multiplier = 1.5  # 50% boost for updates within a week
        elif days_old <= 14:
            multiplier = 1.3  # 30% boost for updates within 2 weeks
        elif days_old <= 30:
            multiplier = 1.15  # 15% boost for updates within a month
        else:
            multiplier = 1.0  # No boost for older items

        if multiplier > 1.0:
            logger.debug(
                f"📅 Recency boost: {days_old}d old → {multiplier}x multiplier"
            )

        return base_score * multiplier

    def _diversify_sources(
        self, results: List[SearchResult], target_count: int, min_jira_pct: float = 0.30
    ) -> List[SearchResult]:
        """Rerank results to ensure diverse source representation.

        Args:
            results: Sorted results by relevance_score
            target_count: Final number of results to return (top_k)
            min_jira_pct: Minimum percentage of Jira results (default 30%)

        Returns:
            Reranked results with source diversification
        """
        # If we don't have enough results, just return what we have
        if len(results) <= target_count:
            return results

        # Group by source
        by_source = {"jira": [], "slack": [], "github": [], "fireflies": []}
        for result in results:
            source_key = result.source if result.source in by_source else "other"
            if source_key == "other":
                by_source.setdefault("other", []).append(result)
            else:
                by_source[source_key].append(result)

        # Calculate targets
        min_jira = max(int(target_count * min_jira_pct), 5)  # At least 5 Jira results

        # Phase 1: Ensure minimum Jira representation
        diversified = []
        jira_results = by_source["jira"][:min_jira]
        diversified.extend(jira_results)
        logger.debug(
            f"🎯 Diversification: Added {len(jira_results)} Jira results (min: {min_jira})"
        )

        # Phase 2: Round-robin from all sources for remaining slots
        remaining_slots = target_count - len(diversified)
        sources = ["slack", "github", "fireflies", "jira"]
        source_ptrs = {s: min_jira if s == "jira" else 0 for s in sources}

        added_count = {s: 0 for s in sources}

        while len(diversified) < target_count:
            added_this_round = False

            for source in sources:
                if len(diversified) >= target_count:
                    break

                # Check if this source has more results to add
                if source_ptrs[source] < len(by_source[source]):
                    result = by_source[source][source_ptrs[source]]

                    # Avoid duplicates from Phase 1
                    if result not in diversified:
                        diversified.append(result)
                        added_count[source] += 1
                        added_this_round = True

                    source_ptrs[source] += 1

            # If we couldn't add anything this round, we've exhausted all sources
            if not added_this_round:
                break

        logger.debug(
            f"   Round-robin added: {', '.join([f'{src}: {count}' for src, count in added_count.items() if count > 0])}"
        )

        return diversified[:target_count]

    def _enrich_with_related_issues(
        self, results: List[SearchResult], top_n_candidates: int = 5
    ) -> List[SearchResult]:
        """Enrich search results with hierarchically related Jira issues.

        When search results contain Jira epics or high-scoring tickets, automatically
        fetch and include their subtasks and linked issues. This ensures complete
        context even when semantic search only surfaces the parent issue.

        Args:
            results: Initial search results
            top_n_candidates: Number of top Jira results to check for related issues

        Returns:
            Enhanced results list with related issues added (with hierarchical boost)
        """
        if not results:
            return results

        # Find top Jira candidates (epics or high-scoring tickets)
        jira_results = [r for r in results if r.source == "jira" and r.issue_key]
        if not jira_results:
            logger.debug("No Jira issues found - skipping hierarchical enrichment")
            return results

        # Take top N by relevance score
        candidates = sorted(
            jira_results, key=lambda x: x.relevance_score, reverse=True
        )[:top_n_candidates]
        logger.info(f"🔗 Checking {len(candidates)} Jira issues for related tickets...")

        # Track existing issue keys to avoid duplicates
        existing_keys = {r.issue_key for r in results if r.issue_key}

        # Fetch related issues for each candidate
        related_results = []
        for candidate in candidates:
            issue_key = candidate.issue_key
            logger.debug(
                f"   Fetching related issues for {issue_key} (issue_type: {candidate.issue_type}, score: {candidate.relevance_score:.4f})"
            )

            # Fetch subtasks and linked issues via JQL
            related_issues = self._fetch_related_jira_issues_sync(issue_key)

            for issue_data in related_issues:
                related_key = issue_data.get("key")

                # Skip if already in results
                if related_key in existing_keys:
                    continue

                # Convert to SearchResult with hierarchical boost
                fields = issue_data.get("fields", {})
                status = fields.get("status", {}).get("name", "Unknown")
                priority = fields.get("priority", {}).get("name", "Medium")
                issue_type = fields.get("issuetype", {}).get("name", "Task")
                assignee_name = fields.get("assignee", {}).get(
                    "displayName", "Unassigned"
                )
                project_key = fields.get("project", {}).get("key", "")
                summary = fields.get("summary", "")
                description = fields.get("description", "")

                # Parse dates
                created_str = fields.get("created", "")
                updated_str = fields.get("updated", "")
                try:
                    created_date = (
                        datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                        if created_str
                        else datetime.now()
                    )
                    updated_date = (
                        datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
                        if updated_str
                        else datetime.now()
                    )
                except:
                    created_date = updated_date = datetime.now()

                # Apply hierarchical boost (30% boost for being related to a high-scoring result)
                base_score = (
                    candidate.relevance_score * 0.8
                )  # Related issues get 80% of parent's score
                hierarchical_score = (
                    base_score * 1.3
                )  # Then apply 30% hierarchical boost

                related_result = SearchResult(
                    source="jira",
                    title=summary,
                    content=description[:500] if description else "",
                    date=updated_date,
                    url=f"{self.settings.jira.url}/browse/{related_key}",
                    author=assignee_name,
                    relevance_score=hierarchical_score,
                    status=status,
                    issue_key=related_key,
                    priority=priority,
                    issue_type=issue_type,
                    project_key=project_key,
                    assignee_name=assignee_name,
                )

                related_results.append(related_result)
                existing_keys.add(related_key)
                logger.debug(
                    f"      → Added {related_key}: {summary[:50]} (score: {hierarchical_score:.4f})"
                )

        if related_results:
            logger.info(
                f"   ✅ Added {len(related_results)} related Jira issues via hierarchical retrieval"
            )
            return results + related_results
        else:
            logger.debug("   No new related issues found")
            return results

    def _fetch_related_jira_issues_sync(self, issue_key: str) -> List[Dict[str, Any]]:
        """Fetch subtasks and linked issues for a Jira ticket (synchronous wrapper).

        Args:
            issue_key: Jira issue key (e.g., 'SUBS-617')

        Returns:
            List of issue dictionaries with fields
        """
        import asyncio

        try:
            # Run async fetch in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    self._fetch_related_jira_issues(issue_key)
                )
                return result
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Error fetching related issues for {issue_key}: {e}")
            return []

    async def _fetch_related_jira_issues(self, issue_key: str) -> List[Dict[str, Any]]:
        """Fetch subtasks and linked issues for a Jira ticket (async).

        Uses JQL queries:
        - Subtasks: parent = {issue_key}
        - Linked issues: issue in linkedIssues({issue_key})

        Args:
            issue_key: Jira issue key (e.g., 'SUBS-617')

        Returns:
            List of issue dictionaries with fields
        """
        from src.integrations.jira_mcp import JiraMCPClient

        jira_client = JiraMCPClient()
        related_issues = []

        try:
            # Fetch subtasks
            subtasks_jql = f"parent = {issue_key}"
            subtasks_result = await jira_client.search_tickets(
                subtasks_jql, max_results=20
            )
            subtasks = (
                subtasks_result
                if isinstance(subtasks_result, list)
                else subtasks_result.get("issues", [])
            )

            if subtasks:
                logger.debug(f"      Found {len(subtasks)} subtasks")
                related_issues.extend(subtasks)

            # Fetch linked issues
            linked_jql = f"issue in linkedIssues({issue_key})"
            linked_result = await jira_client.search_tickets(linked_jql, max_results=20)
            linked = (
                linked_result
                if isinstance(linked_result, list)
                else linked_result.get("issues", [])
            )

            if linked:
                logger.debug(f"      Found {len(linked)} linked issues")
                related_issues.extend(linked)

        except Exception as e:
            logger.error(f"Error in JQL queries for {issue_key}: {e}")

        return related_issues

    def get_index_stats(self) -> Dict[str, Any]:
        """Get statistics about the Pinecone index.

        Returns:
            Dict with index stats (total_count, dimension, etc.)
        """
        if not self.pinecone_index:
            return {"available": False}

        try:
            stats = self.pinecone_index.describe_index_stats()
            return {
                "available": True,
                "total_vectors": stats.get("total_vector_count", 0),
                "dimension": stats.get("dimension", 0),
                "index_fullness": stats.get("index_fullness", 0.0),
            }

        except Exception as e:
            logger.error(f"Error getting index stats: {e}")
            return {"available": False, "error": str(e)}
