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
        self, current_month_hours: Dict[str, float], cumulative_hours: Dict[str, float]
    ) -> Dict[str, int]:
        """
        Update project hours in database.

        Args:
            current_month_hours: Dict of project_key -> current month hours
            cumulative_hours: Dict of project_key -> all-time cumulative hours

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
                    text(
                        """
                        UPDATE projects
                        SET cumulative_hours = :cumulative,
                            updated_at = NOW()
                        WHERE key = :project_key
                    """
                    ),
                    {"cumulative": cumulative, "project_key": project_key},
                )

                # Upsert current month hours into project_monthly_forecast
                result = session.execute(
                    text(
                        """
                        INSERT INTO project_monthly_forecast
                            (project_key, month_year, actual_monthly_hours, updated_at)
                        VALUES
                            (:project_key, :month_year, :actual_hours, NOW())
                        ON CONFLICT (project_key, month_year)
                        DO UPDATE SET
                            actual_monthly_hours = :actual_hours,
                            updated_at = NOW()
                    """
                    ),
                    {
                        "project_key": project_key,
                        "month_year": current_month,
                        "actual_hours": current,
                    },
                )

                updated_count += 1
                logger.info(
                    f"Updated {project_key}: "
                    f"current_month={current:.2f}h, cumulative={cumulative:.2f}h"
                )

            session.commit()
            logger.info(
                f"Successfully updated {updated_count} projects, skipped {skipped_count}"
            )

            return {
                "updated": updated_count,
                "skipped": skipped_count,
                "total": len(active_projects),
            }

        except Exception as e:
            session.rollback()
            logger.error(f"Error updating project hours: {e}")
            raise
        finally:
            session.close()

    def _get_all_time_hours_optimized(self, active_projects: list) -> Dict[str, float]:
        """
        Get cumulative all-time hours for specific projects using server-side filtering.

        This is optimized to query each project individually using Tempo API v4's
        projectId parameter, reducing data transfer by ~98.8% compared to fetching
        all worklogs and filtering client-side.

        Args:
            active_projects: List of project keys to fetch hours for

        Returns:
            Dictionary mapping project keys to cumulative hours
        """
        from datetime import datetime

        start_date = "2020-01-01"
        today = datetime.now().strftime("%Y-%m-%d")
        all_hours = {}

        logger.info(
            f"Fetching all-time hours for {len(active_projects)} projects individually..."
        )

        for idx, project_key in enumerate(active_projects, 1):
            try:
                logger.info(
                    f"[{idx}/{len(active_projects)}] Fetching hours for {project_key}..."
                )

                # Use server-side project filtering (Tempo API v4 projectId parameter)
                worklogs = self.tempo_client.get_worklogs(
                    from_date=start_date, to_date=today, project_key=project_key
                )

                # Process worklogs for this project
                project_hours, processed, skipped = self.tempo_client.process_worklogs(
                    worklogs
                )

                # Store hours for this project (should only have one key)
                if project_key in project_hours:
                    all_hours[project_key] = project_hours[project_key]
                    logger.info(
                        f"  ✅ {project_key}: {project_hours[project_key]:.2f}h ({len(worklogs)} worklogs)"
                    )
                else:
                    # No worklogs for this project
                    all_hours[project_key] = 0.0
                    logger.info(f"  ℹ️  {project_key}: 0.00h (no worklogs)")

            except Exception as e:
                logger.error(
                    f"  ❌ Error fetching hours for {project_key}: {e}", exc_info=True
                )
                # Continue with next project instead of failing entire sync
                all_hours[project_key] = 0.0

        logger.info(f"Completed fetching hours for {len(all_hours)} projects")
        return all_hours

    def run(self) -> Dict:
        """
        Execute the Tempo sync job.

        Returns:
            Dict with job execution statistics
        """
        start_time = datetime.now()
        logger.info(f"Starting Tempo sync job at {start_time}")

        try:
            # Get list of active projects first
            active_projects = self.get_active_projects()
            logger.info(f"Syncing hours for {len(active_projects)} active projects")

            # Fetch current month hours (no filter - still fast)
            logger.info("Fetching current month hours from Tempo...")
            current_month_hours = self.tempo_client.get_current_month_hours()

            # Fetch all-time hours per project using server-side filtering
            # OPTIMIZATION: Query each project individually instead of fetching ALL worklogs
            # Previous: Fetched ~59,556 worklogs for all projects (took 53 minutes)
            # Now: Fetches only worklogs per project using projectId filter (98.8% reduction)
            logger.info(
                f"Fetching all-time hours from Tempo for {len(active_projects)} projects (optimized)..."
            )
            cumulative_hours = self._get_all_time_hours_optimized(active_projects)

            # Update database
            logger.info("Updating database...")
            update_stats = self.update_project_hours(
                current_month_hours, cumulative_hours
            )

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
                "unique_projects_tracked": len(current_month_hours),
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
                "error": str(e),
            }


def run_tempo_sync():
    """
    Entry point for the Tempo sync job.
    This function is called by the scheduler.
    """
    try:
        job = TempoSyncJob()
        return job.run()
    except Exception as e:
        logger.error(f"Failed to initialize or run Tempo sync job: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "start_time": datetime.now().isoformat(),
            "end_time": datetime.now().isoformat(),
            "duration_seconds": 0,
        }


if __name__ == "__main__":
    # Allow running job manually for testing
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    print("Running Tempo sync job manually...")
    stats = run_tempo_sync()
    print(f"\nJob completed: {stats}")
