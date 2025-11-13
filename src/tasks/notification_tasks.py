"""Celery tasks for scheduled notifications and digests."""

import asyncio
import logging
import os
from celery import shared_task
from src.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@shared_task(name="src.tasks.notification_tasks.send_daily_digest", bind=True)
def send_daily_digest(self):
    """
    Send daily TODO digest (Celery task wrapper).
    Scheduled to run at 9 AM EST (14:00 UTC during DST).
    """
    from src.services.job_execution_tracker import track_celery_task
    from src.utils.database import get_db

    logger.info("📧 Starting daily digest task...")
    db = next(get_db())

    try:
        tracker = track_celery_task(self, db, "daily-todo-digest")
        with tracker:
            from src.services.scheduler import TodoScheduler

            scheduler = TodoScheduler()
            asyncio.run(scheduler.send_daily_digest())
            logger.info("✅ Daily digest completed")

            result = {"success": True, "task": "daily_digest"}
            tracker.set_result(result)
            return result
    except Exception as e:
        logger.error(f"❌ Error in daily digest task: {e}", exc_info=True)
        raise
    finally:
        db.close()


@shared_task(name="src.tasks.notification_tasks.send_overdue_reminders", bind=True)
def send_overdue_reminders(self):
    """
    Send overdue TODO reminders (Celery task wrapper).
    Scheduled to run at 10 AM and 2 PM EST.
    """
    from src.services.job_execution_tracker import track_celery_task
    from src.utils.database import get_db

    logger.info("⚠️  Starting overdue reminders task...")
    db = next(get_db())

    try:
        tracker = track_celery_task(self, db, "overdue-reminders")
        with tracker:
            from src.services.scheduler import TodoScheduler

            scheduler = TodoScheduler()
            asyncio.run(scheduler.send_overdue_reminders())
            logger.info("✅ Overdue reminders completed")

            result = {"success": True, "task": "overdue_reminders"}
            tracker.set_result(result)
            return result
    except Exception as e:
        logger.error(f"❌ Error in overdue reminders task: {e}", exc_info=True)
        raise
    finally:
        db.close()


@shared_task(name="src.tasks.notification_tasks.send_due_today_reminders", bind=True)
def send_due_today_reminders(self):
    """
    Send reminders for TODOs due today (Celery task wrapper).
    Scheduled to run at 9:30 AM EST.
    """
    from src.services.job_execution_tracker import track_celery_task
    from src.utils.database import get_db

    logger.info("📅 Starting due today reminders task...")
    db = next(get_db())

    try:
        tracker = track_celery_task(self, db, "due-today-reminders")
        with tracker:
            from src.services.scheduler import TodoScheduler

            scheduler = TodoScheduler()
            asyncio.run(scheduler.send_due_today_reminders())
            logger.info("✅ Due today reminders completed")

            result = {"success": True, "task": "due_today_reminders"}
            tracker.set_result(result)
            return result
    except Exception as e:
        logger.error(f"❌ Error in due today reminders task: {e}", exc_info=True)
        raise
    finally:
        db.close()


@shared_task(name="src.tasks.notification_tasks.send_weekly_summary", bind=True)
def send_weekly_summary(self):
    """
    Send weekly TODO summary (Celery task wrapper).
    Scheduled to run on Mondays at 9 AM EST.
    """
    from src.services.job_execution_tracker import track_celery_task
    from src.utils.database import get_db

    logger.info("📊 Starting weekly summary task...")
    db = next(get_db())

    try:
        tracker = track_celery_task(self, db, "weekly-summary")
        with tracker:
            from src.services.scheduler import TodoScheduler

            scheduler = TodoScheduler()
            asyncio.run(scheduler.send_weekly_summary())
            logger.info("✅ Weekly summary completed")

            result = {"success": True, "task": "weekly_summary"}
            tracker.set_result(result)
            return result
    except Exception as e:
        logger.error(f"❌ Error in weekly summary task: {e}", exc_info=True)
        raise
    finally:
        db.close()


@shared_task(name="src.tasks.notification_tasks.send_weekly_hours_reports", bind=True)
def send_weekly_hours_reports(self):
    """
    Send weekly hours tracking reports (Celery task wrapper).
    Scheduled to run on Mondays at 10 AM EST.
    """
    from src.services.job_execution_tracker import track_celery_task
    from src.utils.database import get_db

    logger.info("📈 Starting weekly hours reports task...")
    db = next(get_db())

    try:
        tracker = track_celery_task(self, db, "weekly-hours-reports")
        with tracker:
            from src.services.scheduler import TodoScheduler

            scheduler = TodoScheduler()
            asyncio.run(scheduler.send_weekly_hours_reports())
            logger.info("✅ Weekly hours reports completed")

            result = {"success": True, "task": "weekly_hours_reports"}
            tracker.set_result(result)
            return result
    except Exception as e:
        logger.error(f"❌ Error in weekly hours reports task: {e}", exc_info=True)
        raise
    finally:
        db.close()


@shared_task(name="src.tasks.notification_tasks.check_urgent_items", bind=True)
def check_urgent_items(self):
    """
    Check for urgent items needing immediate attention (Celery task wrapper).
    Scheduled to run every 2 hours during work hours.
    """
    from src.services.job_execution_tracker import track_celery_task
    from src.utils.database import get_db

    logger.info("🚨 Starting urgent items check...")
    db = next(get_db())

    try:
        tracker = track_celery_task(self, db, "check-urgent-items")
        with tracker:
            from src.services.scheduler import TodoScheduler

            scheduler = TodoScheduler()
            asyncio.run(scheduler.check_urgent_items())
            logger.info("✅ Urgent items check completed")

            result = {"success": True, "task": "urgent_items_check"}
            tracker.set_result(result)
            return result
    except Exception as e:
        logger.error(f"❌ Error in urgent items check: {e}", exc_info=True)
        raise
    finally:
        db.close()


@shared_task(
    name="src.tasks.notification_tasks.sync_tempo_hours",
    bind=True,  # Bind task instance to get retry info
    autoretry_for=(Exception,),  # Auto-retry on any exception
    retry_kwargs={
        "max_retries": 3,
        "countdown": 300,
    },  # Retry 3 times, wait 5 min between retries
    retry_backoff=True,  # Exponential backoff
    retry_backoff_max=1800,  # Max 30 min backoff
    retry_jitter=True,  # Add jitter to prevent thundering herd
)
def sync_tempo_hours(self):
    """
    Sync Tempo hours to database (Celery task wrapper).
    Scheduled to run at 4 AM EST (8:00 UTC).

    Resilience features:
    - Auto-retry up to 3 times with exponential backoff
    - 5-minute initial wait, up to 30-minute max backoff
    - Jitter to prevent simultaneous retries
    """
    from src.services.job_execution_tracker import track_celery_task
    from src.utils.database import get_db

    retry_info = (
        f" (attempt {self.request.retries + 1}/4)" if self.request.retries > 0 else ""
    )
    logger.info(f"⏰ Starting Tempo hours sync task{retry_info}...")

    db = next(get_db())
    try:
        tracker = track_celery_task(self, db, "tempo-sync-daily")
        with tracker:
            from src.services.scheduler import TodoScheduler

            scheduler = TodoScheduler()
            scheduler.sync_tempo_hours()
            logger.info("✅ Tempo hours sync completed")

            result = {
                "success": True,
                "task": "tempo_sync",
                "retries": self.request.retries,
            }
            tracker.set_result(result)
            return result
    except Exception as e:
        logger.error(
            f"❌ Error in Tempo sync task (attempt {self.request.retries + 1}/4): {e}",
            exc_info=True,
        )
        # Re-raise to trigger auto-retry
        raise
    finally:
        db.close()


