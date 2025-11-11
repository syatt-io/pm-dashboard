# Celery Monitoring & Alerting System

**Last Updated**: 2025-11-11
**Status**: ✅ Production Ready

---

## Overview

Comprehensive monitoring and alerting system for Celery tasks with automatic Slack notifications for failures, retries, timeouts, and worker issues.

---

## Features

### 1. **Automatic Failure Alerts** 🚨
- Slack notifications when tasks fail after all retries
- Detailed error information (task name, exception, args/kwargs)
- Cooldown period to prevent alert spam (15 min default)

### 2. **Task Retry Logging** 🔄
- Logs all task retries with attempt numbers
- No alerts (to avoid spam) but visible in logs

### 3. **Worker Health Monitoring** 🏥
- Hourly health checks of Celery workers
- Automatic alerts if workers go down
- Queue depth monitoring

### 4. **Task Timeout Alerts** ⏱️
- Alerts when tasks exceed soft time limits
- Helps identify performance issues

### 5. **Worker Crash Detection** 💥
- Alerts on worker termination (OOM, crashes)
- Worker shutdown notifications (optional)

### 6. **Health Check Endpoints** 📊
- HTTP endpoint for Celery worker status
- Integrates with monitoring systems

---

## Architecture

### Components

```
src/tasks/celery_monitoring.py
├── CeleryMonitor class         # Main monitoring class
├── Celery signal handlers      # Hooks into Celery events
│   ├── task_failure_handler    # Alerts on final failures
│   ├── task_retry_handler      # Logs retries
│   ├── task_success_handler    # Logs successes (optional)
│   ├── task_revoked_handler    # Handles cancelled tasks
│   ├── worker_shutdown_handler # Worker termination
│   └── worker_ready_handler    # Worker startup
├── check_queue_health()        # Query worker status
└── send_health_check_alert()   # Alert on unhealthy workers
```

### Integration Points

1. **Celery App** (`src/tasks/celery_app.py`)
   - Imports monitoring module to register signals
   - Signals connect automatically on import

2. **Health Check Task** (`src/tasks/notification_tasks.py`)
   - Scheduled hourly via Celery Beat
   - Calls `check_queue_health()` and alerts if issues detected

3. **Health API Endpoint** (`src/routes/health.py`)
   - `/api/health/celery` - Returns worker status
   - Used by external monitoring systems

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SLACK_BOT_TOKEN` | *Required* | Slack bot token for sending alerts |
| `SLACK_CHANNEL` | `#general` | Default channel for system alerts |
| `SLACK_ALERT_CHANNEL` | `SLACK_CHANNEL` | Dedicated channel for Celery alerts (optional) |
| `FLASK_ENV` | `development` | Environment indicator (prefixed in alerts) |
| `CELERY_ALERTS_ENABLED` | `true` | Enable/disable alerts globally |
| `CELERY_ALERT_COOLDOWN_MINUTES` | `15` | Minutes between alerts for same task |
| `CELERY_LOG_SUCCESS` | `false` | Log task successes (verbose) |
| `CELERY_ALERT_ON_WORKER_SHUTDOWN` | `false` | Alert on worker shutdown |

### Example `.env` Configuration

```bash
# Celery Monitoring
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_ALERT_CHANNEL=#celery-alerts
CELERY_ALERTS_ENABLED=true
CELERY_ALERT_COOLDOWN_MINUTES=15
```

---

## Alert Examples

### 1. Task Failure Alert

```
🚨 [PRODUCTION] Celery Task Failure

• Task: `src.tasks.notification_tasks.send_daily_digest`
• Task ID: `a1b2c3d4-e5f6-7890-abcd-ef1234567890`
• Exception: `SlackApiError: channel_not_found`
• Retries: 3/3 (task failed after all retries)
• Args: `()`
• Kwargs: `{}`
• Time: 2025-11-11 14:23:45 UTC

🔍 Action Required: Check logs and investigate task failure
```

### 2. Task Timeout Alert

```
⚠️  [PRODUCTION] Celery Task Timeout

• Task: `src.tasks.vector_tasks.backfill_jira`
• Task ID: `b2c3d4e5-f6g7-8901-bcde-fg2345678901`
• Timeout: Task exceeded soft time limit of 110 minutes
• Args: `({'days_back': 365},)`
• Time: 2025-11-11 16:45:12 UTC

⏱️  Action Required: Task is taking too long - investigate performance issues
```

### 3. Worker Health Check Failure

```
🚨 [PRODUCTION] Celery Health Check Failed

• Workers Available: False
• Error: Connection refused to broker
• Time: 2025-11-11 18:00:00 UTC

🚨 Action Required: Celery workers may be down - investigate immediately
```

### 4. Worker Crash Alert

