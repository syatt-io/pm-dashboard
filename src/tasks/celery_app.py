"""Celery application configuration for background task processing."""

import os
import json
from celery import Celery
from celery.schedules import crontab

# Set up GCP credentials from environment variable
# The credentials JSON is stored as GOOGLE_APPLICATION_CREDENTIALS_JSON
gcp_creds_json = os.getenv('GOOGLE_APPLICATION_CREDENTIALS_JSON')
if gcp_creds_json:
    # Write credentials to a temporary file that google-cloud-pubsub can use
    creds_path = '/tmp/gcp-credentials.json'
    with open(creds_path, 'w') as f:
        f.write(gcp_creds_json)
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = creds_path
    print("✓ GCP credentials configured from environment")
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
    include=['src.tasks.vector_tasks', 'src.tasks.notification_tasks']
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
    task_time_limit=30 * 60,  # 30 minutes max per task
    worker_max_tasks_per_child=50,  # Restart worker after 50 tasks to prevent memory leaks
    # Broker connection retry settings
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=10,
    # Use database table prefix to isolate from other apps
    result_backend_table_prefix='celery_',
    # ✅ FIXED: Clean up task results after 1 hour to prevent database bloat
    result_expires=3600,  # 1 hour in seconds
    result_backend_max_connections=10,  # Limit connections to result backend
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
    # Daily digest at 9 AM EST (14:00 UTC during DST, 13:00 UTC standard time)
    # Using 13:00 UTC to work for both DST and standard time
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

__all__ = ['celery_app']