@shared_task(
    name="src.tasks.notification_tasks.sync_project_epic_hours",
    bind=True,  # Bind task instance to get retry info
    autoretry_for=(Exception,),  # Auto-retry on any exception
    retry_kwargs={
        "max_retries": 2,
        "countdown": 180,
    },  # Retry 2 times, wait 3 min between retries
    retry_backoff=True,  # Exponential backoff
    retry_backoff_max=900,  # Max 15 min backoff
    retry_jitter=True,  # Add jitter to prevent thundering herd
)
def sync_project_epic_hours(self, project_key):
    """
    Sync epic hours for a specific project from Tempo (Celery task).

    This task extracts the logic from the /api/jira/projects/<key>/sync-hours endpoint
    to run it reliably via Celery instead of a daemon thread.

    Args:
        project_key: The Jira project key to sync (e.g., 'RNWL')

    Resilience features:
    - Auto-retry up to 2 times with exponential backoff
    - 3-minute initial wait, up to 15-minute max backoff
    - Jitter to prevent simultaneous retries
    """
    try:
        from datetime import datetime, date
        from collections import defaultdict
        from src.integrations.tempo import TempoAPIClient
        from src.models import EpicHours, EpicCategoryMapping
        from src.utils.database import get_session
        from sqlalchemy.dialects.postgresql import insert
        from sqlalchemy import text

        retry_info = (
            f" (attempt {self.request.retries + 1}/3)"
            if self.request.retries > 0
            else ""
        )
        logger.info(f"⏰ Starting epic hours sync for {project_key}{retry_info}...")

        tempo = TempoAPIClient()
        session = get_session()

        # Load epic category mappings for lookup during insertion
        category_mappings = {}
        for mapping in session.query(EpicCategoryMapping).all():
            category_mappings[mapping.epic_key] = mapping.category
        logger.info(f"Loaded {len(category_mappings)} epic category mappings")

        try:
            # Fetch worklogs for last 2+ years
            start_date = "2023-01-01"
            end_date = datetime.now().strftime("%Y-%m-%d")

            logger.info(
                f"Fetching worklogs for {project_key} from {start_date} to {end_date}"
            )
            worklogs = tempo.get_worklogs(
                from_date=start_date, to_date=end_date, project_key=project_key
            )

            if not worklogs:
                logger.warning(f"No worklogs found for {project_key}")
                session.close()
                return {
                    "success": True,
                    "project_key": project_key,
                    "records": 0,
                    "message": "No worklogs found",
                }

            total_worklogs = len(worklogs)
            logger.info(f"Found {total_worklogs} worklogs for {project_key}")

            # Update progress: fetching complete
            self.update_state(
                state="PROGRESS",
                meta={
                    "current": 0,
                    "total": total_worklogs,
                    "message": f"Fetched {total_worklogs} worklogs, starting to process...",
                },
            )

            # Group by epic → month → team
            epic_month_team_hours = defaultdict(
                lambda: defaultdict(lambda: defaultdict(float))
            )
            processed = 0
            skipped = 0

            # Issue key pattern: PROJECT-NUMBER (e.g., RNWL-123)
            import re

            issue_pattern = re.compile(r"([A-Z]+-\d+)")

            for idx, worklog in enumerate(worklogs):
                # Update progress every 50 worklogs (show progress even when skipping)
                if (idx + 1) % 50 == 0 or (idx + 1) == total_worklogs:
                    percent = round(((idx + 1) / total_worklogs) * 100, 1)
                    self.update_state(
                        state="PROGRESS",
                        meta={
                            "current": idx + 1,
                            "total": total_worklogs,
                            "message": f"Processing worklogs... {idx + 1}/{total_worklogs} ({percent}%)",
                        },
                    )

                issue = worklog.get("issue", {})
                issue_id = issue.get("id")
                if not issue_id:
                    skipped += 1
                    continue

                # OPTIMIZATION: Get epic FIRST to filter by project early (avoids API calls)
                epic_key = None
                attributes = worklog.get("attributes", {})
                if attributes:
                    values = attributes.get("values", [])
                    for attr in values:
                        if attr.get("key") == "_Epic_":
                            epic_key = attr.get("value")
                            break

                # Early filtering: If epic has project info and doesn't match, skip without API call
                if epic_key and epic_key != "NO_EPIC" and "-" in epic_key:
                    epic_project = epic_key.split("-")[0]
                    if epic_project != project_key:
                        # Not our project, skip this worklog entirely (saves Jira API call!)
                        skipped += 1
                        continue

                # Get issue key (needed for worklogs without epic or to double-check project)
                issue_key = None
                description = worklog.get("description", "")

                # Fast path: Extract from description
                issue_match = issue_pattern.search(description)
                if issue_match:
                    issue_key = issue_match.group(1)
                else:
                    # Fallback: Jira API lookup (slow but accurate)
                    issue_key = tempo.get_issue_key_from_jira(issue_id)

                if not issue_key:
                    skipped += 1
                    continue

                # Validate project from issue_key (for worklogs without epic or with NO_EPIC)
                project_from_key = issue_key.split("-")[0] if "-" in issue_key else None
                if project_from_key != project_key:
                    # Not our project after all
                    skipped += 1
                    continue

                # Get epic from Jira if not found in Tempo attributes
                if not epic_key:
                    epic_key = tempo.get_epic_from_jira(issue_key)
                    if not epic_key:
                        epic_key = "NO_EPIC"

                # Get month
                started = worklog.get("startDate")
                if not started:
                    skipped += 1
                    continue

                worklog_date = datetime.strptime(started[:10], "%Y-%m-%d").date()
                month = date(worklog_date.year, worklog_date.month, 1)

                # Get hours
                time_spent_seconds = worklog.get("timeSpentSeconds", 0)
                hours = time_spent_seconds / 3600.0

                # Get team
                author = worklog.get("author", {})
                account_id = author.get("accountId")
                if account_id:
                    team = tempo.get_user_team(account_id)
                    if not team or team == "Unassigned":
                        team = "Other"
                else:
                    team = "Other"

                # Accumulate
                epic_month_team_hours[epic_key][month][team] += hours
                processed += 1

            logger.info(
                f"Processed {processed} worklogs for {project_key}, skipped {skipped}"
            )

            # Update progress: processing complete, now saving to database
            self.update_state(
                state="PROGRESS",
                meta={
                    "current": total_worklogs,
                    "total": total_worklogs,
                    "message": "Saving to database...",
                },
            )

            # Delete all existing epic_hours records for this project before inserting fresh data
            # This ensures we don't accumulate stale records from renamed epics or changed Tempo data
            delete_result = session.execute(
                text("DELETE FROM epic_hours WHERE project_key = :project_key"),
                {"project_key": project_key},
            )
            delete_count = delete_result.rowcount
            session.commit()
            logger.info(
                f"Deleted {delete_count} existing epic_hours records for {project_key}"
            )

            # Insert into database
            records_inserted = 0
            for epic_key, months in epic_month_team_hours.items():
                # Look up category for this epic (if mapped)
                epic_category = category_mappings.get(epic_key)

                for month, teams in months.items():
                    for team, hours in teams.items():
                        if hours > 0:
                            stmt = insert(EpicHours).values(
                                project_key=project_key,
                                epic_key=epic_key,
                                epic_summary=epic_key,
                                epic_category=epic_category,  # Populated from mappings (or None)
                                month=month,
                                team=team,
                                hours=round(hours, 2),
                                created_at=datetime.now(),
                                updated_at=datetime.now(),
                            )
                            stmt = stmt.on_conflict_do_update(
                                index_elements=[
                                    "project_key",
                                    "epic_key",
                                    "month",
                                    "team",
                                ],
                                set_={
                                    "hours": stmt.excluded.hours,
                                    "epic_category": stmt.excluded.epic_category,  # Update category on conflict
                                    "updated_at": datetime.now(),
                                },
                            )
                            session.execute(stmt)
                            records_inserted += 1

            session.commit()
            logger.info(
                f"✅ Successfully synced {records_inserted} epic hours records for {project_key}"
            )

            return {
                "success": True,
                "project_key": project_key,
                "records": records_inserted,
                "processed": processed,
                "skipped": skipped,
                "retries": self.request.retries,
            }

        finally:
            session.close()

    except Exception as e:
        logger.error(
            f"❌ Error in epic hours sync for {project_key} (attempt {self.request.retries + 1}/3): {e}",
            exc_info=True,
        )
        # Re-raise to trigger auto-retry
        raise


