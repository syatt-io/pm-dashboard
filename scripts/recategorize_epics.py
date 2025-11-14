#!/usr/bin/env python3
"""
Bulk re-categorization script for epic categories.

This script re-categorizes ALL epics using the improved AI categorizer that:
1. Loads categories dynamically from database
2. Uses fuzzy matching for obvious cases (saves API calls)
3. Uses improved AI prompt with business context
4. Defaults to "UI Dev" for unclear user-facing work

Usage:
    # Dry-run (preview changes without saving)
    python scripts/recategorize_epics.py --dry-run

    # Dry-run for specific project
    python scripts/recategorize_epics.py --dry-run --project SUBS

    # Run re-categorization (save changes)
    python scripts/recategorize_epics.py

    # Run for specific project only
    python scripts/recategorize_epics.py --project SUBS

    # Run with rate limiting (2 seconds between AI calls)
    python scripts/recategorize_epics.py --rate-limit 2
"""

import argparse
import csv
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

# Add parent directory to path for imports
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.database import get_session
from src.models.epic_hours import EpicHours
from src.models.epic_category_mapping import EpicCategoryMapping
from src.services.epic_categorizer import EpicCategorizer

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_unique_epics(session: Session, project_key: str = None) -> List[Tuple[str, str, str]]:
    """Get list of unique epics from epic_hours table.

    Args:
        session: Database session
        project_key: Optional project filter

    Returns:
        List of (epic_key, epic_summary, project_key) tuples
    """
    query = (
        session.query(
            EpicHours.epic_key,
            EpicHours.epic_summary,
            EpicHours.project_key,
        )
        .group_by(
            EpicHours.epic_key,
            EpicHours.epic_summary,
            EpicHours.project_key,
        )
        .order_by(EpicHours.project_key, EpicHours.epic_key)
    )

    if project_key:
        query = query.filter(EpicHours.project_key == project_key)

    epics = query.all()
    logger.info(f"Found {len(epics)} unique epics")

    return epics


def get_current_categories(session: Session) -> Dict[str, str]:
    """Get current category mappings from database.

    Args:
        session: Database session

    Returns:
        Dictionary mapping epic_key to current category
    """
    mappings = session.query(EpicCategoryMapping).all()
    return {m.epic_key: m.category for m in mappings}


