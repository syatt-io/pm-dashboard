"""Epic category mapping model."""

from sqlalchemy import Column, String, Integer, DateTime, UniqueConstraint, Index
from datetime import datetime, timezone
from typing import Dict, Optional, List
from .base import Base
import logging

logger = logging.getLogger(__name__)


class EpicCategoryMapping(Base):
    """
    Maps epics to categories for organizational grouping.

    This table stores user-defined category assignments for epics,
    allowing epics to be grouped into categories like "Project Oversight",
    "UX", "Design", "FE Dev", "BE Dev", etc.
    """

    __tablename__ = "epic_category_mappings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    epic_key = Column(String(100), nullable=False)  # Epic key (e.g., "RNWL-123")
    category = Column(String(100), nullable=False)  # Category name

    # Metadata
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Ensure uniqueness per epic (one category per epic)
    __table_args__ = (
        UniqueConstraint("epic_key", name="uq_epic_category_mapping_epic_key"),
        Index("ix_epic_category_mappings_epic_key", "epic_key"),
    )

    def __repr__(self):
        return f"<EpicCategoryMapping(epic={self.epic_key}, category={self.category})>"

    @staticmethod
    def bulk_upsert(session, mappings: Dict[str, str]) -> Dict[str, int]:
        """
        Efficiently create or update multiple epic category mappings.

        Args:
            session: SQLAlchemy session
            mappings: Dict mapping epic_key to category name
                Example: {"SUBS-123": "FE Dev", "SUBS-124": "Backend"}

        Returns:
            Dict with counts: {"created": 2, "updated": 1, "skipped": 1}
        """
        if not mappings:
            return {"created": 0, "updated": 0, "skipped": 0}

        created = 0
        updated = 0
        skipped = 0

        for epic_key, category in mappings.items():
            # Skip if category is None (AI couldn't categorize)
            if category is None:
                skipped += 1
                continue

            # Check if mapping already exists
            existing = (
                session.query(EpicCategoryMapping).filter_by(epic_key=epic_key).first()
            )

            if existing:
                # Update if category changed
                if existing.category != category:
                    existing.category = category
                    existing.updated_at = datetime.now(timezone.utc)
                    updated += 1
                    logger.debug(
                        f"Updated category mapping for {epic_key}: "
                        f"{existing.category} → {category}"
                    )
                else:
                    skipped += 1
            else:
                # Create new mapping
                new_mapping = EpicCategoryMapping(
                    epic_key=epic_key,
                    category=category,
                )
                session.add(new_mapping)
                created += 1
                logger.debug(f"Created category mapping for {epic_key}: {category}")

        session.commit()

        logger.info(
            f"Bulk upsert complete: {created} created, {updated} updated, {skipped} skipped"
        )

        return {"created": created, "updated": updated, "skipped": skipped}
