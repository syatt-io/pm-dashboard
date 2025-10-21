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
        openai_api_key = os.getenv('OPENAI_API_KEY')
        if not openai_api_key:
            logger.warning("OPENAI_API_KEY not set - vector search embeddings will fail")
            logger.warning("Vector search requires OpenAI for embeddings regardless of LLM provider")

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
            logger.info(f"✅ Connected to Pinecone index: {self.settings.pinecone.index_name}")

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
                input=text[:8000]  # Truncate to token limit
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
        project_key: Optional[str] = None
    ) -> List[SearchResult]:
        """Perform hybrid vector + metadata search.

        Args:
            query: Search query
            top_k: Number of results to return
            days_back: Days to search back
            sources: Filter by sources (slack, fireflies, jira)
            user_email: User email for Fireflies permission filtering
            project_key: Filter by project key (e.g., 'SUBS', 'BC')

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
        filter_conditions = self._build_filter(days_back, sources, user_email, project_key)

        # Debug: Log the actual Pinecone filter being applied
        logger.info(f"🔍 Pinecone filter conditions: {filter_conditions}")

        try:
            # Query Pinecone with hybrid search
            results = self.pinecone_index.query(
                vector=query_embedding,
                top_k=top_k * 2,  # Get extra for reranking
                filter=filter_conditions,
                include_metadata=True
            )

            # Convert to SearchResult objects and apply title boost
            search_results = []
            for match in results.get('matches', []):
                metadata = match.get('metadata', {})

                # Parse date
                date_str = metadata.get('timestamp', '')
                try:
                    result_date = datetime.fromisoformat(date_str) if date_str else datetime.now()
                except:
                    result_date = datetime.now()

                # Get base relevance score
                base_score = float(match.get('score', 0.0))

                # Apply title boost for Fireflies meetings with project keywords
                title = metadata.get('title', 'Untitled')
                boosted_score = self._apply_title_boost(
                    base_score=base_score,
                    title=title,
                    source=metadata.get('source', 'unknown'),
                    query=query,
                    project_key=project_key
                )

                # Create SearchResult
                search_result = SearchResult(
                    source=metadata.get('source', 'unknown'),
                    title=title,
                    content=metadata.get('content_preview', ''),
                    date=result_date,
                    url=metadata.get('url') or metadata.get('permalink'),
                    author=metadata.get('assignee') or metadata.get('user_id', 'Unknown'),
                    relevance_score=boosted_score
                )

                search_results.append(search_result)

            # Sort by boosted relevance score
            search_results.sort(key=lambda x: x.relevance_score, reverse=True)

            # Debug: Log results by source for troubleshooting
            source_counts = {}
            for result in search_results:
                source_counts[result.source] = source_counts.get(result.source, 0) + 1

            logger.info(f"✅ Vector search found {len(search_results)} results for: {query}")
            if source_counts:
                source_breakdown = ', '.join([f"{src}: {count}" for src, count in source_counts.items()])
                logger.info(f"   📊 Results by source: {source_breakdown}")

            return search_results[:top_k]

        except Exception as e:
            logger.error(f"Error during vector search: {e}")
            return []

    def _build_filter(
        self,
        days_back: int,
        sources: Optional[List[str]] = None,
        user_email: Optional[str] = None,
        project_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Build Pinecone metadata filter.

        Args:
            days_back: Days to search back
            sources: Filter by sources
            user_email: User email for Fireflies permissions
            project_key: Filter by project key (Jira only)

        Returns:
            Pinecone filter dict
        """
        conditions = []

        # Date filter - use numeric timestamp_epoch for Pinecone $gte operator
        cutoff_date = datetime.now() - timedelta(days=days_back)
        conditions.append({
            "timestamp_epoch": {"$gte": int(cutoff_date.timestamp())}
        })

        # Project filter - applies across all data sources using resource mappings
        if project_key:
            # Get project resource mappings from database
            logger.info(f"🔍 Building project filter for: {project_key.upper()}")
            project_filters = self._get_project_resource_filters(project_key.upper())

            if project_filters:
                logger.info(f"✅ Applied project filter with {len(project_filters.get('$or', []))} resource types")
                logger.info(f"📋 Filter conditions: {project_filters}")
                conditions.append(project_filters)
            else:
                # If project couldn't be resolved, return empty results
                logger.warning(f"⚠️  Could not find project '{project_key}' - returning no results")
                # Return a filter that matches nothing
                conditions.append({"project_key": "__NONEXISTENT__"})

        # Source filter
        if sources:
            conditions.append({
                "source": {"$in": sources}
            })

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
                    {"access_list": {"$in": [user_email]}}
                ]
            }
            conditions.append(permission_filter)
        else:
            # No user email - only show public/all content
            conditions.append({
                "$or": [
                    {"access_type": "all"},
                    {"is_public": True}
                ]
            })

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
        alpha: float = 0.7  # Weight for vector vs keyword (1.0 = pure vector, 0.0 = pure keyword)
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
                    {"key": project_input.upper()}
                )
                row = result.fetchone()
                if row:
                    return row[0]

                # Try case-insensitive match on name
                result = conn.execute(
                    text("SELECT key FROM projects WHERE LOWER(name) = LOWER(:name)"),
                    {"name": project_input}
                )
                row = result.fetchone()
                if row:
                    return row[0]

                # Try partial match on name (e.g., "berns" matches "Berns Garden Center")
                result = conn.execute(
                    text("SELECT key FROM projects WHERE LOWER(name) LIKE LOWER(:name)"),
                    {"name": f"%{project_input}%"}
                )
                row = result.fetchone()
                if row:
                    return row[0]

                return None

        except Exception as e:
            logger.error(f"Error resolving project key: {e}")
            return None

    def _get_project_resource_filters(self, project_key: str) -> Optional[Dict[str, Any]]:
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
                logger.warning(f"⚠️  Could not resolve project '{project_key}' to a valid project key")
                return None

            logger.info(f"📋 Resolved '{project_key}' to project key: {canonical_key}")

            engine = get_engine()
            with engine.connect() as conn:
                result = conn.execute(
                    text("SELECT slack_channel_ids, notion_page_ids, github_repos, jira_project_keys FROM project_resource_mappings WHERE project_key = :key"),
                    {"key": canonical_key}
                )
                row = result.fetchone()

                if not row:
                    return None

                slack_channel_ids, notion_page_ids, github_repos, jira_project_keys = row

                # Parse JSON arrays
                slack_channels = json.loads(slack_channel_ids) if slack_channel_ids else []
                notion_pages = json.loads(notion_page_ids) if notion_page_ids else []
                github_repo_list = json.loads(github_repos) if github_repos else []
                jira_projects = json.loads(jira_project_keys) if jira_project_keys else []

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
                    or_conditions.append({
                        "$or": [
                            {"page_id": {"$in": notion_pages}},  # Match parent pages directly
                            {"parent_id": {"$in": notion_pages}}  # Match all child pages
                        ]
                    })

                # GitHub: Match by repo name (stored in metadata during ingestion)
                if github_repo_list:
                    # Metadata field would be 'repo' or 'repository_name' depending on ingestion
                    or_conditions.append({"repo": {"$in": github_repo_list}})

                # Fireflies: Use project_tags field for filtering
                # Meetings are tagged with project keys during ingestion based on keyword matching
                fireflies_filter = {
                    "$and": [
                        {"source": "fireflies"},
                        {"project_tags": {"$in": [canonical_key]}}
                    ]
                }

                or_conditions.append(fireflies_filter)
                logger.info(f"📝 Added Fireflies filter for project tag: {canonical_key}")

                if not or_conditions:
                    return None

                logger.info(f"Project {project_key} filter: {len(or_conditions)} resource types")
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
        project_key: Optional[str] = None
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
        if source != 'fireflies':
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
                            {"key": canonical_key}
                        )
                        row = result.fetchone()
                        if row:
                            project_name = row[0]
                            keywords_to_check.append(project_name.lower())
                            # Also check for common variations (e.g., "Beauchamp" from "Beauchamp Garden Center")
                            name_parts = project_name.lower().split()
                            keywords_to_check.extend(name_parts)
                except Exception as e:
                    logger.debug(f"Could not fetch project name for {canonical_key}: {e}")

        # Also extract potential project names from the query
        # Common patterns: "Beauchamp", "Berns", etc.
        query_words = query.lower().split()
        for word in query_words:
            # Filter out common stop words
            if len(word) > 3 and word not in ['what', 'when', 'where', 'which', 'been', 'focused', 'working', 'last', 'weeks', 'days']:
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
            logger.debug(f"   Base score: {base_score:.3f} → Boosted: {boosted_score:.3f}")
            return boosted_score

        return base_score

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
                "total_vectors": stats.get('total_vector_count', 0),
                "dimension": stats.get('dimension', 0),
                "index_fullness": stats.get('index_fullness', 0.0)
            }

        except Exception as e:
            logger.error(f"Error getting index stats: {e}")
            return {"available": False, "error": str(e)}
