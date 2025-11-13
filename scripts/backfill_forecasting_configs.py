#!/usr/bin/env python3
"""
Backfill project_forecasting_config records for existing epic_hours data.

This script analyzes existing epic_hours records and creates corresponding
project_forecasting_config entries with date ranges based on the actual data.
"""

import sys
from pathlib import Path
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models import EpicHours, ProjectForecastingConfig
from src.utils.database import get_session
from sqlalchemy import func
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def backfill_forecasting_configs():
    """Create forecasting configs based on existing epic_hours data."""
    session = get_session()

    try:
        logger.info("Analyzing existing epic_hours data...")

        # Get unique projects with their date ranges from epic_hours
        projects_query = (
            session.query(
                EpicHours.project_key,
                func.min(EpicHours.month).label("start_date"),
                func.max(EpicHours.month).label("end_date"),
                func.count(EpicHours.id).label("record_count"),
            )
            .group_by(EpicHours.project_key)
            .order_by(EpicHours.project_key)
        )

        projects = projects_query.all()
        logger.info(f"Found {len(projects)} projects with epic hours data")

        if not projects:
            logger.warning("No epic_hours data found. Nothing to backfill.")
            return

        # Show what we found
        logger.info("\nProjects and their date ranges:")
        logger.info("-" * 80)
        for project in projects:
            logger.info(
                f"{project.project_key}: {project.start_date} to {project.end_date} "
                f"({project.record_count} records)"
            )
        logger.info("-" * 80)

        # Create forecasting configs
        created_count = 0
        updated_count = 0

        for project in projects:
            existing_config = (
                session.query(ProjectForecastingConfig)
                .filter_by(project_key=project.project_key)
                .first()
            )

            if existing_config:
                # Update existing config
                existing_config.forecasting_start_date = project.start_date
                existing_config.forecasting_end_date = project.end_date
                existing_config.updated_at = datetime.now(timezone.utc)
                logger.info(f"✓ Updated config for {project.project_key}")
                updated_count += 1
            else:
                # Create new config
                new_config = ProjectForecastingConfig(
                    project_key=project.project_key,
                    forecasting_start_date=project.start_date,
                    forecasting_end_date=project.end_date,
                    include_in_forecasting=True,  # Default to True
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
                session.add(new_config)
                logger.info(f"✓ Created config for {project.project_key}")
                created_count += 1

        session.commit()

        logger.info("\n" + "=" * 80)
        logger.info("BACKFILL COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Created: {created_count} new configs")
        logger.info(f"Updated: {updated_count} existing configs")
        logger.info(f"Total: {len(projects)} projects configured")
        logger.info("\nNext steps:")
        logger.info("  1. Go to Analytics → Epic Baselines")
        logger.info("  2. Click 'Rebuild Models'")
        logger.info("  3. Wait for baseline generation to complete")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"Error during backfill: {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    backfill_forecasting_configs()