@celery_app.task(
    name="src.tasks.notification_tasks.import_historical_epic_hours",
    bind=True,  # Bind task instance to get retry info
    autoretry_for=(Exception,),  # Auto-retry on any exception
    retry_kwargs={
        "max_retries": 2,
        "countdown": 300,
    },  # Retry 2 times, wait 5 min between retries
    retry_backoff=True,  # Exponential backoff
    retry_backoff_max=1800,  # Max 30 min backoff
    retry_jitter=True,  # Add jitter to prevent thundering herd
)
def import_historical_epic_hours(
    self,
    project_key,
    start_date,
    end_date,
    characteristics,
    include_in_forecasting=True,
):
    """
    Import historical epic hours for a project from Tempo (Celery task).

    This task is used to backfill historical data for forecasting model training.
    Unlike sync_project_epic_hours, this:
    - Accepts custom date range
    - Uses AI to categorize epics
    - Saves project characteristics
    - Saves forecasting date range configuration
    - Appends data (doesn't delete existing records)

    Args:
        project_key: The Jira project key to import (e.g., 'RNWL')
        start_date: Start date for import (YYYY-MM-DD)
        end_date: End date for import (YYYY-MM-DD)
        characteristics: Dict with project characteristics (1-5 scale):
            - be_integrations
            - custom_theme
            - custom_designs
            - ux_research
            - extensive_customizations
            - project_oversight
        include_in_forecasting: Whether to include this project in forecasting models (default: True)

    Resilience features:
    - Auto-retry up to 2 times with exponential backoff
    - 5-minute initial wait, up to 30-minute max backoff
    - Jitter to prevent simultaneous retries
    """
    try:
        from datetime import datetime, date
        from collections import defaultdict
        from src.integrations.tempo import TempoAPIClient
        from src.models import EpicHours, EpicCategoryMapping, ProjectForecastingConfig
        from src.models.project import ProjectCharacteristics
        from src.utils.database import get_session
        from src.services.epic_categorizer import EpicCategorizer
        from sqlalchemy.dialects.postgresql import insert
        from sqlalchemy import text, func

        retry_info = (
            f" (attempt {self.request.retries + 1}/3)"
            if self.request.retries > 0
            else ""
        )
        logger.info(
            f"🔄 Starting historical epic hours import for {project_key} ({start_date} to {end_date}){retry_info}..."
        )

        tempo = TempoAPIClient()
        session = get_session()

        try:
            # Initialize AI categorizer
            categorizer = EpicCategorizer(session)

            # Fetch worklogs for specified date range
            logger.info(
                f"Fetching worklogs for {project_key} from {start_date} to {end_date}"
            )
            worklogs = tempo.get_worklogs(
                from_date=start_date, to_date=end_date, project_key=project_key
            )

            if not worklogs:
                logger.warning(
                    f"No worklogs found for {project_key} in the specified date range"
                )
                session.close()
                return {
                    "success": True,
                    "project_key": project_key,
                    "epic_count": 0,
                    "records": 0,
                    "message": "No worklogs found in date range",
                }

            total_worklogs = len(worklogs)
            logger.info(f"Found {total_worklogs} worklogs for {project_key}")

            # Update progress: fetching complete
            self.update_state(
                state="PROGRESS",
                meta={
                    "current": 0,
                    "total": total_worklogs,
                    "message": f"Fetched {total_worklogs} worklogs, starting to process...",
                },
            )

            # Group by epic → month → team
            epic_month_team_hours = defaultdict(
                lambda: defaultdict(lambda: defaultdict(float))
            )
            epic_summaries = {}  # Store epic summaries for AI categorization
            processed = 0
            skipped = 0

            # Issue key pattern: PROJECT-NUMBER (e.g., RNWL-123)
            import re

            issue_pattern = re.compile(r"([A-Z]+-\d+)")

            for idx, worklog in enumerate(worklogs):
                # Update progress every 50 worklogs
                if (idx + 1) % 50 == 0 or (idx + 1) == total_worklogs:
                    percent = round(((idx + 1) / total_worklogs) * 100, 1)
                    self.update_state(
                        state="PROGRESS",
                        meta={
                            "current": idx + 1,
                            "total": total_worklogs,
                            "message": f"Processing worklogs... {idx + 1}/{total_worklogs} ({percent}%)",
                        },
                    )

                issue = worklog.get("issue", {})
                issue_id = issue.get("id")
                if not issue_id:
                    skipped += 1
                    continue

                # Get epic key from Tempo attributes
                epic_key = None
                attributes = worklog.get("attributes", {})
                if attributes:
                    values = attributes.get("values", [])
                    for attr in values:
                        if attr.get("key") == "_Epic_":
                            epic_key = attr.get("value")
                            break

                # Early filtering: If epic has project info and doesn't match, skip
                if epic_key and epic_key != "NO_EPIC" and "-" in epic_key:
                    epic_project = epic_key.split("-")[0]
                    if epic_project != project_key:
                        skipped += 1
                        continue

                # Get issue key
                issue_key = None
                description = worklog.get("description", "")

                # Fast path: Extract from description
                issue_match = issue_pattern.search(description)
                if issue_match:
                    issue_key = issue_match.group(1)
                else:
                    # Fallback: Jira API lookup
                    issue_key = tempo.get_issue_key_from_jira(issue_id)

                if not issue_key:
                    skipped += 1
                    continue

                # Validate project from issue_key
                project_from_key = issue_key.split("-")[0] if "-" in issue_key else None
                if project_from_key != project_key:
                    skipped += 1
                    continue

                # Get epic from Jira if not found in Tempo attributes
                if not epic_key:
                    epic_key = tempo.get_epic_from_jira(issue_key)
                    if not epic_key:
                        epic_key = "NO_EPIC"

                # Get epic summary for AI categorization (fetch once per epic)
                if epic_key not in epic_summaries and epic_key != "NO_EPIC":
                    epic_data = tempo.get_epic_details_from_jira(epic_key)
                    if epic_data:
                        epic_summaries[epic_key] = epic_data.get("summary", epic_key)
                    else:
                        epic_summaries[epic_key] = epic_key

                # Get month
                started = worklog.get("startDate")
                if not started:
                    skipped += 1
                    continue

                worklog_date = datetime.strptime(started[:10], "%Y-%m-%d").date()
                month = date(worklog_date.year, worklog_date.month, 1)

                # Get hours
                time_spent_seconds = worklog.get("timeSpentSeconds", 0)
                hours = time_spent_seconds / 3600.0

                # Get team
                author = worklog.get("author", {})
                account_id = author.get("accountId")
                if account_id:
                    team = tempo.get_user_team(account_id)
                    if not team or team == "Unassigned":
                        team = "Other"
                else:
                    team = "Other"

                # Accumulate
                epic_month_team_hours[epic_key][month][team] += hours
                processed += 1

            logger.info(
                f"Processed {processed} worklogs for {project_key}, skipped {skipped}"
            )

            # Update progress: AI categorization phase
            epic_count = len(epic_month_team_hours)
            self.update_state(
                state="PROGRESS",
                meta={
                    "current": total_worklogs,
                    "total": total_worklogs,
                    "message": f"Categorizing {epic_count} epics with AI...",
                },
            )

            # Categorize epics with AI
            logger.info(f"Categorizing {epic_count} epics with AI")
            epic_categories = {}
            for epic_key in epic_month_team_hours.keys():
                if epic_key == "NO_EPIC":
                    epic_categories[epic_key] = "Uncategorized"
                else:
                    epic_summary = epic_summaries.get(epic_key, epic_key)
                    category = categorizer.categorize_epic(epic_key, epic_summary)
                    epic_categories[epic_key] = category
                    logger.debug(f"Categorized {epic_key} as '{category}'")

            # Update progress: saving to database
            self.update_state(
                state="PROGRESS",
                meta={
                    "current": total_worklogs,
                    "total": total_worklogs,
                    "message": "Saving epic hours to database...",
                },
            )

            # Insert into database (append, don't delete existing)
            records_inserted = 0
            for epic_key, months in epic_month_team_hours.items():
                epic_category = epic_categories.get(epic_key)
                epic_summary = epic_summaries.get(epic_key, epic_key)

                for month, teams in months.items():
                    for team, hours in teams.items():
                        if hours > 0:
                            stmt = insert(EpicHours).values(
                                project_key=project_key,
                                epic_key=epic_key,
                                epic_summary=epic_summary,
                                epic_category=epic_category,
                                month=month,
                                team=team,
                                hours=round(hours, 2),
                                created_at=datetime.now(),
                                updated_at=datetime.now(),
                            )
                            stmt = stmt.on_conflict_do_update(
                                index_elements=[
                                    "project_key",
                                    "epic_key",
                                    "month",
                                    "team",
                                ],
                                set_={
                                    "hours": stmt.excluded.hours,
                                    "epic_summary": stmt.excluded.epic_summary,
                                    "epic_category": stmt.excluded.epic_category,
                                    "updated_at": datetime.now(),
                                },
                            )
                            session.execute(stmt)
                            records_inserted += 1

            session.commit()
            logger.info(
                f"Inserted/updated {records_inserted} epic hours records for {project_key}"
            )

            # Ensure project exists in projects table before saving characteristics
            from src.models.project import Project

            project = session.query(Project).filter_by(key=project_key).first()
            if not project:
                # Create project record if it doesn't exist
                project = Project(
                    key=project_key,
                    name=project_key,  # Will be updated when full project sync runs
                )
                session.add(project)
                session.commit()
                logger.info(f"Created project record for {project_key}")

            # Save project characteristics
            self.update_state(
                state="PROGRESS",
                meta={
                    "current": total_worklogs,
                    "total": total_worklogs,
                    "message": "Saving project characteristics...",
                },
            )

            # Check if project characteristics already exist
            existing_chars = (
                session.query(ProjectCharacteristics)
                .filter_by(project_key=project_key)
                .first()
            )

            if existing_chars:
                # Update existing
                existing_chars.be_integrations = characteristics["be_integrations"]
                existing_chars.custom_theme = characteristics["custom_theme"]
                existing_chars.custom_designs = characteristics["custom_designs"]
                existing_chars.ux_research = characteristics["ux_research"]
                existing_chars.extensive_customizations = characteristics[
                    "extensive_customizations"
                ]
                existing_chars.project_oversight = characteristics["project_oversight"]
                existing_chars.updated_at = datetime.now()
                logger.info(f"Updated project characteristics for {project_key}")
            else:
                # Create new
                new_chars = ProjectCharacteristics(
                    project_key=project_key,
                    be_integrations=characteristics["be_integrations"],
                    custom_theme=characteristics["custom_theme"],
                    custom_designs=characteristics["custom_designs"],
                    ux_research=characteristics["ux_research"],
                    extensive_customizations=characteristics[
                        "extensive_customizations"
                    ],
                    project_oversight=characteristics["project_oversight"],
                )
                session.add(new_chars)
                logger.info(f"Created project characteristics for {project_key}")

            # Save forecasting date range configuration
            logger.info(
                f"Saving forecasting config for {project_key} (date range: {start_date} to {end_date})"
            )
            existing_config = (
                session.query(ProjectForecastingConfig)
                .filter_by(project_key=project_key)
                .first()
            )

            if existing_config:
                # Update existing config
                existing_config.forecasting_start_date = datetime.strptime(
                    start_date, "%Y-%m-%d"
                ).date()
                existing_config.forecasting_end_date = datetime.strptime(
                    end_date, "%Y-%m-%d"
                ).date()
                existing_config.include_in_forecasting = include_in_forecasting
                existing_config.updated_at = datetime.now()
                logger.info(f"Updated forecasting config for {project_key}")
            else:
                # Create new config
                new_config = ProjectForecastingConfig(
                    project_key=project_key,
                    forecasting_start_date=datetime.strptime(
                        start_date, "%Y-%m-%d"
                    ).date(),
                    forecasting_end_date=datetime.strptime(end_date, "%Y-%m-%d").date(),
                    include_in_forecasting=include_in_forecasting,
                )
                session.add(new_config)
                logger.info(f"Created forecasting config for {project_key}")

            session.commit()

            # === NEW: AUTOMATED EPIC ENRICHMENT & ANALYSIS ===
            # Step 1: Enrich epic summaries from Jira (replace ticket keys with real names)
            logger.info("🔄 Step 1/3: Enriching epic summaries from Jira...")
            self.update_state(
                state="PROGRESS", meta={"message": "Enriching epic names from Jira..."}
            )

            from src.services.epic_enrichment_service import EpicEnrichmentService

            enrichment_service = EpicEnrichmentService(session)
            enrichment_result = enrichment_service.enrich_project_epics(project_key)

            if enrichment_result["success"]:
                logger.info(
                    f"✅ Enriched {enrichment_result['enriched_count']} epics "
                    f"({enrichment_result['records_updated']} records updated)"
                )
            else:
                logger.warning(
                    f"⚠️ Enrichment failed: {enrichment_result.get('error', 'Unknown error')}"
                )

            # Step 2: Run AI grouping analysis (create canonical categories)
            logger.info("🔄 Step 2/3: Analyzing epic groupings with AI...")
            self.update_state(
                state="PROGRESS",
                meta={"message": "Analyzing epic groupings with AI..."},
            )

            from src.services.epic_analysis_service import EpicAnalysisService

            analysis_service = EpicAnalysisService(session)
            analysis_result = analysis_service.analyze_and_group_epics()

            if analysis_result["success"]:
                logger.info(
                    f"✅ Created {analysis_result['total_categories']} canonical categories "
                    f"from {analysis_result['total_epics']} epics"
                )
            else:
                logger.warning(
                    f"⚠️ Analysis failed: {analysis_result.get('error', 'Unknown error')}"
                )

            # Step 3: Regenerate baselines (update forecasting data)
            logger.info("🔄 Step 3/3: Regenerating epic baselines...")
            self.update_state(
                state="PROGRESS", meta={"message": "Regenerating epic baselines..."}
            )

            from scripts.generate_epic_baselines import generate_baselines

            try:
                baseline_result = generate_baselines()
                logger.info(f"✅ Generated {len(baseline_result)} epic baselines")
                baseline_count = len(baseline_result)
            except Exception as baseline_error:
                logger.error(
                    f"⚠️ Baseline generation failed: {baseline_error}", exc_info=True
                )
                baseline_count = 0

            logger.info(f"✅ Successfully imported historical data for {project_key}")

            # Calculate team breakdown percentages
            team_breakdown = {}
            total_hours = (
                session.query(func.sum(EpicHours.hours))
                .filter(EpicHours.project_key == project_key)
                .scalar()
                or 0
            )

            if total_hours > 0:
                team_stats = (
                    session.query(
                        EpicHours.team, func.sum(EpicHours.hours).label("hours")
                    )
                    .filter(EpicHours.project_key == project_key)
                    .group_by(EpicHours.team)
                    .all()
                )

                for team, hours in team_stats:
                    percentage = round((hours / total_hours) * 100, 1)
                    team_breakdown[team] = {
                        "hours": round(hours, 2),
                        "percentage": percentage,
                    }

            # Calculate epic category breakdown percentages
            category_breakdown = {}
            if total_hours > 0:
                category_stats = (
                    session.query(
                        EpicHours.epic_category,
                        func.sum(EpicHours.hours).label("hours"),
                    )
                    .filter(EpicHours.project_key == project_key)
                    .group_by(EpicHours.epic_category)
                    .all()
                )

                for category, hours in category_stats:
                    percentage = round((hours / total_hours) * 100, 1)
                    category_breakdown[category or "Uncategorized"] = {
                        "hours": round(hours, 2),
                        "percentage": percentage,
                    }

            return {
                "success": True,
                "project_key": project_key,
                "date_range": f"{start_date} to {end_date}",
                "epic_count": epic_count,
                "records": records_inserted,
                "processed": processed,
                "skipped": skipped,
                "retries": self.request.retries,
                # NEW: Team breakdown
                "team_breakdown": team_breakdown,
                # NEW: Epic category breakdown
                "category_breakdown": category_breakdown,
                # Enrichment & analysis stats
                "enrichment": {
                    "success": enrichment_result.get("success", False),
                    "enriched_count": enrichment_result.get("enriched_count", 0),
                    "records_updated": enrichment_result.get("records_updated", 0),
                },
                "analysis": {
                    "success": analysis_result.get("success", False),
                    "total_categories": analysis_result.get("total_categories", 0),
                    "total_epics": analysis_result.get("total_epics", 0),
                },
                "baselines": {
                    "count": baseline_count,
                },
            }

        finally:
            session.close()

    except Exception as e:
        logger.error(
            f"❌ Error in historical import for {project_key} (attempt {self.request.retries + 1}/3): {e}",
            exc_info=True,
        )
        # Re-raise to trigger auto-retry
        raise


