"""Celery application configuration for background task processing."""

import os
from celery import Celery
from celery.schedules import crontab

# Initialize Celery
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# Use database 1 for agent-pm to isolate from other apps
# Replace /0 with /1 at the end of the URL
if redis_url.endswith('/0'):
    redis_url = redis_url[:-2] + '/1'
elif not redis_url.split('/')[-1].isdigit():
    redis_url = redis_url.rstrip('/') + '/1'

celery_app = Celery(
    'agent_pm',
    broker=redis_url,
    backend=redis_url,
    include=['src.tasks.vector_tasks']
)

# Configure Celery with unique key prefix and Redis connection handling
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes max per task
    worker_max_tasks_per_child=50,  # Restart worker after 50 tasks to prevent memory leaks
    # Use unique key prefix to isolate from other apps sharing same Redis
    result_backend_transport_options={
        'global_keyprefix': 'agent-pm:',
        'retry_on_timeout': True,
        'socket_keepalive': True,
        'socket_keepalive_options': {
            1: 1,  # TCP_KEEPIDLE
            2: 1,  # TCP_KEEPINTVL
            3: 3   # TCP_KEEPCNT
        },
        'health_check_interval': 30
    },
    broker_transport_options={
        'global_keyprefix': 'agent-pm:',
        'retry_on_timeout': True,
        'socket_keepalive': True,
        'socket_keepalive_options': {
            1: 1,  # TCP_KEEPIDLE
            2: 1,  # TCP_KEEPINTVL
            3: 3   # TCP_KEEPCNT
        },
        'health_check_interval': 30
    },
    # Broker connection retry settings
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=10,
    # SSL/TLS settings for Upstash Redis (required for rediss:// URLs)
    broker_use_ssl={
        'ssl_cert_reqs': None  # Don't verify SSL certificates
    },
    redis_backend_use_ssl={
        'ssl_cert_reqs': None  # Don't verify SSL certificates
    }
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
