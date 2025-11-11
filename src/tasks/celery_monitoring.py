"""
Celery task monitoring and alerting system.

Provides comprehensive monitoring for Celery tasks including:
- Task failure alerts via Slack
- Task success tracking
- Worker health monitoring
- Queue depth monitoring
- Dead letter queue alerts
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from celery import signals
from celery.exceptions import SoftTimeLimitExceeded
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

logger = logging.getLogger(__name__)


class CeleryMonitor:
    """Monitor Celery task execution and send alerts on failures."""

    def __init__(self):
        """Initialize the monitor with Slack client."""
        self.slack_client = None
        self.alert_channel = os.getenv("SLACK_ALERT_CHANNEL") or os.getenv("SLACK_CHANNEL", "#general")
        self.environment = os.getenv("FLASK_ENV", "development")

        # Only send alerts in production by default
        self.enable_alerts = os.getenv("CELERY_ALERTS_ENABLED", "true").lower() == "true"

        # Slack setup
        slack_token = os.getenv("SLACK_BOT_TOKEN")
        if slack_token:
            self.slack_client = WebClient(token=slack_token)
            logger.info("✓ Celery monitoring Slack client initialized")
        else:
            logger.warning("⚠️  SLACK_BOT_TOKEN not found - Celery alerts disabled")
            self.enable_alerts = False

        # Track task failures to avoid spam
        self.recent_failures = {}  # task_name -> timestamp
        self.failure_cooldown = int(os.getenv("CELERY_ALERT_COOLDOWN_MINUTES", "15")) * 60  # 15 min default

    def should_alert(self, task_name: str) -> bool:
        """Check if we should send an alert for this task (cooldown logic)."""
        if not self.enable_alerts:
            return False

        now = datetime.now()
        last_failure = self.recent_failures.get(task_name)

        if last_failure:
            time_since_last = (now - last_failure).total_seconds()
            if time_since_last < self.failure_cooldown:
                logger.info(f"Suppressing alert for {task_name} (cooldown: {int(time_since_last)}s < {self.failure_cooldown}s)")
                return False

        self.recent_failures[task_name] = now
        return True

    def send_slack_alert(self, message: str, priority: str = "normal"):
        """Send alert to Slack channel."""
        if not self.slack_client:
            logger.warning("Slack client not available, cannot send alert")
            return

        try:
            # Add environment indicator
            env_prefix = f"[{self.environment.upper()}] " if self.environment != "production" else ""

            # Add emoji based on priority
            emoji = "🚨" if priority == "critical" else "⚠️"

            full_message = f"{emoji} {env_prefix}{message}"

            response = self.slack_client.chat_postMessage(
                channel=self.alert_channel,
                text=full_message,
                unfurl_links=False,
                unfurl_media=False
            )

            logger.info(f"✓ Sent Celery alert to {self.alert_channel}: {response['ts']}")

        except SlackApiError as e:
            logger.error(f"❌ Slack API error sending Celery alert: {e}")
        except Exception as e:
            logger.error(f"❌ Error sending Celery alert: {e}")

    def format_task_failure_alert(
        self,
        task_name: str,
        task_id: str,
        exception: Exception,
        args: tuple = (),
        kwargs: dict = None,
        retries: int = 0,
        max_retries: int = 3
    ) -> str:
        """Format a comprehensive task failure alert message."""
        kwargs = kwargs or {}

        message = f"*Celery Task Failure*\n\n"
        message += f"• *Task*: `{task_name}`\n"
        message += f"• *Task ID*: `{task_id}`\n"
        message += f"• *Exception*: `{type(exception).__name__}: {str(exception)}`\n"

        if retries > 0:
            message += f"• *Retries*: {retries}/{max_retries} (task failed after all retries)\n"

        # Add args/kwargs if present (truncate long values)
        if args:
            args_str = str(args)[:200]
            if len(str(args)) > 200:
                args_str += "..."
            message += f"• *Args*: `{args_str}`\n"

        if kwargs:
            kwargs_str = str(kwargs)[:200]
            if len(str(kwargs)) > 200:
                kwargs_str += "..."
            message += f"• *Kwargs*: `{kwargs_str}`\n"

        message += f"• *Time*: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        message += f"\n🔍 *Action Required*: Check logs and investigate task failure"

        return message

    def format_task_timeout_alert(
        self,
        task_name: str,
        task_id: str,
        soft_time_limit: int,
        args: tuple = (),
        kwargs: dict = None
    ) -> str:
        """Format a task timeout alert message."""
        kwargs = kwargs or {}

        message = f"*Celery Task Timeout*\n\n"
        message += f"• *Task*: `{task_name}`\n"
        message += f"• *Task ID*: `{task_id}`\n"
        message += f"• *Timeout*: Task exceeded soft time limit of {soft_time_limit // 60} minutes\n"

        if args:
            message += f"• *Args*: `{str(args)[:150]}`\n"
        if kwargs:
            message += f"• *Kwargs*: `{str(kwargs)[:150]}`\n"

        message += f"• *Time*: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        message += f"\n⏱️  *Action Required*: Task is taking too long - investigate performance issues"

        return message


# Global monitor instance
monitor = CeleryMonitor()


# ========== Celery Signal Handlers ==========

@signals.task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, args=None, kwargs=None,
                        traceback=None, einfo=None, **extra_kwargs):
    """
    Handle task failures and send alerts.

    This signal is sent when a task fails after all retries are exhausted.
    """
    task_name = sender.name if sender else "Unknown Task"

    logger.error(
        f"❌ Celery task failed: {task_name} (ID: {task_id})",
        exc_info=exception,
        extra={
            "task_name": task_name,
            "task_id": task_id,
            "args": args,
            "kwargs": kwargs
        }
    )

    # Check if we should alert (cooldown logic)
    if not monitor.should_alert(task_name):
        return

    # Get retry info from task
    retries = getattr(sender.request, 'retries', 0) if sender and hasattr(sender, 'request') else 0
    max_retries = getattr(sender, 'max_retries', 3) if sender else 3

    # Send Slack alert
    alert_message = monitor.format_task_failure_alert(
        task_name=task_name,
        task_id=task_id,
        exception=exception,
        args=args or (),
        kwargs=kwargs or {},
        retries=retries,
        max_retries=max_retries
    )

    monitor.send_slack_alert(alert_message, priority="critical")


@signals.task_retry.connect
def task_retry_handler(sender=None, task_id=None, reason=None, einfo=None, **kwargs):
    """
    Log task retries (no alerts to avoid spam).

    This signal is sent when a task is retried.
    """
    task_name = sender.name if sender else "Unknown Task"
    retries = getattr(sender.request, 'retries', 0) if sender and hasattr(sender, 'request') else 0
    max_retries = getattr(sender, 'max_retries', 3) if sender else 3

    logger.warning(
        f"🔄 Celery task retry: {task_name} (ID: {task_id}, attempt {retries + 1}/{max_retries + 1})",
        extra={
            "task_name": task_name,
            "task_id": task_id,
            "reason": str(reason),
            "retries": retries,
            "max_retries": max_retries
        }
    )


@signals.task_success.connect
def task_success_handler(sender=None, result=None, **kwargs):
    """
    Log task successes (verbose logging only).

    This signal is sent when a task executes successfully.
    """
    task_name = sender.name if sender else "Unknown Task"

    # Only log success for important tasks or in debug mode
    if os.getenv("CELERY_LOG_SUCCESS", "false").lower() == "true":
        logger.info(
            f"✅ Celery task succeeded: {task_name}",
            extra={
                "task_name": task_name,
                "result": result
            }
        )


@signals.task_revoked.connect
def task_revoked_handler(sender=None, request=None, terminated=None, signum=None, expired=None, **kwargs):
    """
    Handle task revocations (usually due to worker restarts or manual intervention).

    This signal is sent when a task is revoked (cancelled).
    """
    task_name = request.task if request else "Unknown Task"
    task_id = request.id if request else "Unknown"

    reason = "terminated" if terminated else ("expired" if expired else "revoked")

    logger.warning(
        f"⚠️  Celery task {reason}: {task_name} (ID: {task_id})",
        extra={
            "task_name": task_name,
            "task_id": task_id,
            "reason": reason,
            "terminated": terminated,
            "expired": expired
        }
    )

    # Alert on terminated tasks (usually means worker crash or OOM)
    if terminated and monitor.should_alert(task_name):
        message = f"*Celery Task Terminated*\n\n"
        message += f"• *Task*: `{task_name}`\n"
        message += f"• *Task ID*: `{task_id}`\n"
        message += f"• *Reason*: Task was terminated (likely worker crash or OOM)\n"
        message += f"• *Signal*: {signum}\n"
        message += f"• *Time*: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        message += f"\n🚨 *Action Required*: Check worker logs and investigate crash"

        monitor.send_slack_alert(message, priority="critical")


@signals.worker_shutting_down.connect
def worker_shutdown_handler(sender, **kwargs):
    """Handle worker shutdown events."""
    logger.warning(
        f"⚠️  Celery worker shutting down: {sender}",
        extra={"worker": str(sender)}
    )

    # Alert on worker shutdown (could be crash or deployment)
    if monitor.enable_alerts and os.getenv("CELERY_ALERT_ON_WORKER_SHUTDOWN", "false").lower() == "true":
        message = f"*Celery Worker Shutdown*\n\n"
        message += f"• *Worker*: `{sender}`\n"
        message += f"• *Time*: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        message += f"\nℹ️  This could be a deployment or a crash - check worker status"

        monitor.send_slack_alert(message, priority="normal")


@signals.worker_ready.connect
def worker_ready_handler(sender, **kwargs):
    """Handle worker ready events."""
    logger.info(
        f"✓ Celery worker ready: {sender}",
        extra={"worker": str(sender)}
    )


# ========== Helper Functions ==========

def check_queue_health() -> Dict[str, Any]:
    """
    Check Celery queue health metrics.

    Returns metrics about queue depth, worker status, etc.
    This is meant to be called by a health check endpoint.
    """
    from src.tasks.celery_app import celery_app

    try:
        # Get active tasks
        inspect = celery_app.control.inspect()

        active_tasks = inspect.active()
        scheduled_tasks = inspect.scheduled()
        reserved_tasks = inspect.reserved()

        # Calculate metrics
        total_active = sum(len(tasks) for tasks in (active_tasks or {}).values())
        total_scheduled = sum(len(tasks) for tasks in (scheduled_tasks or {}).values())
        total_reserved = sum(len(tasks) for tasks in (reserved_tasks or {}).values())

        # Check if any workers are available
        workers_available = bool(active_tasks is not None)

        return {
            "healthy": workers_available,
            "workers_available": workers_available,
            "active_tasks": total_active,
            "scheduled_tasks": total_scheduled,
            "reserved_tasks": total_reserved,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error checking queue health: {e}")
        return {
            "healthy": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


def send_health_check_alert(health_status: Dict[str, Any]):
    """Send alert if queue health check fails."""
    if not health_status.get("healthy") and monitor.should_alert("celery_health_check"):
        message = f"*Celery Health Check Failed*\n\n"
        message += f"• *Workers Available*: {health_status.get('workers_available', False)}\n"
        message += f"• *Error*: {health_status.get('error', 'Unknown')}\n"
        message += f"• *Time*: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        message += f"\n🚨 *Action Required*: Celery workers may be down - investigate immediately"

        monitor.send_slack_alert(message, priority="critical")


__all__ = ['monitor', 'check_queue_health', 'send_health_check_alert']