@shared_task(
    name="src.tasks.notification_tasks.regenerate_epic_baselines_monthly",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={
        "max_retries": 2,
        "countdown": 300,
    },  # Retry 2 times, wait 5 min between retries
    retry_backoff=True,
    retry_backoff_max=1800,  # Max 30 min backoff
    retry_jitter=True,
)
def regenerate_epic_baselines_monthly(self):
    """
    Monthly task to regenerate epic baselines with latest data.
    Scheduled to run on the 3rd of each month at 9:30 AM EST (13:30 UTC).

    This task:
    1. Enriches all epic summaries from Jira
    2. Runs AI grouping analysis
    3. Regenerates all epic baselines
    4. Sends Slack notification with results

    Resilience features:
    - Auto-retry up to 2 times with exponential backoff
    - 5-minute initial wait, up to 30-minute max backoff
    - Jitter to prevent simultaneous retries
    """
    from src.utils.database import get_session
    from src.services.epic_enrichment_service import EpicEnrichmentService
    from src.services.epic_analysis_service import EpicAnalysisService
    from scripts.generate_epic_baselines import generate_baselines
    from src.integrations.slack import SlackBot

    retry_info = (
        f" (attempt {self.request.retries + 1}/3)" if self.request.retries > 0 else ""
    )
    logger.info(f"🔄 Starting monthly epic baseline regeneration{retry_info}...")

    session = get_session()
    results = {
        "enrichment": {},
        "analysis": {},
        "baselines": {},
    }

    try:
        # Step 1: Enrich all epic summaries from Jira
        logger.info("🔄 Step 1/3: Enriching all epic summaries from Jira...")
        self.update_state(
            state="PROGRESS", meta={"message": "Enriching epic names from Jira..."}
        )

        enrichment_service = EpicEnrichmentService(session)
        enrichment_result = enrichment_service.enrich_all_epics()
        results["enrichment"] = enrichment_result

        if enrichment_result["success"]:
            logger.info(
                f"✅ Enriched {enrichment_result['enriched_count']} epics "
                f"({enrichment_result['records_updated']} records updated)"
            )
        else:
            logger.warning(
                f"⚠️ Enrichment failed: {enrichment_result.get('error', 'Unknown error')}"
            )

        # Step 2: Run AI grouping analysis
        logger.info("🔄 Step 2/3: Analyzing epic groupings with AI...")
        self.update_state(
            state="PROGRESS", meta={"message": "Analyzing epic groupings with AI..."}
        )

        analysis_service = EpicAnalysisService(session)
        analysis_result = analysis_service.analyze_and_group_epics()
        results["analysis"] = analysis_result

        if analysis_result["success"]:
            logger.info(
                f"✅ Created {analysis_result['total_categories']} canonical categories "
                f"from {analysis_result['total_epics']} epics"
            )
        else:
            logger.warning(
                f"⚠️ Analysis failed: {analysis_result.get('error', 'Unknown error')}"
            )

        # Step 3: Regenerate all baselines
        logger.info("🔄 Step 3/3: Regenerating all epic baselines...")
        self.update_state(
            state="PROGRESS", meta={"message": "Regenerating epic baselines..."}
        )

        try:
            baseline_result = generate_baselines()
            logger.info(f"✅ Generated {len(baseline_result)} epic baselines")
            results["baselines"] = {
                "success": True,
                "count": len(baseline_result),
            }
        except Exception as baseline_error:
            logger.error(
                f"⚠️ Baseline generation failed: {baseline_error}", exc_info=True
            )
            results["baselines"] = {
                "success": False,
                "error": str(baseline_error),
                "count": 0,
            }

        # Send Slack notification
        try:
            slack_bot = SlackBot()
            message = (
                "📊 *Monthly Epic Baseline Regeneration Complete*\n\n"
                f"*Enrichment:* {enrichment_result.get('enriched_count', 0)} epics enriched "
                f"({enrichment_result.get('records_updated', 0)} records updated)\n"
                f"*Analysis:* {analysis_result.get('total_categories', 0)} categories created "
                f"from {analysis_result.get('total_epics', 0)} epics\n"
                f"*Baselines:* {results['baselines'].get('count', 0)} baselines generated\n\n"
                f"✅ All epic forecasting data has been refreshed!"
            )
            slack_bot.send_message(message)
            logger.info("✅ Slack notification sent")
        except Exception as slack_error:
            logger.warning(f"⚠️ Failed to send Slack notification: {slack_error}")

        logger.info("✅ Monthly epic baseline regeneration completed successfully")

        return {"success": True, "retries": self.request.retries, **results}

    except Exception as e:
        logger.error(
            f"❌ Error in monthly baseline regeneration (attempt {self.request.retries + 1}/3): {e}",
            exc_info=True,
        )
        # Re-raise to trigger auto-retry
        raise

    finally:
        session.close()


