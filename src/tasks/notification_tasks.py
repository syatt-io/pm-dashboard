"""Celery tasks for scheduled notifications and digests."""

import asyncio
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='src.tasks.notification_tasks.send_daily_digest')
def send_daily_digest():
    """
    Send daily TODO digest (Celery task wrapper).
    Scheduled to run at 9 AM EST (14:00 UTC during DST).
    """
    try:
        logger.info("📧 Starting daily digest task...")
        from src.services.scheduler import TodoScheduler
        scheduler = TodoScheduler()
        asyncio.run(scheduler.send_daily_digest())
        logger.info("✅ Daily digest completed")
        return {'success': True, 'task': 'daily_digest'}
    except Exception as e:
        logger.error(f"❌ Error in daily digest task: {e}", exc_info=True)
        raise


@shared_task(name='src.tasks.notification_tasks.send_overdue_reminders')
def send_overdue_reminders():
    """
    Send overdue TODO reminders (Celery task wrapper).
    Scheduled to run at 10 AM and 2 PM EST.
    """
    try:
        logger.info("⚠️  Starting overdue reminders task...")
        from src.services.scheduler import TodoScheduler
        scheduler = TodoScheduler()
        asyncio.run(scheduler.send_overdue_reminders())
        logger.info("✅ Overdue reminders completed")
        return {'success': True, 'task': 'overdue_reminders'}
    except Exception as e:
        logger.error(f"❌ Error in overdue reminders task: {e}", exc_info=True)
        raise


@shared_task(name='src.tasks.notification_tasks.send_due_today_reminders')
def send_due_today_reminders():
    """
    Send reminders for TODOs due today (Celery task wrapper).
    Scheduled to run at 9:30 AM EST.
    """
    try:
        logger.info("📅 Starting due today reminders task...")
        from src.services.scheduler import TodoScheduler
        scheduler = TodoScheduler()
        asyncio.run(scheduler.send_due_today_reminders())
        logger.info("✅ Due today reminders completed")
        return {'success': True, 'task': 'due_today_reminders'}
    except Exception as e:
        logger.error(f"❌ Error in due today reminders task: {e}", exc_info=True)
        raise


@shared_task(name='src.tasks.notification_tasks.send_weekly_summary')
def send_weekly_summary():
    """
    Send weekly TODO summary (Celery task wrapper).
    Scheduled to run on Mondays at 9 AM EST.
    """
    try:
        logger.info("📊 Starting weekly summary task...")
        from src.services.scheduler import TodoScheduler
        scheduler = TodoScheduler()
        asyncio.run(scheduler.send_weekly_summary())
        logger.info("✅ Weekly summary completed")
        return {'success': True, 'task': 'weekly_summary'}
    except Exception as e:
        logger.error(f"❌ Error in weekly summary task: {e}", exc_info=True)
        raise


@shared_task(name='src.tasks.notification_tasks.send_weekly_hours_reports')
def send_weekly_hours_reports():
    """
    Send weekly hours tracking reports (Celery task wrapper).
    Scheduled to run on Mondays at 10 AM EST.
    """
    try:
        logger.info("📈 Starting weekly hours reports task...")
        from src.services.scheduler import TodoScheduler
        scheduler = TodoScheduler()
        asyncio.run(scheduler.send_weekly_hours_reports())
        logger.info("✅ Weekly hours reports completed")
        return {'success': True, 'task': 'weekly_hours_reports'}
    except Exception as e:
        logger.error(f"❌ Error in weekly hours reports task: {e}", exc_info=True)
        raise


@shared_task(name='src.tasks.notification_tasks.check_urgent_items')
def check_urgent_items():
    """
    Check for urgent items needing immediate attention (Celery task wrapper).
    Scheduled to run every 2 hours during work hours.
    """
    try:
        logger.info("🚨 Starting urgent items check...")
        from src.services.scheduler import TodoScheduler
        scheduler = TodoScheduler()
        asyncio.run(scheduler.check_urgent_items())
        logger.info("✅ Urgent items check completed")
        return {'success': True, 'task': 'urgent_items_check'}
    except Exception as e:
        logger.error(f"❌ Error in urgent items check: {e}", exc_info=True)
        raise


