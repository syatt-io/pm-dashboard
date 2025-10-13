# Notification System - Celery Beat Scheduler

**Last Updated:** 2025-10-13

## Overview

The notification system sends automated TODO reminders, digests, and reports via Slack. All scheduled tasks run via **Celery Beat** for reliability and scalability.

## Architecture

```
Celery Beat (Scheduler)
    ↓
GCP Pub/Sub (Message Broker)
    ↓
Celery Worker (Task Executor)
    ↓
TodoScheduler → NotificationManager → Slack
```

### Components

1. **Celery Beat** (`celery-beat` service) - Schedules tasks based on cron expressions
2. **GCP Pub/Sub** - Message broker for task queuing
3. **Celery Worker** (`celery-worker` service) - Executes queued tasks
4. **TodoScheduler** (`src/services/scheduler.py`) - Business logic for notifications
5. **Notification Tasks** (`src/tasks/notification_tasks.py`) - Celery task wrappers

## Scheduled Tasks

### Daily Tasks (UTC times)

| Time (UTC) | Time (EST) | Task | Description |
|------------|------------|------|-------------|
| 08:00 | 4:00 AM | `tempo-sync-daily` | Sync Tempo hours to database |
| 13:00 | 9:00 AM | `daily-todo-digest` | Daily TODO summary |
| 13:30 | 9:30 AM | `due-today-reminders` | Reminders for items due today |
| 14:00 | 10:00 AM | `overdue-reminders-morning` | Morning overdue alerts |
| 18:00 | 2:00 PM | `overdue-reminders-afternoon` | Afternoon overdue alerts |
| 13, 15, 17, 19, 21 | 9 AM, 11 AM, 1 PM, 3 PM, 5 PM | `urgent-items-*` | High-priority overdue checks |

### Weekly Tasks (Mondays only)

| Time (UTC) | Time (EST) | Task | Description |
|------------|------------|------|-------------|
| 13:00 | 9:00 AM | `weekly-summary` | Weekly TODO summary |
| 14:00 | 10:00 AM | `weekly-hours-reports` | Weekly hours tracking reports |

## Configuration

### Celery Beat Schedule

Located in `src/tasks/celery_app.py`:

```python
celery_app.conf.beat_schedule = {
    'daily-todo-digest': {
        'task': 'src.tasks.notification_tasks.send_daily_digest',
        'schedule': crontab(hour=13, minute=0)
    },
    # ... more schedules
}
```

### Task Implementation

Each task in `src/tasks/notification_tasks.py` wraps a `TodoScheduler` method:

```python
@shared_task(name='src.tasks.notification_tasks.send_daily_digest')
def send_daily_digest():
    """Send daily TODO digest (Celery task wrapper)."""
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
```

## Monitoring

### Monitor Script

Run the monitoring script to check task execution:

```bash
./scripts/monitor_notifications.sh
```

This shows:
- Recent Celery Beat schedules
- Task execution results
- Next scheduled times

### Manual Monitoring

```bash
# Check Celery Beat schedules
doctl apps logs a2255a3b-23cc-4fd0-baa8-91d622bb912a celery-beat --tail 100 | grep "Scheduler: Sending"

# Check Celery Worker execution
doctl apps logs a2255a3b-23cc-4fd0-baa8-91d622bb912a celery-worker --tail 200 | grep "notification_tasks"

# Check for errors
doctl apps logs a2255a3b-23cc-4fd0-baa8-91d622bb912a celery-worker --tail 500 | grep -i "error\|failed"
```

### Slack Notifications

All notifications are sent to: **#mikes-minion**

Expected notification times (EST):
- **4:00 AM** - Tempo sync completion (if in production env)
- **9:00 AM** - Daily digest + Weekly summary (Mondays)
- **9:30 AM** - Due today reminders
- **10:00 AM** - Overdue reminders + Weekly hours reports (Mondays)
- **2:00 PM** - Overdue reminders
- **Every 2 hours** - Urgent items (if any)

## Testing

### Manual Task Triggers

Trigger tasks manually via API endpoints:

