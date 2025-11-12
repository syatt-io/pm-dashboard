#!/usr/bin/env python3
"""Standalone Jira backfill script - doesn't require projects table.

This script fetches all Jira issues from all projects and ingests them into Pinecone.
"""

import logging
import sys
import asyncio
from typing import Dict, Any, List
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, ".")

from src.services.vector_ingest import VectorIngestService
from src.integrations.jira_mcp import JiraMCPClient
from config.settings import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Rate limiting configuration
BATCH_SIZE = 50
DELAY_BETWEEN_BATCHES = 2.0
DELAY_BETWEEN_PROJECTS = 5.0


async def get_all_projects(jira_client: JiraMCPClient) -> List[Dict[str, Any]]:
    """Get all projects from Jira directly."""
    try:
        import aiohttp
        import base64

        auth = base64.b64encode(
            f"{settings.jira.username}:{settings.jira.api_token}".encode()
        ).decode()

        headers = {"Authorization": f"Basic {auth}", "Accept": "application/json"}

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{settings.jira.url}/rest/api/3/project", headers=headers
            ) as response:
                if response.status == 200:
                    projects = await response.json()
                    logger.info(f"✅ Found {len(projects)} projects in Jira")
                    return projects
                else:
                    error_text = await response.text()
                    logger.error(
                        f"❌ Failed to get projects: {response.status} - {error_text}"
                    )
                    return []
    except Exception as e:
        logger.error(f"❌ Error getting projects: {e}")
        return []


async def backfill_jira_issues(days_back: int = 730) -> Dict[str, Any]:
    """Backfill all Jira issues from the last N days."""
    logger.info(
        f"🔄 Starting Jira backfill ({days_back} days / ~{days_back/365:.1f} years)..."
    )

    # Initialize services
    try:
        ingest_service = VectorIngestService()
        jira_client = JiraMCPClient(
            jira_url=settings.jira.url,
            username=settings.jira.username,
            api_token=settings.jira.api_token,
        )
        logger.info("✅ Initialized services")
    except Exception as e:
        logger.error(f"❌ Failed to initialize services: {e}")
        return {"success": False, "error": f"Failed to initialize: {e}"}

    # Get all projects from Jira
    projects = await get_all_projects(jira_client)

    if not projects:
        logger.warning("⚠️  No projects found")
        return {"success": True, "issues_found": 0, "issues_ingested": 0}

    # Sort projects by key for consistent processing
    projects.sort(key=lambda x: x.get("key", ""))

    # Fetch issues for each project
    issues_all = []
    projects_with_issues = {}

    for i, project in enumerate(projects, 1):
        project_key = project.get("key")
        project_name = project.get("name")

        try:
            # Add delay between projects (except first one)
            if i > 1:
                logger.info(
                    f"   ⏱️  Waiting {DELAY_BETWEEN_PROJECTS}s before next project..."
                )
                await asyncio.sleep(DELAY_BETWEEN_PROJECTS)

            # Query this specific project
            jql = f"project = {project_key} AND updated >= -{days_back}d ORDER BY updated DESC"
            logger.info(
                f"[{i}/{len(projects)}] Fetching {project_key} ({project_name})..."
            )

            # Fetch all pages for this project
            project_issues = []
            start_at = 0
            batch_count = 0

            while True:
                # Add delay between batches
                if batch_count > 0:
                    await asyncio.sleep(DELAY_BETWEEN_BATCHES)

                try:
                    result = await jira_client.search_issues(
                        jql=jql,
                        max_results=BATCH_SIZE,
                        start_at=start_at,
                        expand_comments=False,
                    )
                    issues_batch = result.get("issues", [])

                    if not issues_batch:
                        break

                    project_issues.extend(issues_batch)
                    batch_count += 1

                    if len(issues_batch) < BATCH_SIZE:
                        break

                    start_at += BATCH_SIZE
                except Exception as e:
                    logger.error(f"   ❌ Error fetching batch {batch_count + 1}: {e}")
                    break

            if project_issues:
                issues_all.extend(project_issues)
                projects_with_issues[project_key] = len(project_issues)
                logger.info(
                    f"   ✅ [{i}/{len(projects)}] {project_key}: {len(project_issues)} issues"
                )
            else:
                logger.info(f"   ⚪ [{i}/{len(projects)}] {project_key}: 0 issues")

        except Exception as e:
            logger.error(
                f"   ❌ [{i}/{len(projects)}] Failed to fetch {project_key}: {e}"
            )
            continue

    logger.info(
        f"✅ Found {len(issues_all)} total issues across {len(projects_with_issues)} projects"
    )
    logger.info(
        f"📊 Projects with issues: {', '.join(f'{k} ({v})' for k, v in projects_with_issues.items())}"
    )

    if not issues_all:
        logger.warning("⚠️  No issues found in any projects")
        return {"success": True, "issues_found": 0, "issues_ingested": 0}

    # Ingest into Pinecone
    logger.info(
        f"📥 Ingesting {len(issues_all)} issues from {len(projects_with_issues)} projects into Pinecone..."
    )

    total_ingested = 0
    for i, (project_key, issue_count) in enumerate(projects_with_issues.items(), 1):
        try:
            # Get issues for this project
            project_issues = [
                issue
                for issue in issues_all
                if issue.get("key", "").startswith(f"{project_key}-")
            ]

            # Add delay between projects (except first one)
            if i > 1:
                logger.info(
                    f"   ⏱️  Waiting {DELAY_BETWEEN_PROJECTS}s before next project..."
                )
                await asyncio.sleep(DELAY_BETWEEN_PROJECTS)

            logger.info(
                f"[{i}/{len(projects_with_issues)}] Ingesting {len(project_issues)} issues from {project_key}..."
            )
            count = ingest_service.ingest_jira_issues(
                issues=project_issues, project_key=project_key
            )
            total_ingested += count
            logger.info(
                f"✅ [{i}/{len(projects_with_issues)}] Ingested {count} issues from {project_key} (Total: {total_ingested}/{len(issues_all)})"
            )
        except Exception as e:
            logger.error(f"❌ Error ingesting {project_key}: {e}")
            continue

    logger.info(f"\n{'='*80}")
    logger.info(f"✅ BACKFILL COMPLETE!")
    logger.info(f"{'='*80}")
    logger.info(f"Total issues found: {len(issues_all)}")
    logger.info(f"Total issues ingested: {total_ingested}")
    logger.info(f"Projects processed: {len(projects_with_issues)}")
    logger.info(f"Days back: {days_back} (~{days_back/365:.1f} years)")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")
    logger.info(f"{'='*80}\n")

    return {
        "success": True,
        "issues_found": len(issues_all),
        "issues_ingested": total_ingested,
        "projects_processed": len(projects_with_issues),
        "days_back": days_back,
        "timestamp": datetime.now().isoformat(),
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Backfill Jira issues to Pinecone")
    parser.add_argument(
        "--days",
        type=int,
        default=730,
        help="Number of days to backfill (default: 730 / 2 years)",
    )
    args = parser.parse_args()

    result = asyncio.run(backfill_jira_issues(days_back=args.days))

    if result.get("success"):
        sys.exit(0)
    else:
        sys.exit(1)
