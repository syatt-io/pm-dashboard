#!/usr/bin/env python3
"""
Database Cleanup Script: Remove Duplicate Meetings

This script identifies and removes duplicate meetings from the processed_meetings table,
keeping the meeting with the most complete analysis (longest action items + topics).

Run with --dry-run to see what would be deleted without actually deleting.
"""

import sys
import os
import argparse
import logging
from datetime import datetime
from typing import List, Dict, Any, Tuple

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from config.settings import settings

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def find_duplicate_meetings(engine) -> List[Tuple[str, datetime, int, str]]:
    """
    Find meetings with duplicate title + date combinations.

    Returns:
        List of (title, date, count, fireflies_ids) tuples
    """
    query = text(
        """
        SELECT
            title,
            date,
            COUNT(*) as duplicate_count,
            STRING_AGG(fireflies_id, ', ') as fireflies_ids
        FROM processed_meetings
        GROUP BY title, date
        HAVING COUNT(*) > 1
        ORDER BY duplicate_count DESC, date DESC
    """
    )

    with engine.connect() as conn:
        result = conn.execute(query)
        return [(row[0], row[1], row[2], row[3]) for row in result]


def get_duplicate_details(engine, title: str, date: datetime) -> List[Dict[str, Any]]:
    """
    Get detailed information for all meetings with the same title + date.

    Returns:
        List of meeting dictionaries with fireflies_id, title, date, content lengths
    """
    query = text(
        """
        SELECT
            fireflies_id,
            title,
            date,
            LENGTH(COALESCE(action_items, '')) as action_items_length,
            LENGTH(COALESCE(topics, '')) as topics_length,
            LENGTH(COALESCE(summary, '')) as summary_length,
            created_at
        FROM processed_meetings
        WHERE title = :title
          AND date = :date
        ORDER BY
            (LENGTH(COALESCE(action_items, '')) + LENGTH(COALESCE(topics, ''))) DESC,
            created_at DESC
    """
    )

    with engine.connect() as conn:
        result = conn.execute(query, {"title": title, "date": date})
        meetings = []
        for row in result:
            meetings.append(
                {
                    "fireflies_id": row[0],
                    "title": row[1],
                    "date": row[2],
                    "action_items_length": row[3],
                    "topics_length": row[4],
                    "summary_length": row[5],
                    "created_at": row[6],
                    "total_content_length": row[3] + row[4],
                }
            )
        return meetings


def delete_meeting(engine, fireflies_id: str, dry_run: bool = True) -> bool:
    """
    Delete a meeting from the database.

    Args:
        engine: SQLAlchemy engine
        fireflies_id: Fireflies ID of the meeting to delete
        dry_run: If True, don't actually delete (default: True)

    Returns:
        True if deleted (or would be deleted), False otherwise
    """
    if dry_run:
        logger.info(f"[DRY RUN] Would delete meeting: {fireflies_id}")
        return True

    query = text(
        """
        DELETE FROM processed_meetings
        WHERE fireflies_id = :fireflies_id
    """
    )

    try:
        with engine.begin() as conn:
            result = conn.execute(query, {"fireflies_id": fireflies_id})
            deleted = result.rowcount > 0
            if deleted:
                logger.info(f"✅ Deleted meeting: {fireflies_id}")
            else:
                logger.warning(f"⚠️  Meeting not found: {fireflies_id}")
            return deleted
    except Exception as e:
        logger.error(f"❌ Error deleting meeting {fireflies_id}: {e}")
        return False


def cleanup_duplicates(dry_run: bool = True) -> Dict[str, int]:
    """
    Main cleanup function: finds and removes duplicate meetings.

    Args:
        dry_run: If True, don't actually delete (default: True)

    Returns:
        Dictionary with stats: {
            'duplicate_groups': int,
            'total_duplicates': int,
            'kept': int,
            'deleted': int
        }
    """
    logger.info("=" * 70)
    logger.info("Meeting Deduplication Cleanup Script")
    logger.info("=" * 70)

    if dry_run:
        logger.warning("🔍 DRY RUN MODE - No changes will be made")
    else:
        logger.warning("⚠️  LIVE MODE - Meetings will be permanently deleted!")

    # Connect to database
    engine = create_engine(settings.agent.database_url)

    # Find duplicate groups
    logger.info("\n🔎 Searching for duplicate meetings...")
    duplicates = find_duplicate_meetings(engine)

    if not duplicates:
        logger.info("✅ No duplicate meetings found!")
        return {
            "duplicate_groups": 0,
            "total_duplicates": 0,
            "kept": 0,
            "deleted": 0,
        }

    logger.info(f"Found {len(duplicates)} duplicate groups\n")

    stats = {
        "duplicate_groups": len(duplicates),
        "total_duplicates": 0,
        "kept": 0,
        "deleted": 0,
    }

    # Process each duplicate group
    for title, date, count, fireflies_ids in duplicates:
        logger.info("-" * 70)
        logger.info(f"📋 Duplicate Group: {title}")
        logger.info(f"   Date: {date}")
        logger.info(f"   Count: {count} meetings")
        logger.info(f"   IDs: {fireflies_ids}")

        # Get detailed info for all duplicates
        meetings = get_duplicate_details(engine, title, date)

        if not meetings:
            logger.warning("   ⚠️  No meetings found (already cleaned up?)")
            continue

        stats["total_duplicates"] += len(meetings)

        # First meeting (sorted by content length DESC) is the one to keep
        keep_meeting = meetings[0]
        delete_meetings = meetings[1:]

        logger.info(f"\n   ✅ KEEP: {keep_meeting['fireflies_id']}")
        logger.info(
            f"      - Action Items: {keep_meeting['action_items_length']} bytes"
        )
        logger.info(f"      - Topics: {keep_meeting['topics_length']} bytes")
        logger.info(f"      - Summary: {keep_meeting['summary_length']} bytes")
        logger.info(
            f"      - Total Content: {keep_meeting['total_content_length']} bytes"
        )
        logger.info(f"      - Created: {keep_meeting['created_at']}")

        stats["kept"] += 1

        for meeting in delete_meetings:
            logger.info(f"\n   ❌ DELETE: {meeting['fireflies_id']}")
            logger.info(f"      - Action Items: {meeting['action_items_length']} bytes")
            logger.info(f"      - Topics: {meeting['topics_length']} bytes")
            logger.info(f"      - Summary: {meeting['summary_length']} bytes")
            logger.info(
                f"      - Total Content: {meeting['total_content_length']} bytes"
            )
            logger.info(f"      - Created: {meeting['created_at']}")

            # Delete the meeting
            if delete_meeting(engine, meeting["fireflies_id"], dry_run):
                stats["deleted"] += 1

    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("CLEANUP SUMMARY")
    logger.info("=" * 70)
    logger.info(f"Duplicate Groups: {stats['duplicate_groups']}")
    logger.info(f"Total Duplicates: {stats['total_duplicates']}")
    logger.info(f"Kept (most complete): {stats['kept']}")
    logger.info(f"Deleted: {stats['deleted']}")

    if dry_run:
        logger.info("\n🔍 This was a DRY RUN - no changes were made")
        logger.info("Run with --execute flag to actually delete duplicates")
    else:
        logger.info("\n✅ Cleanup completed successfully!")

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Clean up duplicate meetings from processed_meetings table"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually delete duplicates (default is dry-run)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Show what would be deleted without deleting (default)",
    )

    args = parser.parse_args()

    # If --execute is specified, turn off dry-run
    dry_run = not args.execute

    try:
        stats = cleanup_duplicates(dry_run=dry_run)
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Cleanup failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
