"""Job monitoring configuration for all Celery Beat scheduled tasks.

This file defines metadata for all scheduled jobs to enable:
- Failure detection and alerting
- Performance monitoring (expected duration vs actual)
- Job categorization for digest reporting
- Priority-based alert routing
"""

from typing import Dict, Any
from dataclasses import dataclass


@dataclass
class JobConfig:
    """Configuration for a single scheduled job."""

    job_name: str
    category: str  # vector_ingestion, notifications, pm_automation, etc.
    priority: str  # critical, high, normal, low
    expected_duration_seconds: int  # Expected max duration (for slow job detection)
    description: str
    alert_on_failure: bool = True  # Send immediate alert on failure
    alert_cooldown_minutes: int = 15  # Cooldown between duplicate alerts


# Job Categories
VECTOR_INGESTION = "vector_ingestion"
NOTIFICATIONS = "notifications"
DATA_SYNC = "data_sync"
MEETING_ANALYSIS = "meeting_analysis"
PM_AUTOMATION = "pm_automation"
PROACTIVE_AGENT = "proactive_agent"

# Priority Levels
CRITICAL = "critical"  # Core functionality - immediate alert
HIGH = "high"  # Important automation - alert in digest
NORMAL = "normal"  # Regular operations - digest only
LOW = "low"  # Nice-to-have - digest only

# Alert Configuration
ALERT_CONFIG = {
    "immediate_alert_priorities": [
        CRITICAL
    ],  # Only critical failures get immediate Slack alert
    "daily_digest_time": "09:00",  # 9 AM EST
    "alert_cooldown_minutes": 15,  # Prevent duplicate alerts for same failure
    "slow_job_threshold": 1.5,  # Alert if job takes 1.5x expected duration
}


# ============================================================================
# JOB DEFINITIONS - All 20 Celery Beat Scheduled Tasks
# ============================================================================