@shared_task(
    name="src.tasks.notification_tasks.analyze_meetings",
    bind=True,  # Bind task instance to get retry info
    autoretry_for=(Exception,),  # Auto-retry on any exception
    retry_kwargs={
        "max_retries": 2,
        "countdown": 600,
    },  # Retry 2 times, wait 10 min between retries
    retry_backoff=True,  # Exponential backoff
    retry_backoff_max=3600,  # Max 60 min backoff
    retry_jitter=True,  # Add jitter to prevent thundering herd
)
def analyze_meetings(self):
    """
    Analyze meetings from active projects (Celery task wrapper).
    Scheduled to run at 7 AM UTC (3 AM EST).

    Resilience features:
    - Auto-retry up to 2 times with exponential backoff
    - 10-minute initial wait, up to 60-minute max backoff
    - Jitter to prevent simultaneous retries
    """
    try:
        retry_info = (
            f" (attempt {self.request.retries + 1}/3)"
            if self.request.retries > 0
            else ""
        )
        logger.info(f"🔍 Starting meeting analysis sync task{retry_info}...")
        from src.jobs.meeting_analysis_sync import run_meeting_analysis_sync

        stats = run_meeting_analysis_sync()

        if stats.get("success"):
            logger.info(
                f"✅ Meeting analysis completed: {stats.get('meetings_analyzed', 0)} meetings analyzed"
            )
            return {
                "success": True,
                "task": "meeting_analysis",
                "retries": self.request.retries,
                **stats,
            }
        else:
            error_msg = stats.get("error", "Unknown error")
            logger.error(f"❌ Meeting analysis failed: {error_msg}")
            raise Exception(f"Meeting analysis failed: {error_msg}")

    except Exception as e:
        logger.error(
            f"❌ Error in meeting analysis task (attempt {self.request.retries + 1}/3): {e}",
            exc_info=True,
        )
        # Re-raise to trigger auto-retry
        raise


