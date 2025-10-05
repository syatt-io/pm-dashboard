"""
Tempo Hours Sync Job

Scheduled job to update current month and YTD hours from Tempo for all projects.
Runs nightly at 4am EST.
"""

import logging
from datetime import datetime
from typing import Dict, Optional
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.integrations.tempo import TempoAPIClient

logger = logging.getLogger(__name__)


class TempoSyncJob:
    """Scheduled job to sync Tempo hours to database"""

    def __init__(self):
        self.tempo_client = TempoAPIClient()

        # Get database URL from environment
        self.database_url = os.getenv("DATABASE_URL")
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable is required")

        # Create database engine and session
        self.engine = create_engine(self.database_url)
        self.Session = sessionmaker(bind=self.engine)

    def get_active_projects(self) -> list:
        """Get list of active project keys from database"""
        session = self.Session()
        try:
            result = session.execute(
                text("SELECT key FROM projects WHERE is_active = true")
            )
            projects = [row[0] for row in result]
            logger.info(f"Found {len(projects)} active projects")
            return projects
        finally:
            session.close()

    def update_project_hours(
        self,
        current_month_hours: Dict[str, float],
        cumulative_hours: Dict[str, float]
    ) -> Dict[str, int]:
        """
        Update project hours in database.

        Args:
            current_month_hours: Dict of project_key -> current month hours
            cumulative_hours: Dict of project_key -> year-to-date hours

        Returns:
            Dict with update statistics
        """
        session = self.Session()
        updated_count = 0
        skipped_count = 0

        try:
            active_projects = self.get_active_projects()

            # Get current month (first day of month)
            now = datetime.now()
            current_month = datetime(now.year, now.month, 1).date()

            for project_key in active_projects:
                current = current_month_hours.get(project_key, 0)
                cumulative = cumulative_hours.get(project_key, 0)

                # Update cumulative hours in projects table
                session.execute(
                    text("""
                        UPDATE projects
                        SET cumulative_hours = :cumulative,
                            updated_at = NOW()
                        WHERE key = :project_key
                    """),
                    {
                        "cumulative": cumulative,
                        "project_key": project_key
                    }
                )

                # Upsert current month hours into project_monthly_forecast
                result = session.execute(
                    text("""
                        INSERT INTO project_monthly_forecast
                            (project_key, month_year, actual_monthly_hours, updated_at)
                        VALUES
                            (:project_key, :month_year, :actual_hours, NOW())
                        ON CONFLICT (project_key, month_year)
                        DO UPDATE SET
                            actual_monthly_hours = :actual_hours,
                            updated_at = NOW()
                    """),
                    {
                        "project_key": project_key,
                        "month_year": current_month,
                        "actual_hours": current
                    }
                )

                updated_count += 1
                logger.info(
                    f"Updated {project_key}: "
                    f"current_month={current:.2f}h, cumulative={cumulative:.2f}h"
                )

            session.commit()
            logger.info(f"Successfully updated {updated_count} projects, skipped {skipped_count}")

            return {
                "updated": updated_count,
                "skipped": skipped_count,
                "total": len(active_projects)
            }

        except Exception as e:
            session.rollback()
            logger.error(f"Error updating project hours: {e}")
            raise
        finally:
            session.close()

    def run(self) -> Dict:
        """
        Execute the Tempo sync job.

        Returns:
            Dict with job execution statistics
        """
        start_time = datetime.now()
        logger.info(f"Starting Tempo sync job at {start_time}")

        try:
            # Fetch current month hours
            logger.info("Fetching current month hours from Tempo...")
            current_month_hours = self.tempo_client.get_current_month_hours()

            # Fetch year-to-date hours
            logger.info("Fetching year-to-date hours from Tempo...")
            cumulative_hours = self.tempo_client.get_year_to_date_hours()

            # Update database
            logger.info("Updating database...")
            update_stats = self.update_project_hours(current_month_hours, cumulative_hours)

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            stats = {
                "success": True,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration,
                "projects_updated": update_stats["updated"],
                "projects_skipped": update_stats["skipped"],
                "total_projects": update_stats["total"],
                "unique_projects_tracked": len(current_month_hours)
            }

            logger.info(f"Tempo sync job completed successfully in {duration:.2f}s")
            logger.info(f"Stats: {stats}")

            return stats

        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            logger.error(f"Tempo sync job failed after {duration:.2f}s: {e}")

            return {
                "success": False,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration,
                "error": str(e)
            }


def run_tempo_sync():
    """
    Entry point for the Tempo sync job.
    This function is called by the scheduler.
    """
    job = TempoSyncJob()
    return job.run()


if __name__ == "__main__":
    # Allow running job manually for testing
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("Running Tempo sync job manually...")
    stats = run_tempo_sync()
    print(f"\nJob completed: {stats}")