def save_preview_to_csv(
    changes: List[Dict], output_path: Path = Path("recategorization_preview.csv")
):
    """Save categorization preview to CSV.

    Args:
        changes: List of change dictionaries
        output_path: Path to output CSV file
    """
    if not changes:
        logger.info("No changes to save to CSV")
        return

    fieldnames = [
        "epic_key",
        "project_key",
        "epic_summary",
        "old_category",
        "new_category",
        "change_type",
        "used_fuzzy_match",
    ]

    with open(output_path, "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(changes)

    logger.info(f"✅ Saved preview to {output_path}")


def recategorize_epics(
    dry_run: bool = True,
    project_key: str = None,
    rate_limit: float = 0,
    save_preview: bool = True,
):
    """Re-categorize all epics using improved AI categorizer.

    Args:
        dry_run: If True, only preview changes without saving
        project_key: Optional project filter
        rate_limit: Seconds to wait between AI categorization calls
        save_preview: Save preview to CSV file
    """
    session = get_session()
    categorizer = EpicCategorizer(session)

    # Get all unique epics
    epics = get_unique_epics(session, project_key)
    logger.info(f"Processing {len(epics)} epics...")

    # Get current categories
    current_categories = get_current_categories(session)

    # Track changes
    changes = []
    fuzzy_matches = 0
    ai_categorizations = 0
    no_change = 0

    for i, (epic_key, epic_summary, project) in enumerate(epics, 1):
        old_category = current_categories.get(epic_key, "None")

        # Clear categorizer's cache to force re-categorization
        if epic_key in categorizer._cache:
            del categorizer._cache[epic_key]

        # Get new category (will use fuzzy matching or AI)
        fuzzy_match = categorizer._fuzzy_match_category(epic_summary)

        if fuzzy_match:
            new_category = fuzzy_match
            used_fuzzy = True
            fuzzy_matches += 1
        else:
            new_category = categorizer._categorize_with_ai(epic_summary)
            used_fuzzy = False
            ai_categorizations += 1

            # Rate limit AI calls
            if rate_limit > 0:
                time.sleep(rate_limit)

        # Determine change type
        if old_category == new_category:
            change_type = "no_change"
            no_change += 1
        elif old_category == "None" or old_category == "Uncategorized":
            change_type = "new"
        else:
            change_type = "updated"

        # Record change
        if change_type != "no_change" or dry_run:  # Always record in dry-run
            changes.append(
                {
                    "epic_key": epic_key,
                    "project_key": project,
                    "epic_summary": epic_summary,
                    "old_category": old_category,
                    "new_category": new_category,
                    "change_type": change_type,
                    "used_fuzzy_match": used_fuzzy,
                }
            )

        # Save to database if not dry-run
        if not dry_run and change_type != "no_change":
            categorizer._save_mapping(epic_key, new_category)

            # Also update epic_hours table
            session.query(EpicHours).filter(
                EpicHours.epic_key == epic_key
            ).update({"epic_category": new_category}, synchronize_session=False)
            session.commit()

        # Progress update
        if i % 10 == 0:
            logger.info(f"Processed {i}/{len(epics)} epics...")

    # Print summary
    print("\n" + "=" * 80)
    print(f"{'DRY RUN - ' if dry_run else ''}RECATEGORIZATION SUMMARY")
    print("=" * 80)
    print(f"Total epics processed: {len(epics)}")
    print(f"Fuzzy matches (no AI call): {fuzzy_matches}")
    print(f"AI categorizations: {ai_categorizations}")
    print(f"No change needed: {no_change}")
    print(f"New categorizations: {len([c for c in changes if c['change_type'] == 'new'])}")
    print(
        f"Updated categorizations: {len([c for c in changes if c['change_type'] == 'updated'])}"
    )
    print("=" * 80)

    # Save preview to CSV
    if save_preview and changes:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = Path(f"recategorization_preview_{timestamp}.csv")
        save_preview_to_csv([c for c in changes if c["change_type"] != "no_change"], csv_path)

    # Show sample changes
    if changes:
        print("\nSAMPLE CHANGES (first 10):")
        print("-" * 80)
        for change in changes[:10]:
            if change["change_type"] != "no_change":
                fuzzy_flag = " [FUZZY]" if change["used_fuzzy_match"] else ""
                print(
                    f"{change['epic_key']:12} {change['project_key']:6} "
                    f"{change['old_category']:20} → {change['new_category']:20}{fuzzy_flag}"
                )
                print(f"  Summary: {change['epic_summary']}")
                print()

    session.close()


def main():
    parser = argparse.ArgumentParser(
        description="Re-categorize all epics using improved AI categorizer"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without saving to database",
    )
    parser.add_argument(
        "--project",
        type=str,
        help="Only process epics from specific project (e.g., SUBS)",
    )
    parser.add_argument(
        "--rate-limit",
        type=float,
        default=0,
        help="Seconds to wait between AI calls (default: 0)",
    )
    parser.add_argument(
        "--no-preview",
        action="store_true",
        help="Don't save preview to CSV",
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

    recategorize_epics(
        dry_run=args.dry_run,
        project_key=args.project,
        rate_limit=args.rate_limit,
        save_preview=not args.no_preview,
    )

    if args.dry_run:
        print("\n✅ Dry run complete. Review the preview CSV and re-run without --dry-run to apply changes.")
    else:
        print("\n✅ Re-categorization complete!")


if __name__ == "__main__":
    main()
