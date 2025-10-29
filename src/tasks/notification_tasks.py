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
