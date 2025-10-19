"""Service for managing search feedback."""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class FeedbackService:
    """Service for storing and analyzing search feedback."""

    def __init__(self):
        """Initialize feedback service."""
        self.logger = logging.getLogger(__name__)

    async def record_feedback(
        self,
        query: str,
        rating: int,  # 1 = thumbs down, 2 = thumbs up
        user_id: Optional[int] = None,
        slack_user_id: Optional[str] = None,
        feedback_text: Optional[str] = None,
        result_count: Optional[int] = None,
        result_sources: Optional[List[str]] = None,
        top_result_source: Optional[str] = None,
        detail_level: Optional[str] = None,
        project_key: Optional[str] = None,
        response_time_ms: Optional[int] = None,
        summary_length: Optional[int] = None
    ) -> int:
        """Record user feedback on search results.

        Args:
            query: Original search query
            rating: 1 (negative) or 2 (positive)
            user_id: App user ID if available
            slack_user_id: Slack user ID
            feedback_text: Optional text feedback
            result_count: Number of results returned
            result_sources: List of sources in results
            top_result_source: Source of top result
            detail_level: Detail level used
            project_key: Project context
            response_time_ms: Response time in milliseconds
            summary_length: Length of summary generated

        Returns:
            Feedback ID
        """
        try:
            from src.utils.database import session_scope
            from src.models.search_feedback import SearchFeedback

            with session_scope() as session:
                feedback = SearchFeedback(
                    user_id=user_id,
                    slack_user_id=slack_user_id,
                    query=query,
                    rating=rating,
                    feedback_text=feedback_text,
                    result_count=result_count,
                    result_sources=result_sources,
                    top_result_source=top_result_source,
                    detail_level=detail_level,
                    project_key=project_key,
                    response_time_ms=response_time_ms,
                    summary_length=summary_length
                )

                session.add(feedback)
                session.commit()
                session.refresh(feedback)

                rating_emoji = "👍" if rating == 2 else "👎"
                self.logger.info(
                    f"Recorded feedback {rating_emoji}: query='{query[:50]}...', "
                    f"user={slack_user_id}, sources={result_sources}"
                )

                return feedback.id

        except Exception as e:
            self.logger.error(f"Error recording feedback: {e}")
            return -1

    async def get_feedback_stats(
        self,
        days_back: int = 30,
        project_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get feedback statistics.

        Args:
            days_back: Number of days to look back
            project_key: Optional project filter

        Returns:
            Dict with feedback statistics
        """
        try:
            from src.utils.database import session_scope
            from src.models.search_feedback import SearchFeedback
            from sqlalchemy import func

            with session_scope() as session:
                cutoff = datetime.now() - timedelta(days=days_back)

                # Base query
                query = session.query(SearchFeedback).filter(
                    SearchFeedback.created_at >= cutoff
                )

                if project_key:
                    query = query.filter(SearchFeedback.project_key == project_key)

                # Total feedback count
                total_count = query.count()

                # Positive/negative breakdown
                positive_count = query.filter(SearchFeedback.rating == 2).count()
                negative_count = query.filter(SearchFeedback.rating == 1).count()

                # Average rating
                avg_rating = session.query(func.avg(SearchFeedback.rating)).filter(
                    SearchFeedback.created_at >= cutoff
                ).scalar() or 0

                # Top queries with negative feedback
                negative_queries = session.query(
                    SearchFeedback.query,
                    func.count(SearchFeedback.id).label('count')
                ).filter(
                    SearchFeedback.created_at >= cutoff,
                    SearchFeedback.rating == 1
                ).group_by(SearchFeedback.query).order_by(
                    func.count(SearchFeedback.id).desc()
                ).limit(10).all()

                # Source performance (which sources get best feedback)
                source_stats = session.query(
                    SearchFeedback.top_result_source,
                    func.avg(SearchFeedback.rating).label('avg_rating'),
                    func.count(SearchFeedback.id).label('count')
                ).filter(
                    SearchFeedback.created_at >= cutoff,
                    SearchFeedback.top_result_source.isnot(None)
                ).group_by(SearchFeedback.top_result_source).all()

                return {
                    'total_count': total_count,
                    'positive_count': positive_count,
                    'negative_count': negative_count,
                    'positive_rate': positive_count / total_count if total_count > 0 else 0,
                    'avg_rating': float(avg_rating),
                    'problematic_queries': [
                        {'query': q, 'negative_count': c}
                        for q, c in negative_queries
                    ],
                    'source_performance': [
                        {
                            'source': source,
                            'avg_rating': float(avg),
                            'count': count
                        }
                        for source, avg, count in source_stats
                    ]
                }

        except Exception as e:
            self.logger.error(f"Error getting feedback stats: {e}")
            return {}

    async def get_query_performance(
        self,
        query: str,
        days_back: int = 90
    ) -> Optional[Dict[str, Any]]:
        """Get historical performance for a specific query.

        Args:
            query: Query to analyze
            days_back: Number of days to look back

        Returns:
            Dict with query performance stats or None
        """
        try:
            from src.utils.database import session_scope
            from src.models.search_feedback import SearchFeedback
            from sqlalchemy import func

            with session_scope() as session:
                cutoff = datetime.now() - timedelta(days=days_back)

                # Get feedback for this query
                feedback_list = session.query(SearchFeedback).filter(
                    SearchFeedback.query == query,
                    SearchFeedback.created_at >= cutoff
                ).all()

                if not feedback_list:
                    return None

                # Calculate stats
                total = len(feedback_list)
                positive = sum(1 for f in feedback_list if f.rating == 2)
                negative = sum(1 for f in feedback_list if f.rating == 1)

                avg_result_count = sum(f.result_count for f in feedback_list if f.result_count) / total if total > 0 else 0
                avg_response_time = sum(f.response_time_ms for f in feedback_list if f.response_time_ms) / total if total > 0 else 0

                return {
                    'query': query,
                    'total_searches': total,
                    'positive_feedback': positive,
                    'negative_feedback': negative,
                    'positive_rate': positive / total if total > 0 else 0,
                    'avg_result_count': avg_result_count,
                    'avg_response_time_ms': avg_response_time,
                    'last_searched': max(f.created_at for f in feedback_list).isoformat()
                }

        except Exception as e:
            self.logger.error(f"Error getting query performance: {e}")
            return None

    async def should_adjust_ranking(
        self,
        query: str,
        source: str
    ) -> float:
        """Check if source ranking should be adjusted based on feedback.

        Args:
            query: Search query
            source: Source name (jira, slack, github, etc.)

        Returns:
            Boost factor (1.0 = no change, >1.0 = boost, <1.0 = reduce)
        """
        try:
            from src.utils.database import session_scope
            from src.models.search_feedback import SearchFeedback
            from sqlalchemy import func

            with session_scope() as session:
                # Look at feedback for similar queries where this source was top result
                cutoff = datetime.now() - timedelta(days=30)

                # Get average rating when this source was top result
                avg_rating = session.query(func.avg(SearchFeedback.rating)).filter(
                    SearchFeedback.query.like(f'%{query[:20]}%'),  # Similar queries
                    SearchFeedback.top_result_source == source,
                    SearchFeedback.created_at >= cutoff
                ).scalar()

                if avg_rating is None:
                    return 1.0  # No data, no adjustment

                # Convert rating (1-2 scale) to boost factor
                # avg_rating = 1.0 (all thumbs down) -> boost = 0.8 (reduce)
                # avg_rating = 1.5 (mixed) -> boost = 1.0 (no change)
                # avg_rating = 2.0 (all thumbs up) -> boost = 1.2 (increase)
                boost = 0.8 + (float(avg_rating) - 1.0) * 0.4

                return max(0.5, min(1.5, boost))  # Clamp between 0.5 and 1.5

        except Exception as e:
            self.logger.error(f"Error checking ranking adjustment: {e}")
            return 1.0
