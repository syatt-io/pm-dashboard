"""Learning management system for storing and retrieving team insights."""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import sessionmaker
from sqlalchemy import desc, or_, and_

from config.settings import settings
from src.models.learning import Learning, Base
from src.utils.database import get_engine

logger = logging.getLogger(__name__)


class LearningManager:
    """Manages learning entries across web UI and Slack."""

    def __init__(self):
        """Initialize learning manager."""
        self.engine = get_engine()  # Use centralized engine with proper pool settings
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

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
            content: The learning content/insight (will be stored as title+description)
            submitted_by: Username of submitter
            submitted_by_id: User ID
            category: Optional category
            source: Source of the learning (slack, web, retrospective)

        Returns:
            Created Learning object
        """
        session = self.Session()
        try:
            # Split content into title and description if it's long
            title = content[:255] if len(content) <= 255 else content[:252] + "..."
            description = content if len(content) > 255 else None

            learning = Learning(
                title=title,
                description=description,
                user_id=int(submitted_by_id) if submitted_by_id and submitted_by_id.isdigit() else None,
                category=category,
                source=source
            )

            session.add(learning)
            session.commit()
            session.refresh(learning)

            logger.info(f"Learning created: {learning.id}")
            return learning

        except Exception as e:
            logger.error(f"Error creating learning: {e}")
            session.rollback()
            raise
        finally:
            session.close()

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
            include_archived: Include archived learnings (note: schema doesn't have is_archived)

        Returns:
            List of Learning objects
        """
        session = self.Session()
        try:
            query = session.query(Learning)

            if category:
                query = query.filter(Learning.category == category)

            return query.order_by(desc(Learning.created_at)).offset(offset).limit(limit).all()
        finally:
            session.close()

    def get_learning(self, learning_id: int) -> Optional[Learning]:
        """Get a single learning by ID."""
        session = self.Session()
        try:
            return session.query(Learning).filter(Learning.id == learning_id).first()
        finally:
            session.close()

    def search_learnings(
        self,
        search_term: str,
        limit: int = 20,
        include_archived: bool = False
    ) -> List[Learning]:
        """Search learnings by title and description.

        Args:
            search_term: Text to search for
            limit: Maximum results
            include_archived: Include archived learnings (note: schema doesn't have is_archived)

        Returns:
            List of matching Learning objects
        """
        session = self.Session()
        try:
            query = session.query(Learning)

            # Case-insensitive search in title and description
            query = query.filter(
                or_(
                    Learning.title.ilike(f'%{search_term}%'),
                    Learning.description.ilike(f'%{search_term}%')
                )
            )

            return query.order_by(desc(Learning.created_at)).limit(limit).all()
        finally:
            session.close()

    def get_recent_learnings(self, days: int = 7, limit: int = 10) -> List[Learning]:
        """Get learnings from the last N days.

        Args:
            days: Number of days to look back
            limit: Maximum results

        Returns:
            List of recent Learning objects
        """
        session = self.Session()
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

            return session.query(Learning).filter(
                Learning.created_at >= cutoff_date
            ).order_by(desc(Learning.created_at)).limit(limit).all()
        finally:
            session.close()

    def get_categories(self) -> List[str]:
        """Get all unique categories used in learnings.

        Returns:
            List of category strings
        """
        session = self.Session()
        try:
            categories = session.query(Learning.category).filter(
                Learning.category != None
            ).distinct().all()

            return [cat[0] for cat in categories if cat[0]]
        finally:
            session.close()

    def update_learning(
        self,
        learning_id: int,
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
        session = self.Session()
        try:
            learning = session.query(Learning).filter(Learning.id == learning_id).first()
            if not learning:
                return False

            if content is not None:
                # Split content into title and description
                learning.title = content[:255] if len(content) <= 255 else content[:252] + "..."
                learning.description = content if len(content) > 255 else None
            if category is not None:
                learning.category = category

            learning.updated_at = datetime.now(timezone.utc)
            session.commit()

            logger.info(f"Learning updated: {learning_id}")
            return True

        except Exception as e:
            logger.error(f"Error updating learning {learning_id}: {e}")
            session.rollback()
            return False
        finally:
            session.close()

    def archive_learning(self, learning_id: int) -> bool:
        """Archive (soft delete) a learning.
        Note: Production schema doesn't have is_archived column, so this will delete the record.

        Args:
            learning_id: ID of learning to archive

        Returns:
            True if successful, False otherwise
        """
        session = self.Session()
        try:
            learning = session.query(Learning).filter(Learning.id == learning_id).first()
            if not learning:
                return False

            # Since there's no is_archived column, we'll actually delete it
            session.delete(learning)
            session.commit()

            logger.info(f"Learning deleted: {learning_id}")
            return True

        except Exception as e:
            logger.error(f"Error deleting learning {learning_id}: {e}")
            session.rollback()
            return False
        finally:
            session.close()

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about learnings.

        Returns:
            Dictionary with stats
        """
        session = self.Session()
        try:
            total = session.query(Learning).count()

            today = session.query(Learning).filter(
                Learning.created_at >= datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            ).count()

            this_week = session.query(Learning).filter(
                Learning.created_at >= datetime.now(timezone.utc) - timedelta(days=7)
            ).count()

            categories = self.get_categories()

            return {
                'total': total,
                'today': today,
                'this_week': this_week,
                'categories_count': len(categories),
                'categories': categories[:10]  # Top 10 categories
            }
        finally:
            session.close()

    def format_learning_for_slack(self, learning: Learning) -> str:
        """Format a learning for Slack display.

        Args:
            learning: Learning object

        Returns:
            Formatted string for Slack
        """
        category_str = f" [{learning.category}]" if learning.category else ""
        date_str = learning.created_at.strftime('%m/%d')
        content = learning.description or learning.title

        return (
            f"💡{category_str} *{content}*\n"
            f"   _on {date_str}_"
        )