"""Celery application configuration for background task processing."""

import os
import json
import tempfile
import atexit
from celery import Celery
from celery.schedules import crontab

# Set up GCP credentials from environment variable
# The credentials JSON is stored as GOOGLE_APPLICATION_CREDENTIALS_JSON
gcp_creds_json = os.getenv('GOOGLE_APPLICATION_CREDENTIALS_JSON')
if gcp_creds_json:
    # SECURITY FIX: Use secure temporary file with proper permissions and cleanup
    # Create secure temporary file with restrictive permissions (0o600 = owner read/write only)
    fd, creds_path = tempfile.mkstemp(suffix='.json', prefix='gcp-creds-')

    # Set restrictive file permissions (owner read/write only)
    os.chmod(creds_path, 0o600)

    # Write credentials using the file descriptor
    with os.fdopen(fd, 'w') as f:
        f.write(gcp_creds_json)

    # Set environment variable for google-cloud-pubsub
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = creds_path

    # Register cleanup function to delete credentials on exit
    def cleanup_gcp_credentials():
        try:
            if os.path.exists(creds_path):
                os.unlink(creds_path)
        except Exception:
            pass  # Silently fail on cleanup errors

    atexit.register(cleanup_gcp_credentials)
    print("✓ GCP credentials configured from environment (secure tempfile)")
else:
    print("⚠️  GOOGLE_APPLICATION_CREDENTIALS_JSON not set")

# GCP Pub/Sub broker configuration
# Format: gcpubsub://projects/PROJECT_ID
gcp_project_id = os.getenv('GCP_PROJECT_ID', 'syatt-io')
broker_url = f'gcpubsub://projects/{gcp_project_id}'

# Use PostgreSQL for result backend (storing task results)
database_url = os.getenv('DATABASE_URL', 'postgresql://localhost/agent_pm')
if database_url.startswith('postgresql://'):
    result_backend_url = 'db+' + database_url
elif database_url.startswith('postgres://'):
    result_backend_url = 'db+postgresql://' + database_url.split('://', 1)[1]
else:
    result_backend_url = 'db+' + database_url

print(f"Celery broker: GCP Pub/Sub (project: {gcp_project_id})")
backend_display = result_backend_url.split('@')[0] + '@***' if '@' in result_backend_url else result_backend_url
print(f"Celery result backend: {backend_display}")

# Create Celery app WITHOUT broker/backend parameters to avoid import-time evaluation
# The broker will be set in conf.update() below
celery_app = Celery(
    'agent_pm',
    include=[
        'src.tasks.vector_tasks',
        'src.tasks.notification_tasks',
        'src.webhooks.fireflies_webhook'  # Include webhook task for Fireflies meeting processing
    ]
)

# Configure Celery with GCP Pub/Sub broker and PostgreSQL result backend
celery_app.conf.update(
    # Broker: GCP Pub/Sub for message queuing
    # Result Backend: PostgreSQL for storing task results
    broker_url=broker_url,
    result_backend=result_backend_url,
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=120 * 60,  # 120 minutes (2 hours) max per task (for large backfills with 20k+ items)
    task_soft_time_limit=110 * 60,  # 110 minutes soft limit (gives 10 min to cleanup before hard kill)
    worker_max_tasks_per_child=50,  # Restart worker after 50 tasks to prevent memory leaks
    # Broker connection retry settings
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=10,
    # Use database table prefix to isolate from other apps
    result_backend_table_prefix='celery_',
    # ✅ FIXED: Clean up task results after 1 hour to prevent database bloat
    result_expires=3600,  # 1 hour in seconds
    result_backend_max_connections=10,  # Limit connections to result backend
    # ✅ RESILIENCE FIX: Prevent task loss during deployments/restarts
    # Late acknowledgment: only ack messages AFTER task completes successfully
    task_acks_late=True,  # Don't ack until task finishes (prevents loss on restart)
    task_reject_on_worker_lost=True,  # Requeue tasks if worker crashes
    worker_prefetch_multiplier=1,  # Only fetch 1 task at a time (prevents task loss)
    # ✅ GCP Pub/Sub message retention and acknowledgment settings
    # Increase acknowledgment deadline to prevent message loss during worker restarts
    broker_transport_options={
        'ack_deadline': 600,  # 10 minutes for worker to acknowledge (default is 60s)
        'retry_policy': {
            'minimum_backoff': 10,  # Minimum backoff of 10 seconds
            'maximum_backoff': 600,  # Maximum backoff of 10 minutes
        },
        # Message retention: keep unacked messages for up to 7 days
        'message_retention_duration': 604800,  # 7 days in seconds
    },
)

