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
    """Backfill all Jira issues from the last N days.

    Uses per-project queries to ensure all active projects are captured,
    avoiding issues with cross-project JQL queries missing certain projects.
    """
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
            return {"success": True, "issues_found": 0, "issues_ingested": 0}

    except Exception as e:
        logger.error(f"❌ Failed to get active projects: {e}")
        return {"success": False, "error": f"Failed to get active projects: {e}"}

    # Fetch issues for each active project individually
    try:
        issues_all = []
        projects_with_issues = {}

        for i, (project_key, project_name) in enumerate(active_projects, 1):
            try:
                # Add delay between projects (except first one)
                if i > 1:
                    logger.info(f"   ⏱️  Waiting {DELAY_BETWEEN_PROJECTS}s before next project...")
                    await asyncio.sleep(DELAY_BETWEEN_PROJECTS)

                # Query this specific project
                jql = f"project = {project_key} AND updated >= -{days_back}d ORDER BY updated DESC"
                logger.info(f"[{i}/{len(active_projects)}] Fetching {project_key} ({project_name}): {jql}")

                # Fetch all pages for this project
                project_issues = []
                start_at = 0
                batch_count = 0

                while True:
                    # Add delay between batches
                    if batch_count > 0:
                        await asyncio.sleep(DELAY_BETWEEN_BATCHES)

                    result = await jira_client.search_issues(
                        jql=jql,
                        max_results=BATCH_SIZE,
                        start_at=start_at,
                        expand_comments=False
                    )
                    issues_batch = result.get('issues', [])

                    if not issues_batch:
                        break

                    project_issues.extend(issues_batch)
                    batch_count += 1

                    if len(issues_batch) < BATCH_SIZE:
                        break

                    start_at += BATCH_SIZE

                if project_issues:
                    issues_all.extend(project_issues)
                    projects_with_issues[project_key] = len(project_issues)
                    logger.info(f"   ✅ [{i}/{len(active_projects)}] {project_key}: {len(project_issues)} issues")
                else:
                    logger.info(f"   ⚪ [{i}/{len(active_projects)}] {project_key}: 0 issues")

            except Exception as e:
                logger.error(f"   ❌ [{i}/{len(active_projects)}] Failed to fetch {project_key}: {e}")
                continue

        logger.info(f"✅ Found {len(issues_all)} total issues across {len(projects_with_issues)} projects")
        logger.info(f"📊 Projects with issues: {', '.join(f'{k} ({v})' for k, v in projects_with_issues.items())}")

    except Exception as e:
        logger.error(f"❌ Failed to fetch issues: {e}")
        return {"success": False, "error": f"Failed to fetch: {e}"}

    if not issues_all:
        logger.warning("⚠️  No issues found in any active projects")
        return {"success": True, "issues_found": 0, "issues_ingested": 0}

    # Ingest into Pinecone (issues are already grouped by project from the fetch loop)
    logger.info(f"📥 Ingesting {len(issues_all)} issues from {len(projects_with_issues)} projects into Pinecone...")

    total_ingested = 0
    for i, (project_key, issue_count) in enumerate(projects_with_issues.items(), 1):
        try:
            # Get issues for this project
            project_issues = [issue for issue in issues_all if issue.get('key', '').startswith(f"{project_key}-")]

            # Add delay between projects (except first one)
            if i > 1:
                logger.info(f"   ⏱️  Waiting {DELAY_BETWEEN_PROJECTS}s before next project...")
                await asyncio.sleep(DELAY_BETWEEN_PROJECTS)

            logger.info(f"[{i}/{len(projects_with_issues)}] Ingesting {len(project_issues)} issues from {project_key}...")
            count = ingest_service.ingest_jira_issues(
                issues=project_issues,
                project_key=project_key
            )
            total_ingested += count
            logger.info(f"✅ [{i}/{len(projects_with_issues)}] Ingested {count} issues from {project_key} (Total: {total_ingested}/{len(issues_all)})")
        except Exception as e:
            logger.error(f"❌ Error ingesting {project_key}: {e}")
            continue

    logger.info(f"✅ Jira backfill complete! Total ingested: {total_ingested} issues from {len(projects_with_issues)} active projects")
    return {
        "success": True,
        "issues_found": len(issues_all),
        "issues_ingested": total_ingested,
        "projects_processed": len(projects_with_issues),
        "days_back": days_back,
        "timestamp": datetime.now().isoformat()
    }


if __name__ == "__main__":
    result = asyncio.run(backfill_jira_issues())
    if result.get("success"):
        sys.exit(0)
    else:
        sys.exit(1)