# ========== Proactive Agent Tasks (Migrated from Python Scheduler) ==========


@shared_task(name="src.tasks.notification_tasks.detect_proactive_insights", bind=True)
def detect_proactive_insights(self):
    """
    Run proactive insight detection for all users (Celery task wrapper).
    Scheduled to run every 4 hours during work hours (8am, 12pm, 4pm EST).

    Migrated from Python scheduler to Celery Beat for better reliability.
    """
    from src.services.job_execution_tracker import track_celery_task
    from src.utils.database import get_db

    logger.info("🔍 Starting proactive insight detection task...")
    db = next(get_db())

    try:
        tracker = track_celery_task(self, db, "proactive-insights")
        with tracker:
            from src.services.insight_detector import detect_insights_for_all_users
            from src.managers.notifications import NotificationManager
            from config.settings import settings

            stats = detect_insights_for_all_users()
            logger.info(f"✅ Insight detection complete: {stats}")

            # Send Slack notification if insights detected
            if stats["insights_detected"] > 0:
                try:
                    notifier = NotificationManager(settings.notifications)
                    message = (
                        f"🔍 *Proactive Insight Detection Complete*\n\n"
                        f"• Users processed: {stats['users_processed']}\n"
                        f"• Insights detected: {stats['insights_detected']}\n"
                        f"• Insights stored: {stats['insights_stored']}\n"
                    )
                    if stats.get("errors"):
                        message += f"• Errors: {len(stats['errors'])}\n"

                    asyncio.run(
                        notifier._send_slack_message(
                            channel=settings.notifications.slack_channel,
                            message=message,
                        )
                    )
                except Exception as notif_error:
                    logger.error(
                        f"Error sending insight detection notification: {notif_error}"
                    )

            result = {"success": True, "task": "proactive_insights", **stats}
            tracker.set_result(result)
            return result

    except Exception as e:
        logger.error(
            f"❌ Error in proactive insight detection task: {e}", exc_info=True
        )
        raise
    finally:
        db.close()


