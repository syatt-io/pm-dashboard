"""Learning management system for storing and retrieving team insights."""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, desc, or_, and_

from config.settings import settings
from src.models.learning import Learning, Base

logger = logging.getLogger(__name__)


class LearningManager:
    """Manages learning entries across web UI and Slack."""

    def __init__(self):
        """Initialize learning manager."""
        self.engine = create_engine(settings.agent.database_url)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

    def create_learning(
        self,
        content: str,
        submitted_by: str,
        submitted_by_id: str = None,
        category: str = None,
        source: str = 'slack'
    ) -> Learning:
        """Create a new learning entry.

        Args:
            content: The learning content/insight
            submitted_by: Username of submitter
            submitted_by_id: User ID (e.g., Slack ID)
            category: Optional category
            source: Source of the learning (slack, web, retrospective)

        Returns:
            Created Learning object
        """
        try:
            learning = Learning(
                content=content,
                submitted_by=submitted_by,
                submitted_by_id=submitted_by_id,
                category=category,
                source=source
            )

            self.session.add(learning)
            self.session.commit()

            logger.info(f"Learning created: {learning.id} by {submitted_by}")
            return learning

        except Exception as e:
            logger.error(f"Error creating learning: {e}")
            self.session.rollback()
            raise

    def get_learnings(
        self,
        limit: int = 20,
        offset: int = 0,
        category: str = None,
        include_archived: bool = False
    ) -> List[Learning]:
        """Get learnings with optional filtering.

        Args:
            limit: Maximum number of results
            offset: Pagination offset
            category: Filter by category
            include_archived: Include archived learnings

        Returns:
            List of Learning objects
        """
        query = self.session.query(Learning)

        if not include_archived:
            query = query.filter(Learning.is_archived == False)

        if category:
            query = query.filter(Learning.category == category)

        return query.order_by(desc(Learning.created_at)).offset(offset).limit(limit).all()

    def get_learning(self, learning_id: str) -> Optional[Learning]:
        """Get a single learning by ID."""
        return self.session.query(Learning).filter(Learning.id == learning_id).first()

    def search_learnings(
        self,
        search_term: str,
        limit: int = 20,
        include_archived: bool = False
    ) -> List[Learning]:
        """Search learnings by content.

        Args:
            search_term: Text to search for
            limit: Maximum results
            include_archived: Include archived learnings

        Returns:
            List of matching Learning objects
        """
        query = self.session.query(Learning)

        if not include_archived:
            query = query.filter(Learning.is_archived == False)

        # Case-insensitive search
        query = query.filter(
            Learning.content.ilike(f'%{search_term}%')
        )

        return query.order_by(desc(Learning.created_at)).limit(limit).all()

    def get_recent_learnings(self, days: int = 7, limit: int = 10) -> List[Learning]:
        """Get learnings from the last N days.

        Args:
            days: Number of days to look back
            limit: Maximum results

        Returns:
            List of recent Learning objects
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        return self.session.query(Learning).filter(
            and_(
                Learning.created_at >= cutoff_date,
                Learning.is_archived == False
            )
        ).order_by(desc(Learning.created_at)).limit(limit).all()

    def get_categories(self) -> List[str]:
        """Get all unique categories used in learnings.

        Returns:
            List of category strings
        """
        categories = self.session.query(Learning.category).filter(
            and_(
                Learning.category != None,
                Learning.is_archived == False
            )
        ).distinct().all()

        return [cat[0] for cat in categories if cat[0]]

    def update_learning(
        self,
        learning_id: str,
        content: str = None,
        category: str = None
    ) -> bool:
        """Update an existing learning.

        Args:
            learning_id: ID of learning to update
            content: New content (optional)
            category: New category (optional)

        Returns:
            True if successful, False otherwise
        """
        try:
            learning = self.get_learning(learning_id)
            if not learning:
                return False

            if content is not None:
                learning.content = content
            if category is not None:
                learning.category = category

            learning.updated_at = datetime.utcnow()
            self.session.commit()

            logger.info(f"Learning updated: {learning_id}")
            return True

        except Exception as e:
            logger.error(f"Error updating learning {learning_id}: {e}")
            self.session.rollback()
            return False

    def archive_learning(self, learning_id: str) -> bool:
        """Archive (soft delete) a learning.

        Args:
            learning_id: ID of learning to archive

        Returns:
            True if successful, False otherwise
        """
        try:
            learning = self.get_learning(learning_id)
            if not learning:
                return False

            learning.is_archived = True
            learning.updated_at = datetime.utcnow()
            self.session.commit()

            logger.info(f"Learning archived: {learning_id}")
            return True

        except Exception as e:
            logger.error(f"Error archiving learning {learning_id}: {e}")
            self.session.rollback()
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about learnings.

        Returns:
            Dictionary with stats
        """
        total = self.session.query(Learning).filter(
            Learning.is_archived == False
        ).count()

        today = self.session.query(Learning).filter(
            and_(
                Learning.created_at >= datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0),
                Learning.is_archived == False
            )
        ).count()

        this_week = self.session.query(Learning).filter(
            and_(
                Learning.created_at >= datetime.utcnow() - timedelta(days=7),
                Learning.is_archived == False
            )
        ).count()

        categories = self.get_categories()

        return {
            'total': total,
            'today': today,
            'this_week': this_week,
            'categories_count': len(categories),
            'categories': categories[:10]  # Top 10 categories
        }

    def format_learning_for_slack(self, learning: Learning) -> str:
        """Format a learning for Slack display.

        Args:
            learning: Learning object

        Returns:
            Formatted string for Slack
        """
        category_str = f" [{learning.category}]" if learning.category else ""
        date_str = learning.created_at.strftime('%m/%d')

        return (
            f"💡{category_str} *{learning.content}*\n"
            f"   _by {learning.submitted_by} on {date_str}_"
        )