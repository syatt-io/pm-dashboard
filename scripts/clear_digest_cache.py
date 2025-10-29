#!/usr/bin/env python3
"""
Clear project digest cache after Weekly Recap format change.

This script clears all ProjectDigestCache entries to force regeneration
with the new 6-section Weekly Recap format (vs old 4-section format).

Usage:
    python scripts/clear_digest_cache.py
"""
import os
import sys

# Add parent directory to path to import from src
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.database import get_session
from src.models import ProjectDigestCache


def clear_digest_cache():
    """Clear all project digest cache entries from database."""
    session = get_session()
    try:
        # Count existing cache entries
        count = session.query(ProjectDigestCache).count()

        if count == 0:
            print("ℹ️  No digest cache entries found")
            return

        # Delete all cache entries
        session.query(ProjectDigestCache).delete()
        session.commit()

        print(f"✅ Successfully cleared {count} digest cache entries")
        print("   Next digest generation will use new Weekly Recap format")

    except Exception as e:
        session.rollback()
        print(f"❌ Error clearing cache: {e}")
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    print("🧹 Clearing project digest cache...")
    clear_digest_cache()
