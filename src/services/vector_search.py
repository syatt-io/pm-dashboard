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
        user_email: Optional[str] = None
    ) -> List[SearchResult]:
        """Perform hybrid vector + metadata search.

        Args:
            query: Search query
            top_k: Number of results to return
            days_back: Days to search back
            sources: Filter by sources (slack, fireflies, jira)
            user_email: User email for Fireflies permission filtering

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
        filter_conditions = self._build_filter(days_back, sources, user_email)

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
        user_email: Optional[str] = None
    ) -> Dict[str, Any]:
        """Build Pinecone metadata filter.

        Args:
            days_back: Days to search back
            sources: Filter by sources
            user_email: User email for Fireflies permissions

        Returns:
            Pinecone filter dict
        """
        conditions = []

        # Date filter
        cutoff_date = datetime.now() - timedelta(days=days_back)
        conditions.append({
            "date": {"$gte": cutoff_date.strftime('%Y-%m-%d')}
        })

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