```
🚨 [PRODUCTION] Celery Task Terminated

• Task: `src.tasks.vector_tasks.backfill_notion`
• Task ID: `c3d4e5f6-g7h8-9012-cdef-gh3456789012`
• Reason: Task was terminated (likely worker crash or OOM)
• Signal: 9
• Time: 2025-11-11 20:15:30 UTC

🚨 Action Required: Check worker logs and investigate crash
```

---

## Monitoring Schedule

| Check | Frequency | Alert Condition | Cooldown |
|-------|-----------|-----------------|----------|
| Task Failures | On failure | Task fails after all retries | 15 min per task |
| Task Retries | On retry | *No alert* (logs only) | N/A |
| Worker Health | Hourly (via Celery Beat) | No workers available | 15 min |
| Worker Termination | On event | Worker crashes/terminated | 15 min per worker |
| Queue Depth | On health check | *Not yet implemented* | N/A |

---

## Health Check Endpoints

### GET `/api/health/celery`

Check Celery worker and queue health.

**Response 200 (Healthy)**:
```json
{
  "status": "healthy",
  "timestamp": "2025-11-11T14:30:00.123456",
  "celery": {
    "healthy": true,
    "workers_available": true,
    "active_tasks": 3,
    "scheduled_tasks": 15,
    "reserved_tasks": 2,
    "timestamp": "2025-11-11T14:30:00.123456"
  }
}
```

**Response 503 (Unhealthy)**:
```json
{
  "status": "unhealthy",
  "timestamp": "2025-11-11T14:30:00.123456",
  "celery": {
    "healthy": false,
    "workers_available": false,
    "error": "Connection refused",
    "warning": "Celery workers may be unavailable or not responding",
    "timestamp": "2025-11-11T14:30:00.123456"
  }
}
```

### Monitoring Integration

Use the health check endpoint with external monitoring tools:

**Datadog Example**:
```yaml
init_config:

instances:
  - name: agent-pm-celery
    url: https://agent-pm.example.com/api/health/celery
    method: GET
    timeout: 10
    http_response_status_code: 200
```

**Kubernetes Liveness Probe**:
```yaml
livenessProbe:
  httpGet:
    path: /api/health/celery
    port: 8080
  initialDelaySeconds: 60
  periodSeconds: 60
  timeoutSeconds: 10
  failureThreshold: 3
```

---

## Testing

### Test Alert System Locally

1. **Test Slack Connection**:
   ```bash
   python -c "from src.tasks.celery_monitoring import monitor; monitor.send_slack_alert('Test alert from Celery monitoring', 'normal')"
   ```

2. **Trigger Deliberate Task Failure**:
   ```python
   # Create a test task that fails
   from celery import shared_task

   @shared_task
   def test_failure_task():
       raise Exception("This is a test failure")

   # Run it
   test_failure_task.delay()
   ```

3. **Check Health Endpoint**:
   ```bash
   curl http://localhost:4000/api/health/celery | jq
   ```

4. **Simulate Worker Shutdown**:
   ```bash
   # Start Celery worker
   celery -A src.tasks.celery_app worker -l info --concurrency=1

   # Send SIGTERM to test shutdown handler
   pkill -TERM celery
   ```

### Test Health Check Task

```bash
# Manually trigger health check
python -c "from src.tasks.notification_tasks import celery_health_check; celery_health_check()"
```

---

## Troubleshooting

### Alerts Not Sending

**Symptom**: No Slack alerts despite task failures

**Solutions**:

1. **Check Slack Token**:
   ```bash
   python -c "import os; print('SLACK_BOT_TOKEN:', 'SET' if os.getenv('SLACK_BOT_TOKEN') else 'NOT SET')"
   ```

2. **Verify Monitoring Enabled**:
   ```bash
   python -c "from src.tasks.celery_monitoring import monitor; print('Alerts enabled:', monitor.enable_alerts)"
   ```

3. **Check Slack Channel**:
   ```bash
   python -c "from src.tasks.celery_monitoring import monitor; print('Alert channel:', monitor.alert_channel)"
   ```

4. **Test Slack Connectivity**:
   ```python
   from slack_sdk import WebClient
   import os

   client = WebClient(token=os.getenv("SLACK_BOT_TOKEN"))
   response = client.auth_test()
   print(f"Slack bot: {response['user']}")
   ```

### Cooldown Suppressing Alerts

**Symptom**: Expected alerts not showing up

**Cause**: Cooldown period (15 min default) prevents duplicate alerts

**Solutions**:

1. **Reduce Cooldown** (for testing):
   ```bash
   export CELERY_ALERT_COOLDOWN_MINUTES=1
   ```

2. **Check Recent Failures**:
   ```python
   from src.tasks.celery_monitoring import monitor
   print(monitor.recent_failures)
   ```

