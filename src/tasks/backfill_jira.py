#!/usr/bin/env python3
"""One-time Jira backfill script for production.

This script fetches all Jira issues from the last N days and ingests
them into the Pinecone vector database. Run once to populate historical data.

Usage:
    python src/tasks/backfill_jira.py
"""

import logging
import sys
import asyncio
from src.services.vector_ingest import VectorIngestService
from src.integrations.jira_mcp import JiraMCPClient
from config.settings import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def backfill_jira_issues(days_back: int = 2555):
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
        return 1

    # Build JQL query for date range
    jql = f"updated >= -{days_back}d ORDER BY updated DESC"
    logger.info(f"📥 Fetching Jira issues with JQL: {jql}")

    # Fetch all issues with pagination
    try:
        issues_all = []
        start_at = 0
        max_results = 100

        while True:
            # search_issues returns {"issues": [...]}
            result = await jira_client.search_issues(
                jql=jql,
                max_results=max_results,
                start_at=start_at
            )
            issues_batch = result.get('issues', [])

            if not issues_batch:
                break

            issues_all.extend(issues_batch)
            logger.info(f"   Fetched {len(issues_all)} issues so far...")

            if len(issues_batch) < max_results:
                break

            # Move to next page
            start_at += max_results

        logger.info(f"✅ Found {len(issues_all)} issues")
    except Exception as e:
        logger.error(f"❌ Failed to fetch issues: {e}")
        return 1

    if not issues_all:
        logger.warning("⚠️  No issues found - check Jira API credentials and permissions")
        return 0

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

    # Ingest into Pinecone
    total_ingested = 0
    for i, (project_key, project_issues) in enumerate(projects.items(), 1):
        try:
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
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(backfill_jira_issues()))