@shared_task(name="src.tasks.notification_tasks.send_daily_briefs", bind=True)
def send_daily_briefs(self):
    """
    Send daily briefs to all users (Celery task wrapper).
    Scheduled to run at 9 AM EST (primary delivery).

    Migrated from Python scheduler to Celery Beat for better reliability.
    """
    from src.services.job_execution_tracker import track_celery_task
    from src.utils.database import get_db

    logger.info("📬 Starting daily brief delivery task...")
    db = next(get_db())

    try:
        tracker = track_celery_task(self, db, "daily-briefs")
        with tracker:
            from src.services.daily_brief_generator import (
                send_daily_briefs as send_briefs_func,
            )
            from src.managers.notifications import NotificationManager
            from config.settings import settings

            stats = send_briefs_func()
            logger.info(f"✅ Daily brief delivery complete: {stats}")

            # Send Slack notification if briefs sent
            if stats["briefs_sent_slack"] > 0 or stats["briefs_sent_email"] > 0:
                try:
                    notifier = NotificationManager(settings.notifications)
                    message = (
                        f"📬 *Daily Brief Delivery Complete*\n\n"
                        f"• Users processed: {stats['users_processed']}\n"
                        f"• Briefs sent via Slack: {stats['briefs_sent_slack']}\n"
                        f"• Briefs sent via Email: {stats['briefs_sent_email']}\n"
                        f"• Total insights delivered: {stats['total_insights_delivered']}\n"
                    )
                    if stats.get("errors"):
                        message += f"• Errors: {len(stats['errors'])}\n"

                    asyncio.run(
                        notifier._send_slack_message(
                            channel=settings.notifications.slack_channel,
                            message=message,
                        )
                    )
                except Exception as notif_error:
                    logger.error(
                        f"Error sending daily brief notification: {notif_error}"
                    )

            result = {"success": True, "task": "daily_briefs", **stats}
            tracker.set_result(result)
            return result

    except Exception as e:
        logger.error(f"❌ Error in daily brief delivery task: {e}", exc_info=True)
        raise
    finally:
        db.close()


@shared_task(name="src.tasks.notification_tasks.run_auto_escalation", bind=True)
def run_auto_escalation(self):
    """
    Run auto-escalation check for stale insights (Celery task wrapper).
    Scheduled to run every 6 hours (6am, 12pm, 6pm, 12am EST).

    Migrated from Python scheduler to Celery Beat for better reliability.
    """
    from src.services.job_execution_tracker import track_celery_task
    from src.utils.database import get_db

    logger.info("🚨 Starting auto-escalation check task...")
    db = next(get_db())

    try:
        tracker = track_celery_task(self, db, "auto-escalation")
        with tracker:
            from src.services.auto_escalation import AutoEscalationService
            from src.utils.database import session_scope
            from src.managers.notifications import NotificationManager
            from config.settings import settings

            with session_scope() as escalation_db:
                escalation_service = AutoEscalationService(escalation_db)
                stats = escalation_service.run_escalation_check()

            logger.info(f"✅ Auto-escalation check complete: {stats}")

            # Send Slack notification if escalations performed
            if stats["escalations_performed"] > 0:
                try:
                    notifier = NotificationManager(settings.notifications)
                    message = (
                        f"🚨 *Auto-Escalation Summary*\n\n"
                        f"• Insights checked: {stats['total_checked']}\n"
                        f"• Escalations performed: {stats['escalations_performed']}\n"
                        f"• DMs sent: {stats['dm_sent']}\n"
                        f"• Channel posts: {stats['channel_posts']}\n"
                        f"• GitHub comments: {stats['github_comments']}\n"
                    )
                    if stats.get("errors", 0) > 0:
                        message += f"• Errors: {stats['errors']}\n"

                    asyncio.run(
                        notifier._send_slack_message(
                            channel=settings.notifications.slack_channel,
                            message=message,
                        )
                    )
                except Exception as notif_error:
                    logger.error(
                        f"Error sending auto-escalation notification: {notif_error}"
                    )

            result = {"success": True, "task": "auto_escalation", **stats}
            tracker.set_result(result)
            return result

    except Exception as e:
        logger.error(f"❌ Error in auto-escalation check task: {e}", exc_info=True)
        raise
    finally:
        db.close()


# ========== PM Automation Tasks (Migrated from Python Scheduler) ==========


@shared_task(
    name="src.tasks.notification_tasks.run_time_tracking_compliance", bind=True
)
def run_time_tracking_compliance(self):
    """
    Run weekly time tracking compliance check (Celery task wrapper).
    Scheduled to run on Mondays at 10 AM EST.

    Phase 1 PM Automation - migrated from Python scheduler to Celery Beat.
    """
    from src.services.job_execution_tracker import track_celery_task
    from src.utils.database import get_db

    logger.info("📊 Starting time tracking compliance check task...")
    db = next(get_db())

    try:
        tracker = track_celery_task(self, db, "time-tracking-compliance")
        with tracker:
            from src.jobs.time_tracking_compliance import (
                run_time_tracking_compliance as run_compliance_func,
            )

            stats = run_compliance_func()

            if stats.get("success"):
                logger.info(
                    f"✅ Time Tracking Compliance completed: "
                    f"{stats['total_users']} users checked, {stats['compliance_percentage']:.1f}% compliant, "
                    f"{stats['notifications_sent']} notifications sent in {stats['duration_seconds']:.2f}s"
                )
                result = {"success": True, "task": "time_tracking_compliance", **stats}
                tracker.set_result(result)
                return result
            else:
                error_msg = stats.get("error", "Unknown error")
                logger.error(f"❌ Time Tracking Compliance failed: {error_msg}")
                raise Exception(f"Time tracking compliance failed: {error_msg}")

    except Exception as e:
        logger.error(f"❌ Error in time tracking compliance task: {e}", exc_info=True)
        raise
    finally:
        db.close()