3. **Clear Cooldown** (restart worker):
   ```bash
   # Restart Celery worker to reset cooldown state
   pkill celery && celery -A src.tasks.celery_app worker -l info
   ```

### Health Check Fails

**Symptom**: `/api/health/celery` returns 503

**Cause**: Celery workers not running or not responding

**Solutions**:

1. **Check Workers Running**:
   ```bash
   ps aux | grep celery
   ```

2. **Inspect Celery**:
   ```python
   from src.tasks.celery_app import celery_app
   inspect = celery_app.control.inspect()
   print("Active:", inspect.active())
   print("Scheduled:", inspect.scheduled())
   ```

3. **Restart Workers**:
   ```bash
   # Kill all Celery processes
   pkill -9 celery

   # Start fresh worker
   celery -A src.tasks.celery_app worker -l info

   # Start Beat scheduler
   celery -A src.tasks.celery_app beat -l info
   ```

### No Health Check Alerts

**Symptom**: Workers are down but no alerts sent

**Causes & Solutions**:

1. **Health Check Task Not Running**:
   ```bash
   # Check if scheduled in Celery Beat
   python -c "from src.tasks.celery_app import celery_app; print('celery-health-check' in celery_app.conf.beat_schedule)"
   ```

2. **Celery Beat Not Running**:
   ```bash
   # Start Celery Beat
   celery -A src.tasks.celery_app beat -l info
   ```

3. **Alert Cooldown** (see above)

---

## Best Practices

### 1. Alert Tuning

**Do:**
- ✅ Set appropriate cooldown periods (15-30 min)
- ✅ Use separate Slack channel for Celery alerts
- ✅ Monitor alert volume and adjust as needed
- ✅ Escalate critical alerts (worker crashes) to on-call

**Don't:**
- ❌ Set cooldown too low (creates spam)
- ❌ Alert on task retries (too noisy)
- ❌ Send all alerts to general channel
- ❌ Ignore repeated failures (investigate patterns)

### 2. Task Design

**Do:**
- ✅ Set appropriate `max_retries` (2-3 for most tasks)
- ✅ Use exponential backoff for retries
- ✅ Set realistic time limits (soft and hard)
- ✅ Log context (args/kwargs) for debugging

**Don't:**
- ❌ Retry forever (`max_retries=None`)
- ❌ Use short timeouts for long-running tasks
- ❌ Pass sensitive data in task args (logged in alerts)
- ❌ Ignore task failures

### 3. Monitoring Integration

**Do:**
- ✅ Monitor health check endpoint with external tools
- ✅ Set up dashboards (Datadog, Grafana, etc.)
- ✅ Track task success/failure rates over time
- ✅ Monitor queue depth and worker utilization

**Don't:**
- ❌ Rely only on Slack alerts (use metrics too)
- ❌ Ignore warning signals (high queue depth, slow tasks)
- ❌ Skip regular health checks
- ❌ Forget to test alert system periodically

### 4. Incident Response

**When Alerts Fire:**

1. **Acknowledge** - Respond in Slack thread
2. **Investigate** - Check logs, health endpoints, worker status
3. **Mitigate** - Restart workers, scale up, fix bugs
4. **Follow-up** - Root cause analysis, prevent recurrence
5. **Document** - Update runbooks, improve monitoring

---

## Metrics to Track

### Key Performance Indicators

1. **Task Success Rate** - `successful_tasks / total_tasks`
2. **Task Failure Rate** - `failed_tasks / total_tasks`
3. **Average Task Duration** - Monitor for performance degradation
4. **Retry Rate** - `retried_tasks / total_tasks`
5. **Worker Availability** - `uptime / total_time`
6. **Queue Depth** - Number of pending tasks
7. **Alert Frequency** - Alerts per day (should be low)

### Recommended Thresholds

| Metric | Warning | Critical |
|--------|---------|----------|
| Task Failure Rate | >5% | >10% |
| Task Retry Rate | >10% | >20% |
| Worker Downtime | >5 min | >15 min |
| Queue Depth | >100 | >500 |
| Alert Frequency | >10/day | >20/day |

---

## Related Documentation

- **Jobs Inventory**: `docs/JOBS_INVENTORY.md` - All scheduled jobs
- **Celery Configuration**: `src/tasks/celery_app.py` - Celery setup
- **Deployment Guide**: `docs/DEPLOYMENT_TROUBLESHOOTING_2025-10-31.md` - Production deployment

---

## Support

**Issues or Questions?**
- Check logs: `celery -A src.tasks.celery_app worker -l info`
- Test alerts: Run test commands in **Testing** section
- Review Slack channel for recent alerts
- Check health endpoint: `GET /api/health/celery`

---

**Last Updated**: 2025-11-11
**Monitoring Coverage**: 21 Celery Beat scheduled tasks + health checks
