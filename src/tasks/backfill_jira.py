#!/usr/bin/env python3
"""One-time Jira backfill script for production.

This script fetches all Jira issues from the last N days and ingests
them into the Pinecone vector database. Run once to populate historical data.

Usage:
    python src/tasks/backfill_jira.py

This is the MAIN backfill implementation. The Celery task in vector_tasks.py
calls this same function to avoid code duplication.
"""

import logging
import sys
import asyncio
import time
from typing import Dict, Any
from datetime import datetime
from src.services.vector_ingest import VectorIngestService
from src.integrations.jira_mcp import JiraMCPClient
from config.settings import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Rate limiting configuration
BATCH_SIZE = 50  # Fetch 50 issues at a time (reduced from 100)
DELAY_BETWEEN_BATCHES = 2.0  # 2 seconds between batches
DELAY_BETWEEN_PROJECTS = 5.0  # 5 seconds between projects


async def backfill_jira_issues(days_back: int = 2555) -> Dict[str, Any]:
    """Backfill all Jira issues from the last N days."""
    logger.info(f"🔄 Starting Jira backfill ({days_back} days)...")

    # Initialize services
    try:
        ingest_service = VectorIngestService()
        jira_client = JiraMCPClient(
            jira_url=settings.jira.url,
            username=settings.jira.username,
            api_token=settings.jira.api_token
        )
    except Exception as e:
        logger.error(f"❌ Failed to initialize services: {e}")
        return {"success": False, "error": f"Failed to initialize: {e}"}

    # Build JQL query for date range
    jql = f"updated >= -{days_back}d ORDER BY updated DESC"
    logger.info(f"📥 Fetching Jira issues with JQL: {jql}")

    # Fetch all issues with pagination and rate limiting
    try:
        issues_all = []
        start_at = 0
        batch_count = 0

        while True:
            # Add delay between batches (except first batch)
            if batch_count > 0:
                logger.info(f"   ⏱️  Waiting {DELAY_BETWEEN_BATCHES}s before next batch...")
                await asyncio.sleep(DELAY_BETWEEN_BATCHES)

            # search_issues returns {"issues": [...]}
            result = await jira_client.search_issues(
                jql=jql,
                max_results=BATCH_SIZE,
                start_at=start_at,
                expand_comments=False  # Don't fetch comments to reduce data
            )
            issues_batch = result.get('issues', [])

            if not issues_batch:
                break

            issues_all.extend(issues_batch)
            batch_count += 1
            logger.info(f"   Fetched {len(issues_all)} issues so far (batch {batch_count})...")

            if len(issues_batch) < BATCH_SIZE:
                break

            # Move to next page
            start_at += BATCH_SIZE

        logger.info(f"✅ Found {len(issues_all)} issues in {batch_count} batches")
    except Exception as e:
        logger.error(f"❌ Failed to fetch issues: {e}")
        return {"success": False, "error": f"Failed to fetch: {e}"}

    if not issues_all:
        logger.warning("⚠️  No issues found - check Jira API credentials and permissions")
        return {"success": True, "issues_found": 0, "issues_ingested": 0}

    # Group issues by project and ingest in batches
    logger.info("📊 Grouping issues by project...")
    projects = {}
    for issue in issues_all:
        project_key = issue.get('key', '').split('-')[0] if issue.get('key') else 'UNKNOWN'
        if project_key not in projects:
            projects[project_key] = []
        projects[project_key].append(issue)

    logger.info(f"✅ Grouped {len(issues_all)} issues into {len(projects)} projects")
    logger.info(f"📊 Projects: {', '.join(f'{k} ({len(v)})' for k, v in projects.items())}")

    # Ingest into Pinecone with delays between projects
    total_ingested = 0
    for i, (project_key, project_issues) in enumerate(projects.items(), 1):
        try:
            # Add delay between projects (except first one)
            if i > 1:
                logger.info(f"   ⏱️  Waiting {DELAY_BETWEEN_PROJECTS}s before next project...")
                await asyncio.sleep(DELAY_BETWEEN_PROJECTS)

            logger.info(f"[{i}/{len(projects)}] Ingesting {len(project_issues)} issues from {project_key}...")
            count = ingest_service.ingest_jira_issues(
                issues=project_issues,
                project_key=project_key
            )
            total_ingested += count
            logger.info(f"✅ [{i}/{len(projects)}] Ingested {count} issues from {project_key} (Total: {total_ingested}/{len(issues_all)})")
        except Exception as e:
            logger.error(f"❌ Error ingesting {project_key}: {e}")
            continue

    logger.info(f"✅ Jira backfill complete! Total ingested: {total_ingested} issues")
    return {
        "success": True,
        "issues_found": len(issues_all),
        "issues_ingested": total_ingested,
        "days_back": days_back,
        "timestamp": datetime.now().isoformat()
    }


if __name__ == "__main__":
    result = asyncio.run(backfill_jira_issues())
    if result.get("success"):
        sys.exit(0)
    else:
        sys.exit(1)
