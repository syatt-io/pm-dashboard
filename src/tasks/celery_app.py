"""Celery application configuration for background task processing."""

import os
from celery import Celery
from celery.schedules import crontab

# Use PostgreSQL as broker instead of Redis
# This avoids Redis connection issues with Upstash and uses existing PostgreSQL infrastructure
database_url = os.getenv('DATABASE_URL', 'postgresql://localhost/agent_pm')

# Celery requires 'db+' prefix for SQLAlchemy broker
# Convert postgresql:// to db+postgresql://
if database_url.startswith('postgresql://'):
    broker_url = 'db+' + database_url
elif database_url.startswith('postgres://'):
    # Some providers use postgres:// instead of postgresql://
    broker_url = 'db+postgresql://' + database_url.split('://', 1)[1]
else:
    broker_url = database_url

celery_app = Celery(
    'agent_pm',
    broker=broker_url,
    backend=broker_url,
    include=['src.tasks.vector_tasks']
)

# Configure Celery for PostgreSQL broker
celery_app.conf.update(
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
    # PostgreSQL-specific settings
    broker_transport_options={
        'visibility_timeout': 3600,  # 1 hour timeout for long-running tasks
    },
    # Use database table prefix to isolate from other apps
    result_backend_table_prefix='celery_'
)

# Configure periodic tasks
celery_app.conf.beat_schedule = {
    # Ingest Slack messages every 15 minutes
    'ingest-slack-15min': {
        'task': 'src.tasks.vector_tasks.ingest_slack_messages',
        'schedule': crontab(minute='*/15')
    },
    # Ingest Jira issues every 30 minutes
    'ingest-jira-30min': {
        'task': 'src.tasks.vector_tasks.ingest_jira_issues',
        'schedule': crontab(minute='*/30')
    },
    # Ingest Fireflies transcripts every hour
    'ingest-fireflies-hourly': {
        'task': 'src.tasks.vector_tasks.ingest_fireflies_transcripts',
        'schedule': crontab(hour='*/1', minute=0)
    },
    # Ingest Notion pages every hour
    'ingest-notion-hourly': {
        'task': 'src.tasks.vector_tasks.ingest_notion_pages',
        'schedule': crontab(hour='*/1', minute=15)  # Offset by 15min from Fireflies
    },
}

__all__ = ['celery_app']
