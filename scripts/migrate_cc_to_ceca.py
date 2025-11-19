#!/usr/bin/env python3
"""
Migration script to update project_monthly_forecast rows from CC to CECA.

This script:
1. Checks if CECA exists in the projects table
2. If not, creates CECA from Jira data
3. Migrates all forecast data from CC to CECA
4. Verifies the migration

Usage:
    python scripts/migrate_cc_to_ceca.py [--dry-run]
"""
import argparse
import sys
from pathlib import Path

# Add parent directory to path to import src modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from src.utils.database import get_engine
from src.integrations.jira_mcp import JiraMCPClient
import asyncio
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def get_jira_project_data(project_key: str):
    """Fetch project data from Jira API."""
    try:
        client = JiraMCPClient()
        projects = await client.get_projects()

        for project in projects:
            if project.get("key") == project_key:
                return {
                    "key": project.get("key"),
                    "name": project.get("name"),
                    "project_type": project.get("projectTypeKey", "software"),
                }

        logger.warning(f"Project {project_key} not found in Jira")
        return None
    except Exception as e:
        logger.error(f"Error fetching Jira project data: {e}")
        return None


def ensure_project_exists(engine, project_key: str, dry_run: bool = False):
    """Ensure project exists in projects table, create if missing."""
    with engine.connect() as conn:
        # Check if project exists
        result = conn.execute(
            text("SELECT key, name FROM projects WHERE key = :key"),
            {"key": project_key},
        )
        existing = result.fetchone()

        if existing:
            logger.info(f"✅ Project {project_key} exists: {existing.name}")
            return True

        logger.warning(f"⚠️  Project {project_key} does NOT exist in projects table")

        # Fetch from Jira
        logger.info(f"Fetching {project_key} from Jira API...")
        jira_data = asyncio.run(get_jira_project_data(project_key))

        if not jira_data:
            logger.error(f"❌ Could not fetch {project_key} from Jira - cannot proceed")
            return False

        # Insert project
        if dry_run:
            logger.info(f"[DRY RUN] Would insert project: {jira_data}")
        else:
            with engine.begin() as trans_conn:
                trans_conn.execute(
                    text(
                        """
                        INSERT INTO projects (key, name, is_active, created_at, updated_at)
                        VALUES (:key, :name, true, NOW(), NOW())
                    """
                    ),
                    {"key": jira_data["key"], "name": jira_data["name"]},
                )
            logger.info(f"✅ Created project {project_key}: {jira_data['name']}")

        return True


def migrate_forecasts(engine, old_key: str, new_key: str, dry_run: bool = False):
    """Migrate forecast data from old_key to new_key."""
    with engine.connect() as conn:
        # Count rows to migrate
        result = conn.execute(
            text(
                "SELECT COUNT(*) FROM project_monthly_forecast WHERE project_key = :old_key"
            ),
            {"old_key": old_key},
        )
        count = result.scalar()

        if count == 0:
            logger.info(f"ℹ️  No forecast rows found for {old_key}")
            return True

        logger.info(
            f"Found {count} forecast rows to migrate from {old_key} to {new_key}"
        )

        # Show sample data
        result = conn.execute(
            text(
                """
                SELECT project_key, month_year, forecasted_hours
                FROM project_monthly_forecast
                WHERE project_key = :old_key
                ORDER BY month_year
                LIMIT 5
            """
            ),
            {"old_key": old_key},
        )

        logger.info("Sample rows to migrate:")
        for row in result:
            logger.info(
                f"  {row.project_key} | {row.month_year} | {row.forecasted_hours}h"
            )

        if dry_run:
            logger.info(
                f"[DRY RUN] Would update {count} rows from {old_key} to {new_key}"
            )
        else:
            # Perform migration
            with engine.begin() as trans_conn:
                result = trans_conn.execute(
                    text(
                        """
                        UPDATE project_monthly_forecast
                        SET project_key = :new_key
                        WHERE project_key = :old_key
                    """
                    ),
                    {"old_key": old_key, "new_key": new_key},
                )
                updated_count = result.rowcount

            logger.info(f"✅ Migrated {updated_count} rows from {old_key} to {new_key}")

        return True


def verify_migration(engine, old_key: str, new_key: str):
    """Verify migration was successful."""
    with engine.connect() as conn:
        # Check old key count
        result = conn.execute(
            text(
                "SELECT COUNT(*) FROM project_monthly_forecast WHERE project_key = :old_key"
            ),
            {"old_key": old_key},
        )
        old_count = result.scalar()

        # Check new key count
        result = conn.execute(
            text(
                "SELECT COUNT(*) FROM project_monthly_forecast WHERE project_key = :new_key"
            ),
            {"new_key": new_key},
        )
        new_count = result.scalar()

        logger.info("\n=== Migration Verification ===")
        logger.info(f"Rows with {old_key}: {old_count}")
        logger.info(f"Rows with {new_key}: {new_count}")

        if old_count == 0 and new_count > 0:
            logger.info("✅ Migration verified successfully!")
            return True
        elif old_count > 0:
            logger.error(
                f"❌ Migration incomplete - {old_count} rows still have {old_key}"
            )
            return False
        else:
            logger.warning(f"⚠️  No rows found for either {old_key} or {new_key}")
            return True


def main():
    parser = argparse.ArgumentParser(
        description="Migrate project forecasts from CC to CECA"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    args = parser.parse_args()

    old_key = "CC"
    new_key = "CECA"

    logger.info(f"{'=' * 60}")
    logger.info(f"Project Forecast Migration: {old_key} → {new_key}")
    logger.info(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    logger.info(f"{'=' * 60}\n")

    # Create engine
    engine = get_engine()

    # Step 1: Ensure CECA exists
    logger.info("Step 1: Ensuring target project exists...")
    if not ensure_project_exists(engine, new_key, args.dry_run):
        logger.error("❌ Cannot proceed - target project does not exist")
        return 1

    # Step 2: Migrate forecasts
    logger.info("\nStep 2: Migrating forecast data...")
    if not migrate_forecasts(engine, old_key, new_key, args.dry_run):
        logger.error("❌ Migration failed")
        return 1

    # Step 3: Verify (only in live mode)
    if not args.dry_run:
        logger.info("\nStep 3: Verifying migration...")
        if not verify_migration(engine, old_key, new_key):
            logger.error("❌ Verification failed")
            return 1

    logger.info(f"\n{'=' * 60}")
    if args.dry_run:
        logger.info("✅ Dry run complete - no changes made")
        logger.info("Run without --dry-run to apply changes")
    else:
        logger.info("✅ Migration complete!")
    logger.info(f"{'=' * 60}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
