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
# Format: gcpubsub://PROJECT_ID
gcp_project_id = os.getenv('GCP_PROJECT_ID', 'syatt-io')
broker_url = f'gcpubsub://{gcp_project_id}'

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
    include=['src.tasks.vector_tasks']
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
