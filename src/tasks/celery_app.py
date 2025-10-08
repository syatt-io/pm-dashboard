"""Celery application configuration for background task processing."""

import os
from celery import Celery
from celery.schedules import crontab

# Initialize Celery
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

celery_app = Celery(
    'agent_pm',
    broker=redis_url,
    backend=redis_url,
    include=['src.tasks.vector_tasks']
)

# Configure Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes max per task
    worker_max_tasks_per_child=50,  # Restart worker after 50 tasks to prevent memory leaks
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
}

__all__ = ['celery_app']
