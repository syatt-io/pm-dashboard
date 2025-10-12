#!/usr/bin/env python3
"""One-time Tempo backfill script for production.

This script fetches all Tempo worklogs from the last N days and ingests
them into the Pinecone vector database. Run once to populate historical time tracking data.

Usage:
    python src/tasks/backfill_tempo.py

This is the MAIN backfill implementation for Tempo time tracking data.
"""

import logging
import sys
import re
from typing import Dict, Any
from datetime import datetime, timedelta
from src.services.vector_ingest import VectorIngestService
from src.integrations.tempo import TempoAPIClient
from config.settings import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def backfill_tempo_worklogs(days_back: int = 365) -> Dict[str, Any]:
    """Backfill all Tempo worklogs from the last N days.

    Fetches worklogs for active projects and ingests them into Pinecone
    with proper issue and user resolution.

    Args:
        days_back: Number of days back to fetch (default: 365)

    Returns:
        Dict with success status, counts, and metadata
    """
    logger.info(f"🔄 Starting Tempo backfill ({days_back} days)...")

    # Initialize services
    try:
        ingest_service = VectorIngestService()
        tempo_client = TempoAPIClient()
    except Exception as e:
        logger.error(f"❌ Failed to initialize services: {e}")
        return {"success": False, "error": f"Failed to initialize: {e}"}

    # Get list of active projects from database
    try:
        from src.utils.database import get_engine
        from sqlalchemy import text

        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT key, name FROM projects WHERE is_active = true ORDER BY key")
            )
            active_projects = [(row[0], row[1]) for row in result]

        logger.info(f"📋 Found {len(active_projects)} active projects in database")

        if not active_projects:
            logger.warning("⚠️  No active projects found in database")
            return {"success": True, "worklogs_found": 0, "worklogs_ingested": 0}

    except Exception as e:
        logger.error(f"❌ Failed to get active projects: {e}")
        return {"success": False, "error": f"Failed to get active projects: {e}"}

    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    from_date = start_date.strftime("%Y-%m-%d")
    to_date = end_date.strftime("%Y-%m-%d")

    logger.info(f"📅 Fetching worklogs from {from_date} to {to_date}")

    # Fetch all worklogs for the date range
    try:
        logger.info("🔍 Fetching worklogs from Tempo API...")
        all_worklogs = tempo_client.get_worklogs(from_date, to_date)
        logger.info(f"✅ Fetched {len(all_worklogs)} total worklogs from Tempo")

        if not all_worklogs:
            logger.warning("⚠️  No worklogs found in date range")
            return {"success": True, "worklogs_found": 0, "worklogs_ingested": 0}

    except Exception as e:
        logger.error(f"❌ Failed to fetch worklogs from Tempo: {e}")
        return {"success": False, "error": f"Failed to fetch worklogs: {e}"}

    # Filter worklogs by active projects
    try:
        active_project_keys = set([key for key, _ in active_projects])
        filtered_worklogs = []
        projects_with_worklogs = {}
        fast_path_count = 0
        slow_path_count = 0
        skipped_count = 0

        # Compile regex pattern once for performance
        issue_pattern = re.compile(r'([A-Z]+-\d+)')

        logger.info(f"🔍 Starting to filter {len(all_worklogs)} worklogs by active projects...")

        for idx, worklog in enumerate(all_worklogs):
            # Progress logging every 1000 worklogs
            if (idx + 1) % 1000 == 0:
                logger.info(f"   Progress: {idx + 1}/{len(all_worklogs)} worklogs processed... "
                          f"(filtered: {len(filtered_worklogs)}, fast: {fast_path_count}, slow: {slow_path_count}, skipped: {skipped_count})")

            try:
                # Extract project key from issue key in description or issue object
                issue_id = worklog.get('issue', {}).get('id')
                description = worklog.get('description', '')

                # Fast path: extract from description
                issue_match = issue_pattern.search(description)

                if issue_match:
                    issue_key = issue_match.group(1)
                    project_key = issue_key.split('-')[0]
                    fast_path_count += 1
                else:
                    # Complete path: resolve via Jira (will be cached)
                    if issue_id:
                        try:
                            issue_key = tempo_client.get_issue_key_from_jira(str(issue_id))
                            if issue_key:
                                project_key = issue_key.split('-')[0]
                                slow_path_count += 1
                            else:
                                skipped_count += 1
                                continue
                        except Exception as jira_err:
                            logger.warning(f"Failed to resolve issue ID {issue_id}: {jira_err}")
                            skipped_count += 1
                            continue
                    else:
                        skipped_count += 1
                        continue

                # Only include worklogs for active projects
                if project_key in active_project_keys:
                    filtered_worklogs.append(worklog)
                    projects_with_worklogs[project_key] = projects_with_worklogs.get(project_key, 0) + 1

            except Exception as worklog_err:
                logger.warning(f"Error processing worklog {idx}: {worklog_err}")
                skipped_count += 1
                continue

        logger.info(f"✅ Filtered to {len(filtered_worklogs)} worklogs from {len(projects_with_worklogs)} active projects")
        logger.info(f"📊 Resolution stats: Fast path: {fast_path_count}, Slow path (Jira API): {slow_path_count}, Skipped: {skipped_count}")
        logger.info(f"📊 Projects with worklogs: {', '.join(f'{k} ({v})' for k, v in sorted(projects_with_worklogs.items()))}")

        if not filtered_worklogs:
            logger.warning("⚠️  No worklogs found for active projects")
            return {"success": True, "worklogs_found": 0, "worklogs_ingested": 0}

    except Exception as e:
        logger.error(f"❌ Failed to filter worklogs: {e}", exc_info=True)
        return {"success": False, "error": f"Failed to filter worklogs: {e}"}

    # Ingest into Pinecone
    try:
        logger.info(f"📥 Ingesting {len(filtered_worklogs)} worklogs into Pinecone...")

        # Ingest all worklogs in one call (batching is handled internally)
        count = ingest_service.ingest_tempo_worklogs(
            worklogs=filtered_worklogs,
            tempo_client=tempo_client
        )

        logger.info(f"✅ Tempo backfill complete! Total ingested: {count} worklogs from {len(projects_with_worklogs)} active projects")

        # Log cache statistics
        logger.info(f"📊 Issue resolution cache: {len(tempo_client.issue_cache)} entries")
        logger.info(f"📊 User name cache: {len(tempo_client.account_cache)} entries")

        return {
            "success": True,
            "worklogs_found": len(all_worklogs),
            "worklogs_filtered": len(filtered_worklogs),
            "worklogs_ingested": count,
            "projects_processed": len(projects_with_worklogs),
            "days_back": days_back,
            "date_range": f"{from_date} to {to_date}",
            "cache_stats": {
                "issue_cache_entries": len(tempo_client.issue_cache),
                "user_cache_entries": len(tempo_client.account_cache)
            },
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"❌ Failed to ingest worklogs: {e}")
        return {"success": False, "error": f"Failed to ingest: {e}"}


if __name__ == "__main__":
    result = backfill_tempo_worklogs()
    if result.get("success"):
        sys.exit(0)
    else:
        sys.exit(1)