# Configure periodic tasks
celery_app.conf.beat_schedule = {
    # ========== Vector Database Ingestion Tasks ==========
    # All ingestion tasks run daily between 2-5 AM EST (6-9 UTC) to minimize resource usage
    # Staggered by 15 minutes to avoid overwhelming services

    # Ingest Notion pages daily at 2:00 AM EST (6:00 UTC)
    'ingest-notion-daily': {
        'task': 'src.tasks.vector_tasks.ingest_notion_pages',
        'schedule': crontab(hour=6, minute=0)
    },
    # Ingest Slack messages daily at 2:15 AM EST (6:15 UTC)
    'ingest-slack-daily': {
        'task': 'src.tasks.vector_tasks.ingest_slack_messages',
        'schedule': crontab(hour=6, minute=15)
    },
    # Ingest Jira issues daily at 2:30 AM EST (6:30 UTC)
    'ingest-jira-daily': {
        'task': 'src.tasks.vector_tasks.ingest_jira_issues',
        'schedule': crontab(hour=6, minute=30)
    },
    # Ingest Fireflies transcripts daily at 2:45 AM EST (6:45 UTC)
    'ingest-fireflies-daily': {
        'task': 'src.tasks.vector_tasks.ingest_fireflies_transcripts',
        'schedule': crontab(hour=6, minute=45)
    },
    # Ingest Tempo worklogs daily at 4:30 AM EST (8:30 UTC) - after tempo-sync-daily
    'ingest-tempo-daily': {
        'task': 'src.tasks.vector_tasks.ingest_tempo_worklogs',
        'schedule': crontab(hour=8, minute=30)
    },

    # ========== Notification & Digest Tasks ==========
    # Daily digest at 9 AM EST (13:00 UTC)
    'daily-todo-digest': {
        'task': 'src.tasks.notification_tasks.send_daily_digest',
        'schedule': crontab(hour=13, minute=0)
    },
    # Due today reminders at 9:30 AM EST (14:30 UTC during DST)
    'due-today-reminders': {
        'task': 'src.tasks.notification_tasks.send_due_today_reminders',
        'schedule': crontab(hour=13, minute=30)
    },
    # Overdue reminders at 10 AM EST (15:00 UTC during DST)
    'overdue-reminders-morning': {
        'task': 'src.tasks.notification_tasks.send_overdue_reminders',
        'schedule': crontab(hour=14, minute=0)
    },
    # Overdue reminders at 2 PM EST (19:00 UTC during DST)
    'overdue-reminders-afternoon': {
        'task': 'src.tasks.notification_tasks.send_overdue_reminders',
        'schedule': crontab(hour=18, minute=0)
    },
    # Check urgent items every 2 hours during work hours (9 AM, 11 AM, 1 PM, 3 PM, 5 PM EST)
    'urgent-items-9am': {
        'task': 'src.tasks.notification_tasks.check_urgent_items',
        'schedule': crontab(hour=13, minute=0)
    },
    'urgent-items-11am': {
        'task': 'src.tasks.notification_tasks.check_urgent_items',
        'schedule': crontab(hour=15, minute=0)
    },
    'urgent-items-1pm': {
        'task': 'src.tasks.notification_tasks.check_urgent_items',
        'schedule': crontab(hour=17, minute=0)
    },
    'urgent-items-3pm': {
        'task': 'src.tasks.notification_tasks.check_urgent_items',
        'schedule': crontab(hour=19, minute=0)
    },
    'urgent-items-5pm': {
        'task': 'src.tasks.notification_tasks.check_urgent_items',
        'schedule': crontab(hour=21, minute=0)
    },

    # ========== Weekly Tasks ==========
    # Weekly summary on Mondays at 9 AM EST (14:00 UTC during DST)
    'weekly-summary': {
        'task': 'src.tasks.notification_tasks.send_weekly_summary',
        'schedule': crontab(day_of_week=1, hour=13, minute=0)
    },
    # Weekly hours reports on Mondays at 10 AM EST (15:00 UTC during DST)
    'weekly-hours-reports': {
        'task': 'src.tasks.notification_tasks.send_weekly_hours_reports',
        'schedule': crontab(day_of_week=1, hour=14, minute=0)
    },

    # ========== Daily Sync Tasks ==========
    # Tempo hours sync at 4 AM EST (9:00 UTC during DST, 8:00 UTC standard time)
    # Using 8:00 UTC to work for both DST and standard time
    'tempo-sync-daily': {
        'task': 'src.tasks.notification_tasks.sync_tempo_hours',
        'schedule': crontab(hour=8, minute=0)
    },
}

# Register worker startup signal handler for missed task recovery
try:
    from celery.signals import worker_ready
    from src.tasks.startup_checks import on_worker_ready

    # Connect the signal handler
    worker_ready.connect(on_worker_ready)
    print("✓ Worker startup checks registered")
except Exception as e:
    print(f"⚠️  Could not register worker startup checks: {e}")

__all__ = ['celery_app']
