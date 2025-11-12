#!/usr/bin/env python3
"""Extract September worklogs directly from Jira API to supplement Tempo MCP data."""

import sqlite3
from datetime import datetime
import asyncio
import logging
from collections import defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Projects to check
PROJECTS = [
    "BEAU",
    "RNWL",
    "BEVS",
    "ETHEL",
    "SUBS",
    "BEAN",
    "SLABS",
    "ECSC",
    "SYDA",
    "BIGO",
    "BMBY",
    "IRIS",
    "RENW",
    "TURK",
]


async def get_worklogs_for_project(project_key):
    """Get worklogs for all issues in a project."""
    from src.integrations.jira_mcp import JiraMCPClient
    from config.settings import settings

    client = JiraMCPClient(
        jira_url=settings.jira.url,
        username=settings.jira.username,
        api_token=settings.jira.api_token,
    )

    project_hours = defaultdict(float)

    try:
        # Search for all issues in the project
        jql = f"project = {project_key}"
        issues = await client.search_tickets(jql, max_results=100)
        logger.info(f"Found {len(issues)} issues in project {project_key}")

        for issue in issues:
            issue_key = issue.get("key")

            # Get worklogs for this issue
            try:
                worklogs = await client.get_worklog(issue_key)

                if worklogs and "worklogs" in worklogs:
                    for log in worklogs["worklogs"]:
                        # Parse the date
                        started = log.get("started", "")
                        if started:
                            # Extract date portion (YYYY-MM-DD)
                            date_str = started[:10]
                            try:
                                log_date = datetime.strptime(date_str, "%Y-%m-%d")

                                # Check if it's September 2025
                                if log_date.year == 2025 and log_date.month == 9:
                                    hours = log.get("timeSpentSeconds", 0) / 3600
                                    project_hours[project_key] += hours
                                    logger.debug(
                                        f"Found September worklog for {issue_key}: {hours}h on {date_str}"
                                    )
                            except ValueError:
                                pass
            except Exception as e:
                logger.warning(f"Error getting worklogs for {issue_key}: {e}")

    except Exception as e:
        logger.error(f"Error processing project {project_key}: {e}")
    finally:
        await client.close()

    return project_hours


async def sync_all_projects():
    """Sync worklogs for all projects."""
    all_hours = {}

    for project_key in PROJECTS:
        logger.info(f"Checking project {project_key}...")
        hours = await get_worklogs_for_project(project_key)

        if project_key in hours and hours[project_key] > 0:
            all_hours[project_key] = hours[project_key]
            logger.info(f"{project_key}: {hours[project_key]:.2f} hours in September")

    return all_hours


def update_database(september_hours):
    """Update database with September hours from Jira."""
    conn = sqlite3.connect("../database/pm_agent.db")
    cursor = conn.cursor()

    updated = 0
    for project_key, hours in september_hours.items():
        # Update the current_month_hours for September
        cursor.execute(
            """
            UPDATE projects
            SET current_month_hours = ?,
                updated_at = datetime('now')
            WHERE key = ?
        """,
            (hours, project_key),
        )

        if cursor.rowcount > 0:
            updated += 1
            logger.info(f"Updated {project_key}: {hours:.2f} hours for September")

    conn.commit()
    conn.close()

    return updated


async def main():
    logger.info("Starting Jira worklog sync for September 2025...")

    # Get September hours from Jira
    september_hours = await sync_all_projects()

    if september_hours:
        logger.info(f"\nFound September hours for {len(september_hours)} projects:")
        for project, hours in sorted(september_hours.items()):
            logger.info(f"  {project}: {hours:.2f}h")

        # Update database
        updated = update_database(september_hours)
        logger.info(f"\nUpdated {updated} projects in database")
    else:
        logger.info("No September hours found in Jira worklogs")


if __name__ == "__main__":
    asyncio.run(main())