```bash
# Trigger all notification tasks
curl -X POST "https://agent-pm-tsbbb.ondigitalocean.app/api/scheduler/celery/test-all"

# Trigger specific task
curl -X POST "https://agent-pm-tsbbb.ondigitalocean.app/api/scheduler/celery/daily-digest"
curl -X POST "https://agent-pm-tsbbb.ondigitalocean.app/api/scheduler/celery/overdue-reminders"
curl -X POST "https://agent-pm-tsbbb.ondigitalocean.app/api/scheduler/celery/due-today"
curl -X POST "https://agent-pm-tsbbb.ondigitalocean.app/api/scheduler/celery/weekly-summary"
curl -X POST "https://agent-pm-tsbbb.ondigitalocean.app/api/scheduler/celery/tempo-sync"
```

Response format:
```json
{
  "success": true,
  "message": "Daily digest task queued",
  "task_id": "dea6b9a7-1388-441c-9afd-0b09c0747e8a"
}
```

### Local Testing

Test tasks locally (requires venv):

```bash
source venv/bin/activate

python -c "
from src.tasks.notification_tasks import send_daily_digest
result = send_daily_digest()
print(f'Result: {result}')
"
```

## Troubleshooting

### Tasks Not Executing

1. **Check Celery Beat is running:**
   ```bash
   doctl apps logs a2255a3b-23cc-4fd0-baa8-91d622bb912a celery-beat --tail 50
   ```
   Should see: `beat: Starting...`

2. **Check Celery Worker is running:**
   ```bash
   doctl apps logs a2255a3b-23cc-4fd0-baa8-91d622bb912a celery-worker --tail 50
   ```
   Should see: `ready.`

3. **Check GCP Pub/Sub credentials:**
   ```bash
   doctl apps logs a2255a3b-23cc-4fd0-baa8-91d622bb912a celery-beat --tail 100 | grep "GCP"
   ```
   Should see: `✓ GCP credentials configured from environment`

### Tasks Fail with Errors

Check worker logs for error details:
```bash
doctl apps logs a2255a3b-23cc-4fd0-baa8-91d622bb912a celery-worker --tail 500 | grep -A 10 "ERROR"
```

Common issues:
- **Database connection errors**: Check DATABASE_URL in app.yaml
- **Slack API errors**: Check SLACK_BOT_TOKEN is valid
- **Import errors**: Ensure all dependencies installed in requirements.txt

### Notifications Not Appearing in Slack

1. Check task executed successfully in worker logs
2. Verify Slack bot token is valid: `SLACK_BOT_TOKEN` in app.yaml
3. Check bot has permission to post in #mikes-minion
4. Look for Slack API errors in logs:
   ```bash
   doctl apps logs a2255a3b-23cc-4fd0-baa8-91d622bb912a --tail 500 | grep -i "slack"
   ```

## Migration Notes

### Previous System (Deprecated)

The old system used Python's `schedule` library with PostgreSQL advisory locks in `gunicorn_config.py`. This was replaced due to:
- PostgreSQL lock acquisition failures (silent errors)
- Single-point-of-failure with Gunicorn workers
- Difficult to monitor and debug

### New System (Current)

Celery Beat provides:
- ✅ Proven reliability (already used for vector ingestion)
- ✅ Built-in monitoring and task tracking
- ✅ Retry logic and error handling
- ✅ Distributed task execution
- ✅ Result storage in PostgreSQL

## Future Enhancements

Potential improvements:
1. **Task result dashboard** - Web UI to view task execution history
2. **Alert on failures** - Send Slack alert if task fails 3+ times
3. **Dynamic scheduling** - Allow users to customize notification times
4. **Task metrics** - Track execution time, success rate, etc.
5. **Retry configuration** - Custom retry logic per task type

## References

- [Celery Documentation](https://docs.celeryproject.org/)
- [Celery Beat Scheduler](https://docs.celeryproject.org/en/stable/userguide/periodic-tasks.html)
- [GCP Pub/Sub with Celery](https://cloud.google.com/pubsub/docs/overview)
- [Crontab Schedules](https://crontab.guru/)

---

**Status:** ✅ Production Ready
**Last Tested:** 2025-10-13
**Owner:** Mike Samimi
