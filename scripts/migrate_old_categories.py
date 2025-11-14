#!/usr/bin/env python3
"""
Migrate old epic category values to new category names.

This script maps legacy category names (FE Dev, BE Dev, etc.) to the current
category schema (UI Dev, Project Oversight, etc.) without using AI.

Usage:
    # Dry-run (preview changes)
    python scripts/migrate_old_categories.py --dry-run

    # Run migration
    python scripts/migrate_old_categories.py
"""

import argparse
import logging
from pathlib import Path
from typing import Dict

# Add parent directory to path for imports
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.database import get_session
from src.models.epic_hours import EpicHours
from src.models.epic_category_mapping import EpicCategoryMapping
from sqlalchemy import func

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Mapping from old category names to new category names
CATEGORY_MIGRATION_MAP: Dict[str, str] = {
    # Old tech-focused names -> New business-focused names
    "FE Dev": "UI Dev",
    "BE Dev": "Project Oversight",  # Backend work often involves oversight/architecture
    "QA": "Project Oversight",  # QA is part of project management
    "DevOps": "Project Oversight",  # Infrastructure/deployment oversight
    "Design": "Design",  # Keep as is
    "UX": "UX",  # Keep as is
    "PM": "Project Oversight",  # Explicit PM work
    # Handle any other legacy values
    "Frontend": "UI Dev",
    "Backend": "Project Oversight",
    "Testing": "Project Oversight",
    "Infrastructure": "Project Oversight",
    # Keep current valid categories as-is
    "Project Oversight": "Project Oversight",
    "UI Dev": "UI Dev",
    "Customizations": "Customizations",
    "Integrations": "Integrations",
    "Migrations": "Migrations",
    "3rd Party Apps": "3rd Party Apps",
    "SEO & Analytics": "SEO & Analytics",
    "POS": "POS",
    "Launch Support": "Launch Support",
    "Uncategorized": "Uncategorized",
}


def get_category_statistics(session) -> Dict[str, int]:
    """Get count of epics per category.

    Args:
        session: Database session

    Returns:
        Dictionary mapping category to epic count
    """
    results = (
        session.query(
            EpicHours.epic_category, func.count(func.distinct(EpicHours.epic_key))
        )
        .group_by(EpicHours.epic_category)
        .order_by(EpicHours.epic_category)
        .all()
    )

    return {cat: count for cat, count in results}


def migrate_categories(dry_run: bool = True):
    """Migrate old category values to new category names.

    Args:
        dry_run: If True, only preview changes without saving
    """
    session = get_session()

    # Get current statistics
    logger.info("Analyzing current category distribution...")
    stats_before = get_category_statistics(session)

    print("\n" + "=" * 80)
    print("CURRENT CATEGORY DISTRIBUTION")
    print("=" * 80)
    for category, count in sorted(stats_before.items()):
        print(f"  {category or '(null)':30} -> {count:3} epics")
    print("=" * 80)

    # Find categories that need migration
    migrations_needed = []
    for old_cat, count in stats_before.items():
        if old_cat and old_cat not in CATEGORY_MIGRATION_MAP:
            logger.warning(
                f"Unknown category '{old_cat}' not in migration map! Will treat as 'Uncategorized'"
            )
            migrations_needed.append((old_cat, "Uncategorized", count))
        elif old_cat and CATEGORY_MIGRATION_MAP.get(old_cat) != old_cat:
            new_cat = CATEGORY_MIGRATION_MAP[old_cat]
            migrations_needed.append((old_cat, new_cat, count))
        elif not old_cat or old_cat == "null":
            migrations_needed.append((old_cat or "(null)", "Uncategorized", count))

    if not migrations_needed:
        print("\n✅ No category migrations needed! All categories are current.")
        session.close()
        return

    # Preview migrations
    print("\n" + "=" * 80)
    print(f"{'DRY RUN - ' if dry_run else ''}CATEGORY MIGRATIONS")
    print("=" * 80)
    total_epics = 0
    for old_cat, new_cat, count in migrations_needed:
        print(f"  {old_cat:30} -> {new_cat:30} ({count:3} epics)")
        total_epics += count
    print("=" * 80)
    print(f"Total epics to migrate: {total_epics}")
    print("=" * 80)

    if dry_run:
        print("\n🔍 DRY RUN MODE - No changes will be saved")
        session.close()
        return

    # Perform migrations
    print("\n⚙️  Applying migrations...")
    migrated_count = 0

    for old_cat, new_cat, expected_count in migrations_needed:
        logger.info(f"Migrating '{old_cat}' -> '{new_cat}'...")

        # Update epic_hours table
        if old_cat == "(null)":
            updated = (
                session.query(EpicHours)
                .filter(EpicHours.epic_category.is_(None))
                .update({"epic_category": new_cat}, synchronize_session=False)
            )
        else:
            updated = (
                session.query(EpicHours)
                .filter(EpicHours.epic_category == old_cat)
                .update({"epic_category": new_cat}, synchronize_session=False)
            )

        logger.info(f"  Updated {updated} rows in epic_hours")

        # Update epic_category_mappings table
        if old_cat != "(null)":
            mapping_updated = (
                session.query(EpicCategoryMapping)
                .filter(EpicCategoryMapping.category == old_cat)
                .update({"category": new_cat}, synchronize_session=False)
            )
            logger.info(f"  Updated {mapping_updated} rows in epic_category_mappings")

        session.commit()
        migrated_count += updated

    # Get final statistics
    stats_after = get_category_statistics(session)

    print("\n" + "=" * 80)
    print("NEW CATEGORY DISTRIBUTION")
    print("=" * 80)
    for category, count in sorted(stats_after.items()):
        print(f"  {category:30} -> {count:3} epics")
    print("=" * 80)

    print(f"\n✅ Migration complete! Migrated {migrated_count} epic records.")

    session.close()


def main():
    parser = argparse.ArgumentParser(
        description="Migrate old epic category values to new category names"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without saving to database",
    )

    args = parser.parse_args()

    if args.dry_run:
        print("🔍 DRY RUN MODE - No changes will be saved to database")
    else:
        print("⚠️  LIVE MODE - Changes will be saved to database!")
        response = input("Continue? (yes/no): ")
        if response.lower() != "yes":
            print("Aborted.")
            return

    migrate_categories(dry_run=args.dry_run)

    if args.dry_run:
        print(
            "\n✅ Dry run complete. Review the changes above and re-run without --dry-run to apply."
        )
    else:
        print("\n✅ Migration complete!")


if __name__ == "__main__":
    main()
