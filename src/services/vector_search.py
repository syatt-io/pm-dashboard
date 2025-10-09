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
        """Initialize vector search service."""
        from config.settings import settings
        from openai import OpenAI

        self.settings = settings
        self.openai_client = OpenAI(api_key=settings.ai.api_key)
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
        """Get OpenAI embedding for query text."""
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

        try:
            # Query Pinecone with hybrid search
            results = self.pinecone_index.query(
                vector=query_embedding,
                top_k=top_k * 2,  # Get extra for reranking
                filter=filter_conditions,
                include_metadata=True
            )

            # Convert to SearchResult objects
            search_results = []
            for match in results.get('matches', []):
                metadata = match.get('metadata', {})

                # Parse date
                date_str = metadata.get('timestamp', '')
                try:
                    result_date = datetime.fromisoformat(date_str) if date_str else datetime.now()
                except:
                    result_date = datetime.now()

                # Create SearchResult
                search_result = SearchResult(
                    source=metadata.get('source', 'unknown'),
                    title=metadata.get('title', 'Untitled'),
                    content=metadata.get('content_preview', ''),
                    date=result_date,
                    url=metadata.get('url') or metadata.get('permalink'),
                    author=metadata.get('assignee') or metadata.get('user_id', 'Unknown'),
                    relevance_score=float(match.get('score', 0.0))
                )

                search_results.append(search_result)

            # Sort by relevance score
            search_results.sort(key=lambda x: x.relevance_score, reverse=True)

            logger.info(f"✅ Vector search found {len(search_results)} results for: {query}")
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
            project_filters = self._get_project_resource_filters(project_key.upper())

            if project_filters:
                conditions.append(project_filters)
            else:
                # Fallback: if no mappings configured, only filter Jira
                logger.warning(f"No resource mappings found for project {project_key}, only filtering Jira")
                conditions.append({"project_key": project_key.upper()})

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

    def _get_project_resource_filters(self, project_key: str) -> Optional[Dict[str, Any]]:
        """Build Pinecone filter for project using resource mappings from database.

        Args:
            project_key: Project key to get mappings for

        Returns:
            Pinecone filter dict with $or conditions for all mapped resources,
            or None if no mappings found
        """
        try:
            from src.utils.database import get_engine
            from sqlalchemy import text
            import json

            engine = get_engine()
            with engine.connect() as conn:
                result = conn.execute(
                    text("SELECT slack_channel_ids, notion_page_ids, github_repos, jira_project_keys FROM project_resource_mappings WHERE project_key = :key"),
                    {"key": project_key}
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

                # Jira: Match by project_key from mappings (if configured), otherwise use the project key itself
                if jira_projects:
                    or_conditions.append({"project_key": {"$in": jira_projects}})
                else:
                    # Fallback: use the project key itself for Jira filtering
                    or_conditions.append({"project_key": project_key})

                # Slack: Match by channel_id
                if slack_channels:
                    or_conditions.append({"channel_id": {"$in": slack_channels}})

                # Notion: Match by page_id
                if notion_pages:
                    or_conditions.append({"page_id": {"$in": notion_pages}})

                # GitHub: Match by repo name (stored in metadata during ingestion)
                if github_repo_list:
                    # Metadata field would be 'repo' or 'repository_name' depending on ingestion
                    or_conditions.append({"repo": {"$in": github_repo_list}})

                # Fireflies: Use project keywords from project_keywords table
                # Get keywords for this project
                keywords_result = conn.execute(
                    text("SELECT keyword FROM project_keywords WHERE project_key = :key"),
                    {"key": project_key}
                )
                keywords = [row[0].lower() for row in keywords_result]

                # For Fireflies, we'll rely on the semantic search to find matching meetings
                # by including project keywords in the search query (handled in ContextSearchService)
                # No explicit metadata filter needed here

                if not or_conditions:
                    return None

                logger.info(f"Project {project_key} filter: {len(or_conditions)} resource types")
                return {"$or": or_conditions}

        except Exception as e:
            logger.error(f"Error building project resource filters: {e}")
            return None

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
