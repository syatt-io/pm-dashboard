"""Database models for search feedback."""

from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, Float, JSON
from sqlalchemy.sql import func
from src.models.base import Base


class SearchFeedback(Base):
    """Store user feedback on search results."""

    __tablename__ = "search_feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # User and query info
    user_id = Column(Integer, nullable=True)  # App user ID if available
    slack_user_id = Column(String(50), nullable=True)  # Slack user ID
    query = Column(Text, nullable=False)  # Original search query

    # Feedback
    rating = Column(Integer, nullable=False)  # 1 (thumbs down) or 2 (thumbs up)
    feedback_text = Column(Text, nullable=True)  # Optional text feedback

    # Context for learning
    result_count = Column(Integer, nullable=True)  # Number of results returned
    result_sources = Column(
        JSON, nullable=True
    )  # List of sources in results (e.g., ['jira', 'slack', 'github'])
    top_result_source = Column(String(50), nullable=True)  # Source of top result
    detail_level = Column(
        String(20), nullable=True
    )  # Detail level used (brief/normal/detailed/slack)
    project_key = Column(String(10), nullable=True)  # Project context if detected

    # Response metadata
    response_time_ms = Column(Integer, nullable=True)  # How long search took
    summary_length = Column(Integer, nullable=True)  # Length of summary generated

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self):
        """String representation."""
        rating_emoji = "👍" if self.rating == 2 else "👎"
        return f"<SearchFeedback(query='{self.query[:50]}...', rating={rating_emoji}, user={self.slack_user_id})>"


class QueryExpansion(Base):
    """Store learned query expansions and synonyms."""

    __tablename__ = "query_expansions"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Original and expanded terms
    original_term = Column(String(100), nullable=False, index=True)
    expanded_term = Column(String(100), nullable=False)

    # Expansion type
    expansion_type = Column(
        String(20), nullable=False
    )  # 'synonym', 'related', 'acronym', 'learned'

    # Quality metrics
    confidence_score = Column(
        Float, nullable=False, default=1.0
    )  # How confident we are in this expansion
    usage_count = Column(
        Integer, nullable=False, default=0
    )  # How many times this expansion was used
    success_count = Column(
        Integer, nullable=False, default=0
    )  # How many times it led to positive feedback

    # Context
    project_key = Column(
        String(10), nullable=True
    )  # Project-specific expansion (e.g., "BC" -> "beauchamp")
    domain = Column(
        String(50), nullable=True
    )  # Domain context (e.g., "ecommerce", "dev-tools")

    # Metadata
    is_active = Column(
        Boolean, nullable=False, default=True
    )  # Can be disabled if low quality
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self):
        """String representation."""
        return f"<QueryExpansion('{self.original_term}' -> '{self.expanded_term}', type={self.expansion_type}, confidence={self.confidence_score:.2f})>"
