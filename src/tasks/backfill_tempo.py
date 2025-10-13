#!/usr/bin/env python3
"""Tempo backfill script with checkpointing and date range support.

This script fetches Tempo worklogs for a specific date range and ingests
them into the Pinecone vector database with progress tracking and resumability.

Usage:
    python src/tasks/backfill_tempo.py

Or with custom date range:
    python src/tasks/backfill_tempo.py --from-date 2024-01-01 --to-date 2024-01-31

This is the MAIN backfill implementation for Tempo time tracking data.
"""

import logging
import sys
import re
import argparse
from typing import Dict, Any, Optional
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


def backfill_tempo_worklogs(
    days_back: Optional[int] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    batch_id: Optional[str] = None
) -> Dict[str, Any]:
    """Backfill Tempo worklogs with checkpointing and verbose logging.

    Fetches worklogs for active projects and ingests them into Pinecone
    with proper issue and user resolution. Tracks progress in database for resumability.

    Args:
        days_back: Number of days back to fetch (default: 365) - ignored if from_date/to_date provided
        from_date: Start date in YYYY-MM-DD format (overrides days_back)
        to_date: End date in YYYY-MM-DD format (overrides days_back)
        batch_id: Optional batch identifier for tracking (e.g., "2024-01")

    Returns:
        Dict with success status, counts, and metadata
    """
    # Calculate date range
    if from_date and to_date:
        logger.info(f"🔄 Starting Tempo backfill for date range: {from_date} to {to_date}")
    else:
        if days_back is None:
            days_back = 365
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        from_date = start_date.strftime("%Y-%m-%d")
        to_date = end_date.strftime("%Y-%m-%d")
        logger.info(f"🔄 Starting Tempo backfill ({days_back} days): {from_date} to {to_date}")

    # Generate batch_id if not provided
    if not batch_id:
        batch_id = f"{from_date}_to_{to_date}"

    # Initialize progress tracking
    progress_record = None
    try:
        from src.utils.database import get_engine, get_session
        from src.models import BackfillProgress
        from sqlalchemy import text

        engine = get_engine()
        session = get_session()

        # Check if this batch was already completed
        existing = session.query(BackfillProgress).filter_by(
            source='tempo',
            batch_id=batch_id,
            status='completed'
        ).first()

        if existing:
            logger.warning(f"⚠️  Batch {batch_id} already completed on {existing.completed_at}")
            logger.info(f"📊 Previous result: {existing.ingested_items} worklogs ingested")
            session.close()
            return {
                "success": True,
                "already_completed": True,
                "batch_id": batch_id,
                "completed_at": existing.completed_at.isoformat() if existing.completed_at else None,
                "ingested_items": existing.ingested_items
            }

        # Create or update progress record
        progress_record = session.query(BackfillProgress).filter_by(
            source='tempo',
            batch_id=batch_id
        ).first()

        if not progress_record:
            progress_record = BackfillProgress(
                source='tempo',
                batch_id=batch_id,
                start_date=from_date,
                end_date=to_date,
                status='running',
                started_at=datetime.utcnow()
            )
            session.add(progress_record)
        else:
            progress_record.status = 'running'
            progress_record.started_at = datetime.utcnow()
            progress_record.error_message = None

        session.commit()
        logger.info(f"📋 Progress tracking initialized for batch: {batch_id}")

    except Exception as e:
        logger.error(f"❌ Failed to initialize progress tracking: {e}")
        if session:
            session.close()
        # Continue anyway - progress tracking is optional
        progress_record = None
        session = None

    # Initialize services
    try:
        ingest_service = VectorIngestService()
        tempo_client = TempoAPIClient()
        logger.info("✅ Services initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize services: {e}")
        if progress_record and session:
            progress_record.status = 'failed'
            progress_record.error_message = f"Failed to initialize services: {e}"
            session.commit()
            session.close()
        return {"success": False, "error": f"Failed to initialize: {e}"}

    # Get list of active projects from database
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT key, name FROM projects WHERE is_active = true ORDER BY key")
            )
            active_projects = [(row[0], row[1]) for row in result]

        logger.info(f"📋 Found {len(active_projects)} active projects in database")

        if not active_projects:
            logger.warning("⚠️  No active projects found in database")
            if progress_record and session:
                progress_record.status = 'completed'
                progress_record.completed_at = datetime.utcnow()
                session.commit()
                session.close()
            return {"success": True, "worklogs_found": 0, "worklogs_ingested": 0}

    except Exception as e:
        logger.error(f"❌ Failed to get active projects: {e}")
        if progress_record and session:
            progress_record.status = 'failed'
            progress_record.error_message = f"Failed to get active projects: {e}"
            session.commit()
            session.close()
        return {"success": False, "error": f"Failed to get active projects: {e}"}

    # Fetch all worklogs for the date range
    try:
        logger.info(f"🔍 Fetching worklogs from Tempo API...")
        logger.info(f"📅 Date range: {from_date} to {to_date}")

        all_worklogs = tempo_client.get_worklogs(from_date, to_date)
        logger.info(f"✅ Fetched {len(all_worklogs)} total worklogs from Tempo API")

        if progress_record and session:
            progress_record.total_items = len(all_worklogs)
            session.commit()

        if not all_worklogs:
            logger.warning("⚠️  No worklogs found in date range")
            if progress_record and session:
                progress_record.status = 'completed'
                progress_record.completed_at = datetime.utcnow()
                session.commit()
                session.close()
            return {"success": True, "worklogs_found": 0, "worklogs_ingested": 0}

    except Exception as e:
        logger.error(f"❌ Failed to fetch worklogs from Tempo: {e}")
        if progress_record and session:
            progress_record.status = 'failed'
            progress_record.error_message = f"Failed to fetch worklogs: {e}"
            session.commit()
            session.close()
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
            # Progress logging every 500 worklogs
            if (idx + 1) % 500 == 0:
                logger.info(f"   Filtering progress: {idx + 1}/{len(all_worklogs)} worklogs processed... "
                          f"(filtered: {len(filtered_worklogs)}, fast: {fast_path_count}, slow: {slow_path_count}, skipped: {skipped_count})")

                # Update progress in database
                if progress_record and session:
                    try:
                        progress_record.processed_items = idx + 1
                        session.commit()
                    except:
                        pass  # Don't fail entire backfill if progress update fails

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
            if progress_record and session:
                progress_record.status = 'completed'
                progress_record.completed_at = datetime.utcnow()
                progress_record.ingested_items = 0
                session.commit()
                session.close()
            return {"success": True, "worklogs_found": 0, "worklogs_ingested": 0}

    except Exception as e:
        logger.error(f"❌ Failed to filter worklogs: {e}", exc_info=True)
        if progress_record and session:
            progress_record.status = 'failed'
            progress_record.error_message = f"Failed to filter worklogs: {e}"
            session.commit()
            session.close()
        return {"success": False, "error": f"Failed to filter worklogs: {e}"}

    # Ingest into Pinecone
    try:
        logger.info(f"📥 Starting ingestion of {len(filtered_worklogs)} worklogs into Pinecone...")
        logger.info(f"⏱️  Estimated time: ~{len(filtered_worklogs) * 0.15:.0f} seconds (~{len(filtered_worklogs) * 0.15 / 60:.1f} minutes)")

        # Ingest all worklogs in one call (batching and progress logging handled internally)
        count = ingest_service.ingest_tempo_worklogs(
            worklogs=filtered_worklogs,
            tempo_client=tempo_client
        )

        logger.info(f"✅ Tempo backfill complete! Total ingested: {count} worklogs from {len(projects_with_worklogs)} active projects")

        # Log cache statistics
        logger.info(f"📊 Issue resolution cache: {len(tempo_client.issue_cache)} entries")
        logger.info(f"📊 User name cache: {len(tempo_client.account_cache)} entries")

        # Update progress record as completed
        if progress_record and session:
            progress_record.status = 'completed'
            progress_record.ingested_items = count
            progress_record.completed_at = datetime.utcnow()
            session.commit()
            logger.info(f"✅ Progress record updated: {batch_id} completed")
            session.close()

        return {
            "success": True,
            "batch_id": batch_id,
            "worklogs_found": len(all_worklogs),
            "worklogs_filtered": len(filtered_worklogs),
            "worklogs_ingested": count,
            "projects_processed": len(projects_with_worklogs),
            "date_range": f"{from_date} to {to_date}",
            "cache_stats": {
                "issue_cache_entries": len(tempo_client.issue_cache),
                "user_cache_entries": len(tempo_client.account_cache)
            },
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"❌ Failed to ingest worklogs: {e}", exc_info=True)
        if progress_record and session:
            progress_record.status = 'failed'
            progress_record.error_message = f"Failed to ingest: {e}"
            session.commit()
            session.close()
        return {"success": False, "error": f"Failed to ingest: {e}"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Backfill Tempo worklogs into Pinecone')
    parser.add_argument('--days-back', type=int, default=365, help='Number of days back to fetch (default: 365)')
    parser.add_argument('--from-date', type=str, help='Start date in YYYY-MM-DD format')
    parser.add_argument('--to-date', type=str, help='End date in YYYY-MM-DD format')
    parser.add_argument('--batch-id', type=str, help='Optional batch identifier (e.g., "2024-01")')

    args = parser.parse_args()

    result = backfill_tempo_worklogs(
        days_back=args.days_back,
        from_date=args.from_date,
        to_date=args.to_date,
        batch_id=args.batch_id
    )

    if result.get("success"):
        sys.exit(0)
    else:
        sys.exit(1)