@shared_task(
    name="src.tasks.notification_tasks.run_monthly_epic_reconciliation", bind=True
)
def run_monthly_epic_reconciliation(self):
    """
    Run monthly epic reconciliation with epic association (Celery task wrapper).
    Scheduled to run on the 3rd of every month at 9 AM EST.

    Phase 1 PM Automation - migrated from Python scheduler to Celery Beat.
    Runs on 3rd to allow time for hours to be logged after month-end.
    """
    from datetime import datetime
    from src.services.job_execution_tracker import track_celery_task
    from src.utils.database import get_db

    # Only run on the 3rd of the month
    if datetime.now().day != 3:
        logger.info("⏭️  Skipping monthly epic reconciliation (not 3rd of month)")
        return {"success": True, "task": "monthly_epic_reconciliation", "skipped": True}

    logger.info("📈 Starting monthly epic reconciliation task (3rd of month)...")
    db = next(get_db())

    try:
        tracker = track_celery_task(self, db, "monthly-epic-reconciliation")
        with tracker:
            from src.jobs.monthly_epic_reconciliation import (
                run_monthly_epic_reconciliation as run_reconciliation_func,
            )

            stats = run_reconciliation_func()

            if stats.get("success"):
                epic_assoc = stats.get("epic_association", {})
                logger.info(
                    f"✅ Monthly Epic Reconciliation completed: "
                    f"{stats.get('projects_analyzed', 0)} projects, {stats.get('epics_processed', 0)} epics analyzed, "
                    f"variance: {stats.get('total_variance_pct', 0):.1f}%, "
                    f"epic associations: {epic_assoc.get('matches_found', 0)} matches "
                    f"({epic_assoc.get('updates_applied', 0)} applied) "
                    f"in {stats['duration_seconds']:.2f}s"
                )
                result = {
                    "success": True,
                    "task": "monthly_epic_reconciliation",
                    **stats,
                }
                tracker.set_result(result)
                return result
            else:
                error_msg = stats.get("error", "Unknown error")
                logger.error(f"❌ Monthly Epic Reconciliation failed: {error_msg}")
                raise Exception(f"Monthly epic reconciliation failed: {error_msg}")

    except Exception as e:
        logger.error(
            f"❌ Error in monthly epic reconciliation task: {e}", exc_info=True
        )
        raise
    finally:
        db.close()


# ========== Monitoring & Health Check Tasks ==========


@shared_task(name="src.tasks.notification_tasks.celery_health_check")
def celery_health_check():
    """
    Periodic Celery health check (Celery task wrapper).
    Scheduled to run every hour.

    Checks Celery worker health and sends alerts if issues detected.
    """
    try:
        logger.info("🏥 Starting Celery health check...")
        from src.tasks.celery_monitoring import (
            check_queue_health,
            send_health_check_alert,
        )

        health_status = check_queue_health()
        logger.info(f"✅ Celery health check complete: {health_status}")

        # Send alert if unhealthy
        if not health_status.get("healthy"):
            send_health_check_alert(health_status)

        return {"success": True, "task": "celery_health_check", **health_status}

    except Exception as e:
        logger.error(f"❌ Error in Celery health check task: {e}", exc_info=True)
        raise


@shared_task(name="src.tasks.notification_tasks.send_job_monitoring_digest")
def send_job_monitoring_digest():
    """
    Send daily job monitoring digest via email and Slack (Celery task wrapper).
    Scheduled to run at 9 AM EST (13:00 UTC).

    Generates a comprehensive report of all job executions from the past 24 hours:
    - Overall success rate
    - Failed jobs with error details
    - Slow jobs that exceeded expected duration
    - Category-based breakdown
    - Actionable recommendations

    This replaces individual job success notifications to prevent alert fatigue.
    """
    try:
        logger.info("📊 Starting job monitoring digest task...")
        from src.utils.database import get_db
        from src.services.job_monitoring_digest import JobMonitoringDigestService
        from src.managers.notifications import NotificationManager
        from config.settings import settings

        # Get database session
        db = next(get_db())

        try:
            # Generate digest
            digest_service = JobMonitoringDigestService(db)
            digest = digest_service.generate_daily_digest(hours_back=24)

            logger.info(
                f"Generated digest: {digest['summary']['total_executions']} executions, "
                f"{digest['summary']['success_rate']}% success rate"
            )

            # Format email HTML
            email_html = digest_service.format_email_body(digest)

            # Format Slack message
            slack_message = digest_service.format_slack_message(digest)

            # Send email if configured
            smtp_host = getattr(settings.notifications, "smtp_host", None)
            smtp_user = getattr(settings.notifications, "smtp_user", None)
            smtp_password = getattr(settings.notifications, "smtp_password", None)

            if all([smtp_host, smtp_user, smtp_password]):
                try:
                    import smtplib
                    from email.mime.multipart import MIMEMultipart
                    from email.mime.text import MIMEText

                    smtp_port = getattr(settings.notifications, "smtp_port", 587)
                    from_email = os.getenv("SMTP_FROM_EMAIL", smtp_user)
                    from_name = os.getenv("SMTP_FROM_NAME", "Agent PM")
                    to_email = os.getenv("ADMIN_EMAIL", smtp_user)

                    msg = MIMEMultipart("alternative")
                    msg["Subject"] = (
                        f"Job Monitoring Daily Digest - {digest['summary']['period_start'][:10]}"
                    )
                    msg["From"] = f"{from_name} <{from_email}>"
                    msg["To"] = to_email

                    # Attach HTML content
                    msg.attach(MIMEText(email_html, "html"))

                    # Send email
                    with smtplib.SMTP(smtp_host, smtp_port) as server:
                        server.starttls()
                        server.login(smtp_user, smtp_password)
                        server.send_message(msg)

                    logger.info("✅ Email digest sent successfully")
                except Exception as email_err:
                    logger.error(f"Failed to send email digest: {email_err}")

            # Send Slack notification
            if settings.notifications.slack_bot_token:
                try:
                    notifier = NotificationManager(settings.notifications)
                    # Send to PM channel if configured, otherwise default channel
                    channel = (
                        getattr(settings.notifications, "slack_pm_channel", None)
                        or settings.notifications.slack_channel
                    )
                    # Use slack_client directly to send message
                    notifier.slack_client.chat_postMessage(
                        channel=channel, text=slack_message
                    )
                    logger.info("✅ Slack digest sent successfully")
                except Exception as slack_err:
                    logger.error(f"Failed to send Slack digest: {slack_err}")

            logger.info("✅ Job monitoring digest completed")

            return {
                "success": True,
                "task": "job_monitoring_digest",
                "executions_analyzed": digest["summary"]["total_executions"],
                "success_rate": digest["summary"]["success_rate"],
                "failures": len(digest["failures"]),
                "slow_jobs": len(digest["slow_jobs"]),
            }

        finally:
            db.close()

    except Exception as e:
        logger.error(f"❌ Error in job monitoring digest task: {e}", exc_info=True)
        raise
