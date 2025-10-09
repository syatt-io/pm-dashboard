#!/usr/bin/env python3
"""
Simple script to trigger backfill tasks in production.
Run this from the celery-worker console in DigitalOcean.

Usage:
    python scripts/trigger_backfills.py
"""

from src.tasks.celery_app import celery_app

# Configure to not wait for results (fire and forget)
celery_app.conf.task_ignore_result = True

print("=" * 60)
print("Triggering Production Backfill Tasks")
print("=" * 60)

print("\n🔄 Triggering Slack backfill (365 days)...")
try:
    slack_result = celery_app.send_task(
        'src.tasks.vector_tasks.backfill_slack',
        kwargs={'days_back': 365}
    )
    print(f"✅ Slack backfill task sent! Task ID: {slack_result.id}")
except Exception as e:
    print(f"❌ Failed to send Slack task: {e}")

print("\n🔄 Triggering Jira backfill (365 days)...")
try:
    jira_result = celery_app.send_task(
        'src.tasks.vector_tasks.backfill_jira',
        kwargs={'days_back': 365}
    )
    print(f"✅ Jira backfill task sent! Task ID: {jira_result.id}")
except Exception as e:
    print(f"❌ Failed to send Jira task: {e}")

print("\n" + "=" * 60)
print("Tasks Triggered!")
print("=" * 60)
print("\nMonitor progress with:")
print("doctl apps logs a2255a3b-23cc-4fd0-baa8-91d622bb912a --type run --follow --app-component celery-worker")
