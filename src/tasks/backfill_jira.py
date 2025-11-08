#!/usr/bin/env python3
"""Jira backfill task using V2 disk-caching pattern.

This module provides the async function used by both:
1. Direct imports from API endpoints
2. Celery tasks for robust async execution

It wraps the V2 standalone script which implements the reliable disk-caching pattern.
"""

import logging
import sys
import asyncio
from typing import Dict, Any, List, Optional

# Add project root to path
sys.path.insert(0, '.')

logger = logging.getLogger(__name__)


async def backfill_jira_issues(
    days_back: int = 1,
    resume: bool = True,
    project_filter: Optional[List[str]] = None,
    active_only: bool = True
) -> Dict[str, Any]:
    """
    Backfill Jira issues using the V2 disk-caching pattern.

    This is a wrapper around the V2 standalone script which implements:
    - Disk-based caching for reliability
    - Resume capability
    - Proper pagination handling (no duplicates)
    - Metadata size validation
    - Response verification

    Args:
        days_back: Number of days to look back (default: 1 for incremental)
        resume: Skip already-cached projects (default: True)
        project_filter: Optional list of project keys to process
        active_only: Only process active projects from database (default: True)

    Returns:
        Dict with success status, counts, and metadata

    See: scripts/backfill_jira_standalone_v2.py for implementation details
    See: docs/BACKFILL_BEST_PRACTICES.md for V2 pattern documentation
    """
    logger.info(f"🔄 Starting Jira backfill (V2 pattern): days={days_back}, active_only={active_only}, resume={resume}")

    try:
        # Import the V2 backfill function
        from scripts.backfill_jira_standalone_v2 import backfill_jira_issues as v2_backfill

        # Call the V2 implementation
        result = await v2_backfill(
            days_back=days_back,
            resume=resume,
            project_filter=project_filter,
            active_only=active_only
        )

        logger.info(f"✅ Jira backfill completed: {result.get('issues_ingested', 0)} issues ingested")
        return result

    except Exception as e:
        logger.error(f"❌ Jira backfill failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "issues_found": 0,
            "issues_ingested": 0
        }


if __name__ == "__main__":
    # For testing: run a 1-day incremental backfill
    import sys

    result = asyncio.run(backfill_jira_issues(days_back=1, active_only=True))

    if result.get("success"):
        print(f"\n✅ Success! Ingested {result.get('issues_ingested', 0)} issues")
        sys.exit(0)
    else:
        print(f"\n❌ Failed: {result.get('error', 'Unknown error')}")
        sys.exit(1)
