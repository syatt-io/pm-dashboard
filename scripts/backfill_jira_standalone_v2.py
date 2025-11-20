#!/usr/bin/env python3
"""Standalone Jira backfill script with disk-based caching for reliability.

This script fetches all Jira issues from all projects and ingests them into Pinecone.
Unlike v1, this version saves fetched data to disk incrementally to prevent data loss.
"""

import logging
import sys
import asyncio
import json
from typing import Dict, Any, List
from datetime import datetime
from pathlib import Path

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

# Cache directory for storing fetched data
CACHE_DIR = Path("/tmp/jira_backfill_cache")
CACHE_DIR.mkdir(exist_ok=True)


def save_project_data(project_key: str, issues: List[Dict[str, Any]]) -> None:
    """Save project issues to disk cache."""
    cache_file = CACHE_DIR / f"{project_key}.json"
    try:
        with open(cache_file, "w") as f:
            json.dump(
                {
                    "project_key": project_key,
                    "issue_count": len(issues),
                    "issues": issues,
                    "fetched_at": datetime.now().isoformat(),
                },
                f,
            )
        logger.debug(f"💾 Saved {len(issues)} issues for {project_key} to {cache_file}")
    except Exception as e:
        logger.error(f"❌ Failed to save {project_key} to cache: {e}")


def load_cached_projects() -> Dict[str, List[Dict[str, Any]]]:
    """Load all cached project data from disk."""
    cached_data = {}
    if not CACHE_DIR.exists():
        return cached_data

    for cache_file in CACHE_DIR.glob("*.json"):
        try:
            with open(cache_file, "r") as f:
                data = json.load(f)
                project_key = data["project_key"]
                cached_data[project_key] = data["issues"]
                logger.info(
                    f"📂 Loaded {len(data['issues'])} cached issues for {project_key}"
                )
        except Exception as e:
            logger.error(f"❌ Failed to load cache file {cache_file}: {e}")

    return cached_data


def get_already_fetched_projects() -> set:
    """Get list of projects that have already been fetched."""
    if not CACHE_DIR.exists():
        return set()
    return {f.stem for f in CACHE_DIR.glob("*.json")}


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


def get_active_projects_from_db() -> List[str]:
    """Get active project keys from database."""
    try:
        from sqlalchemy import create_engine, text
        import os

        # Use DATABASE_URL from settings or environment
        database_url = os.getenv("DATABASE_URL") or settings.database_url
        if not database_url:
            logger.warning(
                "⚠️  No DATABASE_URL configured, cannot filter by active projects"
            )
            return []

        engine = create_engine(database_url)
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT key FROM projects WHERE is_active = true ORDER BY key")
            )
            active_keys = [row[0] for row in result]
            logger.info(
                f"✅ Found {len(active_keys)} active projects in database: {', '.join(active_keys)}"
            )
            return active_keys
    except Exception as e:
        logger.error(f"❌ Error querying database for active projects: {e}")
        return []