@shared_task(
    name='src.tasks.notification_tasks.sync_tempo_hours',
    bind=True,  # Bind task instance to get retry info
    autoretry_for=(Exception,),  # Auto-retry on any exception
    retry_kwargs={'max_retries': 3, 'countdown': 300},  # Retry 3 times, wait 5 min between retries
    retry_backoff=True,  # Exponential backoff
    retry_backoff_max=1800,  # Max 30 min backoff
    retry_jitter=True  # Add jitter to prevent thundering herd
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
    try:
        retry_info = f" (attempt {self.request.retries + 1}/4)" if self.request.retries > 0 else ""
        logger.info(f"⏰ Starting Tempo hours sync task{retry_info}...")
        from src.services.scheduler import TodoScheduler
        scheduler = TodoScheduler()
        scheduler.sync_tempo_hours()
        logger.info("✅ Tempo hours sync completed")
        return {'success': True, 'task': 'tempo_sync', 'retries': self.request.retries}
    except Exception as e:
        logger.error(f"❌ Error in Tempo sync task (attempt {self.request.retries + 1}/4): {e}", exc_info=True)
        # Re-raise to trigger auto-retry
        raise


@shared_task(
    name='src.tasks.notification_tasks.sync_project_epic_hours',
    bind=True,  # Bind task instance to get retry info
    autoretry_for=(Exception,),  # Auto-retry on any exception
    retry_kwargs={'max_retries': 2, 'countdown': 180},  # Retry 2 times, wait 3 min between retries
    retry_backoff=True,  # Exponential backoff
    retry_backoff_max=900,  # Max 15 min backoff
    retry_jitter=True  # Add jitter to prevent thundering herd
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

        retry_info = f" (attempt {self.request.retries + 1}/3)" if self.request.retries > 0 else ""
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
            start_date = '2023-01-01'
            end_date = datetime.now().strftime('%Y-%m-%d')

            logger.info(f"Fetching worklogs for {project_key} from {start_date} to {end_date}")
            worklogs = tempo.get_worklogs(from_date=start_date, to_date=end_date, project_key=project_key)

            if not worklogs:
                logger.warning(f"No worklogs found for {project_key}")
                session.close()
                return {'success': True, 'project_key': project_key, 'records': 0, 'message': 'No worklogs found'}

            total_worklogs = len(worklogs)
            logger.info(f"Found {total_worklogs} worklogs for {project_key}")

            # Update progress: fetching complete
            self.update_state(
                state='PROGRESS',
                meta={
                    'current': 0,
                    'total': total_worklogs,
                    'message': f'Fetched {total_worklogs} worklogs, starting to process...'
                }
            )

            # Group by epic → month → team
            epic_month_team_hours = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
            processed = 0
            skipped = 0

            # Issue key pattern: PROJECT-NUMBER (e.g., RNWL-123)
            import re
            issue_pattern = re.compile(r'([A-Z]+-\d+)')

            for idx, worklog in enumerate(worklogs):
                # Update progress every 50 worklogs (show progress even when skipping)
                if (idx + 1) % 50 == 0 or (idx + 1) == total_worklogs:
                    percent = round(((idx + 1) / total_worklogs) * 100, 1)
                    self.update_state(
                        state='PROGRESS',
                        meta={
                            'current': idx + 1,
                            'total': total_worklogs,
                            'message': f'Processing worklogs... {idx + 1}/{total_worklogs} ({percent}%)'
                        }
                    )

                issue = worklog.get('issue', {})
                issue_id = issue.get('id')
                if not issue_id:
                    skipped += 1
                    continue

                # OPTIMIZATION: Get epic FIRST to filter by project early (avoids API calls)
                epic_key = None
                attributes = worklog.get('attributes', {})
                if attributes:
                    values = attributes.get('values', [])
                    for attr in values:
                        if attr.get('key') == '_Epic_':
                            epic_key = attr.get('value')
                            break

                # Early filtering: If epic has project info and doesn't match, skip without API call
                if epic_key and epic_key != 'NO_EPIC' and '-' in epic_key:
                    epic_project = epic_key.split('-')[0]
                    if epic_project != project_key:
                        # Not our project, skip this worklog entirely (saves Jira API call!)
                        skipped += 1
                        continue

                # Get issue key (needed for worklogs without epic or to double-check project)
                issue_key = None
                description = worklog.get('description', '')

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
                project_from_key = issue_key.split('-')[0] if '-' in issue_key else None
                if project_from_key != project_key:
                    # Not our project after all
                    skipped += 1
                    continue

                # Get epic from Jira if not found in Tempo attributes
                if not epic_key:
                    epic_key = tempo.get_epic_from_jira(issue_key)
                    if not epic_key:
                        epic_key = 'NO_EPIC'

                # Get month
                started = worklog.get('startDate')
                if not started:
                    skipped += 1
                    continue

                worklog_date = datetime.strptime(started[:10], '%Y-%m-%d').date()
                month = date(worklog_date.year, worklog_date.month, 1)

                # Get hours
                time_spent_seconds = worklog.get('timeSpentSeconds', 0)
                hours = time_spent_seconds / 3600.0

                # Get team
                author = worklog.get('author', {})
                account_id = author.get('accountId')
                if account_id:
                    team = tempo.get_user_team(account_id)
                    if not team or team == 'Unassigned':
                        team = 'Other'
                else:
                    team = 'Other'

                # Accumulate
                epic_month_team_hours[epic_key][month][team] += hours
                processed += 1

            logger.info(f"Processed {processed} worklogs for {project_key}, skipped {skipped}")

            # Update progress: processing complete, now saving to database
            self.update_state(
                state='PROGRESS',
                meta={
                    'current': total_worklogs,
                    'total': total_worklogs,
                    'message': 'Saving to database...'
                }
            )

            # Delete all existing epic_hours records for this project before inserting fresh data
            # This ensures we don't accumulate stale records from renamed epics or changed Tempo data
            delete_result = session.execute(
                text("DELETE FROM epic_hours WHERE project_key = :project_key"),
                {"project_key": project_key}
            )
            delete_count = delete_result.rowcount
            session.commit()
            logger.info(f"Deleted {delete_count} existing epic_hours records for {project_key}")

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
                                updated_at=datetime.now()
                            )
                            stmt = stmt.on_conflict_do_update(
                                index_elements=['project_key', 'epic_key', 'month', 'team'],
                                set_={
                                    'hours': stmt.excluded.hours,
                                    'epic_category': stmt.excluded.epic_category,  # Update category on conflict
                                    'updated_at': datetime.now()
                                }
                            )
                            session.execute(stmt)
                            records_inserted += 1

            session.commit()
            logger.info(f"✅ Successfully synced {records_inserted} epic hours records for {project_key}")

            return {
                'success': True,
                'project_key': project_key,
                'records': records_inserted,
                'processed': processed,
                'skipped': skipped,
                'retries': self.request.retries
            }

        finally:
            session.close()

    except Exception as e:
        logger.error(f"❌ Error in epic hours sync for {project_key} (attempt {self.request.retries + 1}/3): {e}", exc_info=True)
        # Re-raise to trigger auto-retry
        raise


@shared_task(
    name='src.tasks.notification_tasks.analyze_meetings',
    bind=True,  # Bind task instance to get retry info
    autoretry_for=(Exception,),  # Auto-retry on any exception
    retry_kwargs={'max_retries': 2, 'countdown': 600},  # Retry 2 times, wait 10 min between retries
    retry_backoff=True,  # Exponential backoff
    retry_backoff_max=3600,  # Max 60 min backoff
    retry_jitter=True  # Add jitter to prevent thundering herd
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
        retry_info = f" (attempt {self.request.retries + 1}/3)" if self.request.retries > 0 else ""
        logger.info(f"🔍 Starting meeting analysis sync task{retry_info}...")
        from src.jobs.meeting_analysis_sync import run_meeting_analysis_sync
        stats = run_meeting_analysis_sync()

        if stats.get('success'):
            logger.info(f"✅ Meeting analysis completed: {stats.get('meetings_analyzed', 0)} meetings analyzed")
            return {
                'success': True,
                'task': 'meeting_analysis',
                'retries': self.request.retries,
                **stats
            }
        else:
            error_msg = stats.get('error', 'Unknown error')
            logger.error(f"❌ Meeting analysis failed: {error_msg}")
            raise Exception(f"Meeting analysis failed: {error_msg}")

    except Exception as e:
        logger.error(f"❌ Error in meeting analysis task (attempt {self.request.retries + 1}/3): {e}", exc_info=True)
        # Re-raise to trigger auto-retry
        raise