JOBS: Dict[str, JobConfig] = {
    # ========================================================================
    # 1. VECTOR DATABASE INGESTION (5 Tasks) - CRITICAL
    # ========================================================================
    "ingest-notion-daily": JobConfig(
        job_name="ingest-notion-daily",
        category=VECTOR_INGESTION,
        priority=CRITICAL,
        expected_duration_seconds=600,  # 10 minutes
        description="Daily ingestion of Notion pages into Pinecone vector DB",
        alert_on_failure=True,
    ),
    "ingest-slack-daily": JobConfig(
        job_name="ingest-slack-daily",
        category=VECTOR_INGESTION,
        priority=CRITICAL,
        expected_duration_seconds=300,  # 5 minutes
        description="Daily ingestion of Slack messages into Pinecone vector DB",
        alert_on_failure=True,
    ),
    "ingest-jira-daily": JobConfig(
        job_name="ingest-jira-daily",
        category=VECTOR_INGESTION,
        priority=CRITICAL,
        expected_duration_seconds=900,  # 15 minutes
        description="Daily ingestion of Jira issues + comments into Pinecone vector DB",
        alert_on_failure=True,
    ),
    "ingest-fireflies-daily": JobConfig(
        job_name="ingest-fireflies-daily",
        category=VECTOR_INGESTION,
        priority=CRITICAL,
        expected_duration_seconds=300,  # 5 minutes
        description="Daily ingestion of Fireflies meeting transcripts into Pinecone vector DB",
        alert_on_failure=True,
    ),
    "ingest-tempo-daily": JobConfig(
        job_name="ingest-tempo-daily",
        category=VECTOR_INGESTION,
        priority=CRITICAL,
        expected_duration_seconds=180,  # 3 minutes
        description="Daily ingestion of Tempo worklogs into Pinecone vector DB",
        alert_on_failure=True,
    ),
    # ========================================================================
    # 2. NOTIFICATION & REMINDERS (7 Tasks) - NORMAL/LOW
    # ========================================================================
    "daily-todo-digest": JobConfig(
        job_name="daily-todo-digest",
        category=NOTIFICATIONS,
        priority=NORMAL,
        expected_duration_seconds=60,  # 1 minute
        description="Daily TODO digest sent to opted-in users via Slack DM",
        alert_on_failure=False,  # Digest only
    ),
    "due-today-reminders": JobConfig(
        job_name="due-today-reminders",
        category=NOTIFICATIONS,
        priority=NORMAL,
        expected_duration_seconds=60,  # 1 minute
        description="Daily reminders for TODOs due today",
        alert_on_failure=False,  # Digest only
    ),
    "overdue-reminders-morning": JobConfig(
        job_name="overdue-reminders-morning",
        category=NOTIFICATIONS,
        priority=NORMAL,
        expected_duration_seconds=60,  # 1 minute
        description="Morning reminders for overdue TODOs",
        alert_on_failure=False,  # Digest only
    ),
    "overdue-reminders-afternoon": JobConfig(
        job_name="overdue-reminders-afternoon",
        category=NOTIFICATIONS,
        priority=NORMAL,
        expected_duration_seconds=60,  # 1 minute
        description="Afternoon reminders for overdue TODOs",
        alert_on_failure=False,  # Digest only
    ),
    "urgent-items-check": JobConfig(
        job_name="urgent-items-check",
        category=NOTIFICATIONS,
        priority=LOW,
        expected_duration_seconds=30,  # 30 seconds
        description="Every 2 hours check for high-priority overdue items",
        alert_on_failure=False,  # Digest only
    ),
    "weekly-summary": JobConfig(
        job_name="weekly-summary",
        category=NOTIFICATIONS,
        priority=NORMAL,
        expected_duration_seconds=120,  # 2 minutes
        description="Weekly TODO summary (Mondays 9 AM EST)",
        alert_on_failure=False,  # Digest only
    ),
    "weekly-hours-reports": JobConfig(
        job_name="weekly-hours-reports",
        category=NOTIFICATIONS,
        priority=NORMAL,
        expected_duration_seconds=180,  # 3 minutes
        description="Weekly project hours reports to PMs (Mondays 10 AM EST)",
        alert_on_failure=False,  # Digest only
    ),
    # ========================================================================
    # 3. DATA SYNC OPERATIONS (1 Task) - HIGH
    # ========================================================================
    "tempo-sync-daily": JobConfig(
        job_name="tempo-sync-daily",
        category=DATA_SYNC,
        priority=HIGH,
        expected_duration_seconds=60,  # 1 minute
        description="Daily sync of project hours from Tempo API to database",
        alert_on_failure=True,
    ),
    # ========================================================================
    # 4. MEETING ANALYSIS (1 Task) - HIGH
    # ========================================================================
    "meeting-analysis-sync": JobConfig(
        job_name="meeting-analysis-sync",
        category=MEETING_ANALYSIS,
        priority=HIGH,
        expected_duration_seconds=600,  # 10 minutes (multiple meetings)
        description="Nightly analysis of Fireflies meeting transcripts with AI",
        alert_on_failure=True,
    ),
    # ========================================================================
    # 5. PM AUTOMATION JOBS (2 Tasks) - HIGH
    # ========================================================================
    "time-tracking-compliance": JobConfig(
        job_name="time-tracking-compliance",
        category=PM_AUTOMATION,
        priority=HIGH,
        expected_duration_seconds=180,  # 3 minutes
        description="Weekly time tracking compliance check (Mondays 10 AM EST)",
        alert_on_failure=True,
    ),
    "monthly-epic-reconciliation": JobConfig(
        job_name="monthly-epic-reconciliation",
        category=PM_AUTOMATION,
        priority=HIGH,
        expected_duration_seconds=300,  # 5 minutes
        description="Monthly epic hours reconciliation report (3rd of month)",
        alert_on_failure=True,
    ),
    # ========================================================================
    # 6. JOB MONITORING DIGEST (1 Task) - NORMAL
    # ========================================================================
    "job-monitoring-digest": JobConfig(
        job_name="job-monitoring-digest",
        category=NOTIFICATIONS,
        priority=NORMAL,
        expected_duration_seconds=60,  # 1 minute
        description="Daily job monitoring digest via email and Slack (9:05 AM EST)",
        alert_on_failure=False,  # Digest only
    ),
    # ========================================================================
    # 7. PROACTIVE AGENT JOBS (3 Tasks) - HIGH/NORMAL
    # ========================================================================
    "proactive-insights-8am": JobConfig(
        job_name="proactive-insights-8am",
        category=PROACTIVE_AGENT,
        priority=HIGH,
        expected_duration_seconds=300,  # 5 minutes
        description="AI-powered proactive insights detection (8 AM EST)",
        alert_on_failure=True,
    ),
    "proactive-insights-12pm": JobConfig(
        job_name="proactive-insights-12pm",
        category=PROACTIVE_AGENT,
        priority=HIGH,
        expected_duration_seconds=300,  # 5 minutes
        description="AI-powered proactive insights detection (12 PM EST)",
        alert_on_failure=True,
    ),
    "proactive-insights-4pm": JobConfig(
        job_name="proactive-insights-4pm",
        category=PROACTIVE_AGENT,
        priority=HIGH,
        expected_duration_seconds=300,  # 5 minutes
        description="AI-powered proactive insights detection (4 PM EST)",
        alert_on_failure=True,
    ),
    "daily-briefs": JobConfig(
        job_name="daily-briefs",
        category=PROACTIVE_AGENT,
        priority=NORMAL,
        expected_duration_seconds=120,  # 2 minutes
        description="Daily brief delivery to users via Slack/Email (9 AM EST)",
        alert_on_failure=False,  # Digest only
    ),
    "auto-escalation-6am": JobConfig(
        job_name="auto-escalation-6am",
        category=PROACTIVE_AGENT,
        priority=NORMAL,
        expected_duration_seconds=120,  # 2 minutes
        description="Auto-escalation of stale insights (6 AM EST)",
        alert_on_failure=False,  # Digest only
    ),
    "auto-escalation-12pm": JobConfig(
        job_name="auto-escalation-12pm",
        category=PROACTIVE_AGENT,
        priority=NORMAL,
        expected_duration_seconds=120,  # 2 minutes
        description="Auto-escalation of stale insights (12 PM EST)",
        alert_on_failure=False,  # Digest only
    ),
    "auto-escalation-6pm": JobConfig(
        job_name="auto-escalation-6pm",
        category=PROACTIVE_AGENT,
        priority=NORMAL,
        expected_duration_seconds=120,  # 2 minutes
        description="Auto-escalation of stale insights (6 PM EST)",
        alert_on_failure=False,  # Digest only
    ),
    "auto-escalation-12am": JobConfig(
        job_name="auto-escalation-12am",
        category=PROACTIVE_AGENT,
        priority=NORMAL,
        expected_duration_seconds=120,  # 2 minutes
        description="Auto-escalation of stale insights (12 AM EST)",
        alert_on_failure=False,  # Digest only
    ),
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def get_job_config(job_name: str) -> JobConfig:
    """Get configuration for a specific job.

    Args:
        job_name: The Celery Beat schedule name

    Returns:
        JobConfig object with job metadata

    Raises:
        KeyError: If job_name is not found in JOBS dictionary
    """
    if job_name not in JOBS:
        raise KeyError(
            f"Job '{job_name}' not found in monitoring config. "
            f"Available jobs: {', '.join(JOBS.keys())}"
        )
    return JOBS[job_name]


def get_jobs_by_category(category: str) -> Dict[str, JobConfig]:
    """Get all jobs in a specific category.

    Args:
        category: Job category (e.g., 'vector_ingestion', 'notifications')

    Returns:
        Dictionary of job_name -> JobConfig for all jobs in category
    """
    return {
        name: config for name, config in JOBS.items() if config.category == category
    }


def get_jobs_by_priority(priority: str) -> Dict[str, JobConfig]:
    """Get all jobs with a specific priority level.

    Args:
        priority: Priority level ('critical', 'high', 'normal', 'low')

    Returns:
        Dictionary of job_name -> JobConfig for all jobs at priority level
    """
    return {
        name: config for name, config in JOBS.items() if config.priority == priority
    }


def get_critical_jobs() -> Dict[str, JobConfig]:
    """Get all critical jobs that require immediate alerts on failure.

    Returns:
        Dictionary of job_name -> JobConfig for all critical jobs
    """
    return get_jobs_by_priority(CRITICAL)


def should_send_immediate_alert(job_name: str) -> bool:
    """Check if a job failure should trigger an immediate alert.

    Args:
        job_name: The Celery Beat schedule name

    Returns:
        True if immediate alert should be sent, False otherwise
    """
    try:
        config = get_job_config(job_name)
        return (
            config.alert_on_failure
            and config.priority in ALERT_CONFIG["immediate_alert_priorities"]
        )
    except KeyError:
        # Unknown jobs get immediate alerts for safety
        return True


def get_all_categories() -> list[str]:
    """Get list of all job categories.

    Returns:
        List of unique category names
    """
    return list(set(config.category for config in JOBS.values()))


def get_all_priorities() -> list[str]:
    """Get list of all priority levels.

    Returns:
        List of unique priority levels
    """
    return list(set(config.priority for config in JOBS.values()))


# ============================================================================
# STATISTICS
# ============================================================================


def get_job_stats() -> Dict[str, Any]:
    """Get statistics about configured jobs.

    Returns:
        Dictionary with job count by category and priority
    """
    stats = {
        "total_jobs": len(JOBS),
        "by_category": {},
        "by_priority": {},
        "immediate_alerts_enabled": 0,
    }

    for config in JOBS.values():
        # Count by category
        stats["by_category"][config.category] = (
            stats["by_category"].get(config.category, 0) + 1
        )

        # Count by priority
        stats["by_priority"][config.priority] = (
            stats["by_priority"].get(config.priority, 0) + 1
        )

        # Count immediate alerts
        if should_send_immediate_alert(config.job_name):
            stats["immediate_alerts_enabled"] += 1

    return stats


# Print stats when module is imported (useful for debugging)
if __name__ == "__main__":
    import json

    print("\n" + "=" * 70)
    print("JOB MONITORING CONFIGURATION SUMMARY")
    print("=" * 70 + "\n")

    stats = get_job_stats()
    print(f"Total Configured Jobs: {stats['total_jobs']}")
    print(f"\nBy Category:")
    for category, count in sorted(stats["by_category"].items()):
        print(f"  {category}: {count}")

    print(f"\nBy Priority:")
    for priority, count in sorted(stats["by_priority"].items()):
        print(f"  {priority}: {count}")

    print(f"\nImmediate Alerts Enabled: {stats['immediate_alerts_enabled']} jobs")

    print("\n" + "=" * 70)
    print("CRITICAL JOBS (Immediate Alerts)")
    print("=" * 70 + "\n")

    for name, config in get_critical_jobs().items():
        print(f"  • {name}")
        print(f"    Category: {config.category}")
        print(f"    Max Duration: {config.expected_duration_seconds}s")
        print(f"    Description: {config.description}")
        print()