async def backfill_jira_issues(
    days_back: int = 730,
    resume: bool = True,
    project_filter: List[str] = None,
    active_only: bool = False,
) -> Dict[str, Any]:
    """Backfill all Jira issues from the last N days.

    Args:
        days_back: Number of days to look back
        resume: If True, skip projects that are already cached
        project_filter: Optional list of project keys to process (e.g., ['SUBS', 'SATG'])
        active_only: If True, only process projects marked as active in database
    """
    logger.info(
        f"🔄 Starting Jira backfill ({days_back} days / ~{days_back/365:.1f} years)..."
    )

    # Check for cached data
    already_fetched = get_already_fetched_projects()
    if already_fetched and resume:
        logger.info(
            f"📂 Found {len(already_fetched)} already fetched projects: {', '.join(sorted(already_fetched))}"
        )
        logger.info(f"   Will skip these and only fetch new/missing projects")

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

    # Filter by active projects if requested
    if active_only:
        active_keys = get_active_projects_from_db()
        if active_keys:
            projects = [p for p in projects if p.get("key") in active_keys]
            logger.info(f"🔍 Filtered to {len(projects)} active projects")
        else:
            logger.warning(
                "⚠️  Could not get active projects from database, processing all projects"
            )

    # Filter by specific projects if provided
    if project_filter:
        projects = [p for p in projects if p.get("key") in project_filter]
        logger.info(
            f"🔍 Filtered to {len(projects)} specific projects: {', '.join(project_filter)}"
        )

    # Sort projects by key for consistent processing
    projects.sort(key=lambda x: x.get("key", ""))

    # Fetch issues for each project (with caching)
    projects_with_issues = {}
    projects_skipped = 0

    for i, project in enumerate(projects, 1):
        project_key = project.get("key")
        project_name = project.get("name")

        # Skip if already fetched and resume mode is enabled
        if resume and project_key in already_fetched:
            logger.info(
                f"⏭️  [{i}/{len(projects)}] Skipping {project_key} (already cached)"
            )
            projects_skipped += 1
            continue

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

            # Fetch all issues for this project in ONE call
            # NOTE: /search/jql endpoint doesn't support pagination properly (always returns first page)
            # So we fetch all results with maxResults=1000 (Jira's max)
            project_issues = []

            try:
                result = await jira_client.search_issues(
                    jql=jql,
                    max_results=1000,  # Get all results in one call (Jira max is 1000)
                    start_at=0,
                    expand_comments=False,
                )
                project_issues = result.get("issues", [])
            except Exception as e:
                logger.error(f"   ❌ Error fetching issues: {e}")

            if project_issues:
                # Save to disk immediately
                save_project_data(project_key, project_issues)
                projects_with_issues[project_key] = len(project_issues)
                logger.info(
                    f"   ✅ [{i}/{len(projects)}] {project_key}: {len(project_issues)} issues (saved to disk)"
                )
            else:
                logger.info(f"   ⚪ [{i}/{len(projects)}] {project_key}: 0 issues")

        except Exception as e:
            logger.error(
                f"   ❌ [{i}/{len(projects)}] Failed to fetch {project_key}: {e}"
            )
            continue

    # Load ALL cached data (both newly fetched and previously cached)
    logger.info(f"\n{'='*80}")
    logger.info(f"📂 Loading all cached project data from {CACHE_DIR}...")
    logger.info(f"{'='*80}")

    all_cached_data = load_cached_projects()

    if not all_cached_data:
        logger.warning("⚠️  No issues found in cache")
        return {"success": True, "issues_found": 0, "issues_ingested": 0}

    # Count total issues
    total_issues = sum(len(issues) for issues in all_cached_data.values())
    logger.info(
        f"✅ Loaded {total_issues} total issues from {len(all_cached_data)} projects"
    )
    logger.info(
        f"📊 Projects: {', '.join(f'{k} ({len(v)})' for k, v in sorted(all_cached_data.items()))}"
    )

    # Ingest into Pinecone
    logger.info(f"\n{'='*80}")
    logger.info(
        f"📥 Ingesting {total_issues} issues from {len(all_cached_data)} projects into Pinecone..."
    )
    logger.info(f"{'='*80}\n")

    total_ingested = 0
    for i, (project_key, project_issues) in enumerate(
        sorted(all_cached_data.items()), 1
    ):
        try:
            # Add delay between projects (except first one)
            if i > 1:
                logger.info(
                    f"   ⏱️  Waiting {DELAY_BETWEEN_PROJECTS}s before next project..."
                )
                await asyncio.sleep(DELAY_BETWEEN_PROJECTS)

            logger.info(
                f"[{i}/{len(all_cached_data)}] Ingesting {len(project_issues)} issues from {project_key}..."
            )
            count = ingest_service.ingest_jira_issues(
                issues=project_issues, project_key=project_key
            )
            total_ingested += count
            logger.info(
                f"✅ [{i}/{len(all_cached_data)}] Ingested {count} issues from {project_key} (Total: {total_ingested}/{total_issues})"
            )
        except Exception as e:
            logger.error(f"❌ Error ingesting {project_key}: {e}")
            continue

    logger.info(f"\n{'='*80}")
    logger.info(f"✅ BACKFILL COMPLETE!")
    logger.info(f"{'='*80}")
    logger.info(f"Projects fetched this run: {len(projects_with_issues)}")
    logger.info(f"Projects skipped (cached): {projects_skipped}")
    logger.info(f"Total projects processed: {len(all_cached_data)}")
    logger.info(f"Total issues found: {total_issues}")
    logger.info(f"Total issues ingested: {total_ingested}")
    logger.info(f"Days back: {days_back} (~{days_back/365:.1f} years)")
    logger.info(f"Cache directory: {CACHE_DIR}")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")
    logger.info(f"{'='*80}\n")

    return {
        "success": True,
        "issues_found": total_issues,
        "issues_ingested": total_ingested,
        "projects_processed": len(all_cached_data),
        "projects_fetched_this_run": len(projects_with_issues),
        "projects_skipped": projects_skipped,
        "days_back": days_back,
        "cache_dir": str(CACHE_DIR),
        "timestamp": datetime.now().isoformat(),
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Backfill Jira issues to Pinecone (with disk caching)"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=730,
        help="Number of days to backfill (default: 730 / 2 years)",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Disable resume mode (re-fetch all projects)",
    )
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Clear cache directory before starting",
    )
    parser.add_argument(
        "--projects",
        type=str,
        help='Comma-separated list of project keys to backfill (e.g., "SUBS,SATG,BEVI")',
    )
    parser.add_argument(
        "--active-only",
        action="store_true",
        help="Only backfill projects marked as active in database",
    )
    args = parser.parse_args()

    # Clear cache if requested
    if args.clear_cache:
        import shutil

        if CACHE_DIR.exists():
            shutil.rmtree(CACHE_DIR)
            logger.info(f"🗑️  Cleared cache directory: {CACHE_DIR}")
        CACHE_DIR.mkdir(exist_ok=True)

    # Parse project filter
    project_filter = None
    if args.projects:
        project_filter = [p.strip().upper() for p in args.projects.split(",")]
        logger.info(f"🎯 Will process specific projects: {', '.join(project_filter)}")

    result = asyncio.run(
        backfill_jira_issues(
            days_back=args.days,
            resume=not args.no_resume,
            project_filter=project_filter,
            active_only=args.active_only,
        )
    )

    if result.get("success"):
        sys.exit(0)
    else:
        sys.exit(1)
