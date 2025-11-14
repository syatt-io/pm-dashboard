"""Proactive insight detection service for monitoring projects and surfacing important events."""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from config.settings import settings
from src.models import (
    ProactiveInsight,
    User,
    UserWatchedProject,
    ProcessedMeeting,
    MeetingMetadata,
)
from src.integrations.github_client import GitHubClient
from src.utils.database import session_scope, get_db

logger = logging.getLogger(__name__)


class InsightDetector:
    """Service for detecting proactive insights across projects."""

    def __init__(self, db: Session):
        """Initialize the insight detector.

        Args:
            db: Database session
        """
        self.db = db
        self.github_client = None
        if settings.github.api_token:
            self.github_client = GitHubClient(
                api_token=settings.github.api_token,
                organization=settings.github.organization,
            )

    def detect_insights_for_user(self, user: User) -> List[ProactiveInsight]:
        """Detect all insights for a specific user.

        Args:
            user: User to detect insights for

        Returns:
            List of detected insights
        """
        insights = []

        try:
            # Get user's watched projects
            watched_projects = (
                self.db.query(UserWatchedProject)
                .filter(UserWatchedProject.user_id == user.id)
                .all()
            )

            project_keys = [wp.project_key for wp in watched_projects]

            if not project_keys:
                logger.info(f"No watched projects for user {user.id}")
                return insights

            # Run all detectors
            insights.extend(self._detect_stale_prs(user, project_keys))
            insights.extend(self._detect_budget_alerts(user, project_keys))
            insights.extend(self._detect_anomaly(user, project_keys))
            insights.extend(self._detect_meeting_prep(user, project_keys))

            logger.info(f"Detected {len(insights)} insights for user {user.id}")

        except Exception as e:
            logger.error(
                f"Error detecting insights for user {user.id}: {e}", exc_info=True
            )

        return insights

    def _detect_stale_prs(
        self, user: User, project_keys: List[str]
    ) -> List[ProactiveInsight]:
        """Detect stale PRs that need review.

        Args:
            user: User to detect insights for
            project_keys: List of project keys to monitor

        Returns:
            List of stale PR insights
        """
        insights = []

        if not self.github_client:
            logger.warning("GitHub client not configured, skipping stale PR detection")
            return insights

        try:
            # Define stale threshold (3 days)
            stale_threshold = datetime.now(timezone.utc) - timedelta(days=3)

            # Get open PRs
            prs = self.github_client.list_pull_requests(state="open")

            for pr in prs:
                try:
                    # Check if PR is stale (older than 3 days, no reviews)
                    created_at = datetime.fromisoformat(
                        pr["created_at"].replace("Z", "+00:00")
                    )

                    if created_at > stale_threshold:
                        continue  # Not stale yet

                    # Check if already alerted in last 24 hours
                    if self._recently_alerted(user.id, "stale_pr", pr["number"]):
                        continue

                    # Get review count
                    reviews = self.github_client.get_pr_reviews(pr["number"])
                    if len(reviews) > 0:
                        continue  # Has reviews, not stale

                    # Calculate days open
                    days_open = (datetime.now(timezone.utc) - created_at).days

                    # Create insight
                    insight = ProactiveInsight(
                        id=str(uuid.uuid4()),
                        user_id=user.id,
                        project_key=None,  # Could map repo to project if needed
                        insight_type="stale_pr",
                        title=f"PR #{pr['number']} needs review",
                        description=f"Pull request '{pr['title']}' has been open for {days_open} days without reviews.",
                        severity="warning",
                        metadata_json={
                            "pr_number": pr["number"],
                            "pr_url": pr["html_url"],
                            "pr_title": pr["title"],
                            "days_open": days_open,
                            "author": pr["user"]["login"],
                            "repo": pr["base"]["repo"]["name"],
                        },
                        created_at=datetime.now(timezone.utc),
                    )

                    insights.append(insight)

                except Exception as e:
                    logger.error(f"Error processing PR {pr.get('number')}: {e}")
                    continue

            logger.info(f"Detected {len(insights)} stale PRs for user {user.id}")

        except Exception as e:
            logger.error(f"Error detecting stale PRs: {e}", exc_info=True)

        return insights

    def _detect_budget_alerts(
        self, user: User, project_keys: List[str]
    ) -> List[ProactiveInsight]:
        """Detect budget alerts for projects.

        Args:
            user: User to detect insights for
            project_keys: List of project keys to monitor

        Returns:
            List of budget alert insights
        """
        insights = []

        try:
            from src.database import SessionLocal
            from sqlalchemy import text

            # Get project budget status from tempo_hours_log and projects
            for project_key in project_keys:
                try:
                    # Check if already alerted in last week
                    if self._recently_alerted(
                        user.id, "budget_alert", project_key, days=7
                    ):
                        continue

                    # Query to get current month's hours and budget
                    # Uses pre-calculated hours from project_monthly_forecast (updated by nightly Tempo sync)
                    query = text(
                        """
                        SELECT
                            pmf.project_key,
                            pmf.forecasted_hours as budget,
                            COALESCE(pmf.actual_monthly_hours, 0) as hours_used
                        FROM project_monthly_forecast pmf
                        WHERE pmf.project_key = :project_key
                            AND pmf.month_year = DATE_TRUNC('month', CURRENT_DATE)
                    """
                    )

                    result = self.db.execute(
                        query, {"project_key": project_key}
                    ).fetchone()

                    if not result or not result.budget:
                        continue

                    budget = float(result.budget)
                    hours_used = float(result.hours_used)
                    usage_pct = (hours_used / budget * 100) if budget > 0 else 0

                    # Calculate time passed in month
                    now = datetime.now(timezone.utc)
                    days_in_month = (
                        datetime(now.year, now.month + 1 if now.month < 12 else 1, 1)
                        - timedelta(days=1)
                    ).day
                    days_passed = now.day
                    time_passed_pct = days_passed / days_in_month * 100

                    # Alert if >75% budget used with >40% time remaining
                    if usage_pct >= 75 and (100 - time_passed_pct) >= 40:
                        # Determine severity
                        if usage_pct >= 90:
                            severity = "critical"
                        else:
                            severity = "warning"

                        insight = ProactiveInsight(
                            id=str(uuid.uuid4()),
                            user_id=user.id,
                            project_key=project_key,
                            insight_type="budget_alert",
                            title=f"{project_key} approaching budget limit",
                            description=f"Project has used {usage_pct:.0f}% of budget with {100 - time_passed_pct:.0f}% of month remaining. Consider scope adjustment.",
                            severity=severity,
                            metadata_json={
                                "project_key": project_key,
                                "budget_used_pct": round(usage_pct, 1),
                                "time_passed_pct": round(time_passed_pct, 1),
                                "hours_used": round(hours_used, 1),
                                "hours_budgeted": round(budget, 1),
                                "hours_remaining": round(budget - hours_used, 1),
                            },
                            created_at=datetime.now(timezone.utc),
                        )

                        insights.append(insight)

                except Exception as e:
                    logger.error(
                        f"Error checking budget for project {project_key}: {e}"
                    )
                    continue

            logger.info(f"Detected {len(insights)} budget alerts for user {user.id}")

        except Exception as e:
            logger.error(f"Error detecting budget alerts: {e}", exc_info=True)

        return insights

    def _detect_anomaly(
        self, user: User, project_keys: List[str]
    ) -> List[ProactiveInsight]:
        """Detect anomalies in project patterns (hours, velocity, meetings).

        Args:
            user: User to detect insights for
            project_keys: List of project keys to monitor

        Returns:
            List of anomaly insights
        """
        insights = []

        try:
            from sqlalchemy import text
            from src.integrations.tempo import TempoAPIClient

            # Initialize Tempo client for worklog queries
            try:
                tempo_client = TempoAPIClient()
            except Exception as e:
                logger.warning(f"Could not initialize Tempo client: {e}")
                tempo_client = None

            for project_key in project_keys:
                try:
                    # Check if already alerted in last 3 days (avoid alert fatigue)
                    if self._recently_alerted(user.id, "anomaly", project_key, days=3):
                        continue

                    # 1. HOURS DEVIATION ANOMALY
                    hours_anomaly = self._detect_hours_anomaly(
                        project_key, tempo_client
                    )
                    if hours_anomaly:
                        insight = ProactiveInsight(
                            id=str(uuid.uuid4()),
                            user_id=user.id,
                            project_key=project_key,
                            insight_type="anomaly",
                            title=hours_anomaly["title"],
                            description=hours_anomaly["description"],
                            severity=hours_anomaly["severity"],
                            metadata_json=hours_anomaly["metadata"],
                            created_at=datetime.now(timezone.utc),
                        )
                        insights.append(insight)

                    # 2. TICKET VELOCITY ANOMALY
                    velocity_anomaly = self._detect_velocity_anomaly(project_key)
                    if velocity_anomaly:
                        insight = ProactiveInsight(
                            id=str(uuid.uuid4()),
                            user_id=user.id,
                            project_key=project_key,
                            insight_type="anomaly",
                            title=velocity_anomaly["title"],
                            description=velocity_anomaly["description"],
                            severity=velocity_anomaly["severity"],
                            metadata_json=velocity_anomaly["metadata"],
                            created_at=datetime.now(timezone.utc),
                        )
                        insights.append(insight)

                    # 3. MEETING PATTERN ANOMALY
                    meeting_anomaly = self._detect_meeting_anomaly(project_key)
                    if meeting_anomaly:
                        insight = ProactiveInsight(
                            id=str(uuid.uuid4()),
                            user_id=user.id,
                            project_key=project_key,
                            insight_type="anomaly",
                            title=meeting_anomaly["title"],
                            description=meeting_anomaly["description"],
                            severity=meeting_anomaly["severity"],
                            metadata_json=meeting_anomaly["metadata"],
                            created_at=datetime.now(timezone.utc),
                        )
                        insights.append(insight)

                except Exception as e:
                    logger.error(
                        f"Error detecting anomalies for project {project_key}: {e}"
                    )
                    continue

            logger.info(f"Detected {len(insights)} anomaly insights for user {user.id}")

        except Exception as e:
            logger.error(f"Error in anomaly detection: {e}", exc_info=True)

        return insights

    def _detect_hours_anomaly(
        self, project_key: str, tempo_client: Optional[Any]
    ) -> Optional[Dict]:
        """Detect unusual hours patterns for a project.

        Args:
            project_key: Project to analyze
            tempo_client: Tempo API client instance

        Returns:
            Anomaly dict if detected, None otherwise
        """
        try:
            if not tempo_client:
                return None

            # Get hours for last 4 weeks (7-day periods)
            weekly_hours = []
            for week_offset in range(4):
                end_date = datetime.now() - timedelta(weeks=week_offset)
                start_date = end_date - timedelta(days=7)

                date_range_hours = tempo_client.get_date_range_hours(
                    start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")
                )

                hours = date_range_hours.get(project_key, 0)
                weekly_hours.append(hours)

            if len(weekly_hours) < 2:
                return None

            # Current week is first element (most recent)
            current_week_hours = weekly_hours[0]
            baseline_hours = sum(weekly_hours[1:]) / len(weekly_hours[1:])

            # Skip if baseline is too low (not enough activity)
            if baseline_hours < 2:
                return None

            # Calculate deviation percentage
            if baseline_hours > 0:
                deviation_pct = (
                    (current_week_hours - baseline_hours) / baseline_hours
                ) * 100
            else:
                deviation_pct = 0

            # Threshold: 40% deviation (configurable)
            THRESHOLD = 40

            if abs(deviation_pct) >= THRESHOLD:
                if deviation_pct > 0:
                    # Hours spike
                    severity = "warning" if deviation_pct < 75 else "critical"
                    title = f"{project_key}: Unusual hours increase detected"
                    description = (
                        f"Hours logged this week ({current_week_hours:.1f}h) are "
                        f"{abs(deviation_pct):.0f}% higher than 4-week average ({baseline_hours:.1f}h). "
                        f"This may indicate scope creep or resource constraints."
                    )
                else:
                    # Hours drop
                    severity = "warning"
                    title = f"{project_key}: Significant hours decrease detected"
                    description = (
                        f"Hours logged this week ({current_week_hours:.1f}h) are "
                        f"{abs(deviation_pct):.0f}% lower than 4-week average ({baseline_hours:.1f}h). "
                        f"This may indicate project delays or resource reallocation."
                    )

                return {
                    "title": title,
                    "description": description,
                    "severity": severity,
                    "metadata": {
                        "project_key": project_key,
                        "current_week_hours": round(current_week_hours, 1),
                        "baseline_hours": round(baseline_hours, 1),
                        "deviation_pct": round(deviation_pct, 1),
                        "anomaly_type": (
                            "hours_spike" if deviation_pct > 0 else "hours_drop"
                        ),
                        "weekly_hours_history": [round(h, 1) for h in weekly_hours],
                    },
                }

        except Exception as e:
            logger.error(f"Error detecting hours anomaly for {project_key}: {e}")
            return None

        return None

    def _detect_velocity_anomaly(self, project_key: str) -> Optional[Dict]:
        """Detect unusual ticket velocity patterns.

        Args:
            project_key: Project to analyze

        Returns:
            Anomaly dict if detected, None otherwise
        """
        try:
            from sqlalchemy import text

            # Query ticket closures for last 4 weeks
            query = text(
                """
                WITH weekly_closures AS (
                    SELECT
                        DATE_TRUNC('week', resolved_at) as week_start,
                        COUNT(*) as tickets_closed
                    FROM jira_tickets
                    WHERE project_key = :project_key
                        AND resolved_at >= CURRENT_DATE - INTERVAL '28 days'
                        AND resolved_at IS NOT NULL
                    GROUP BY DATE_TRUNC('week', resolved_at)
                    ORDER BY week_start DESC
                )
                SELECT
                    week_start,
                    tickets_closed
                FROM weekly_closures
            """
            )

            result = self.db.execute(query, {"project_key": project_key}).fetchall()

            if len(result) < 2:
                return None

            # Current week (most recent) vs baseline (average of previous weeks)
            current_week_tickets = result[0].tickets_closed if len(result) > 0 else 0
            baseline_tickets = (
                sum(r.tickets_closed for r in result[1:]) / len(result[1:])
                if len(result) > 1
                else 0
            )

            # Skip if baseline is too low
            if baseline_tickets < 2:
                return None

            # Calculate deviation
            if baseline_tickets > 0:
                deviation_pct = (
                    (current_week_tickets - baseline_tickets) / baseline_tickets
                ) * 100
            else:
                deviation_pct = 0

            # Threshold: 40% drop (we care about velocity drops more than spikes)
            if deviation_pct <= -40:
                severity = "warning" if deviation_pct > -60 else "critical"
                title = f"{project_key}: Ticket velocity drop detected"
                description = (
                    f"Tickets closed this week ({current_week_tickets}) are "
                    f"{abs(deviation_pct):.0f}% lower than 4-week average ({baseline_tickets:.1f}). "
                    f"This may indicate blockers, resource constraints, or process issues."
                )

                return {
                    "title": title,
                    "description": description,
                    "severity": severity,
                    "metadata": {
                        "project_key": project_key,
                        "current_week_tickets": current_week_tickets,
                        "baseline_tickets": round(baseline_tickets, 1),
                        "deviation_pct": round(deviation_pct, 1),
                        "anomaly_type": "velocity_drop",
                    },
                }

        except Exception as e:
            logger.error(f"Error detecting velocity anomaly for {project_key}: {e}")
            return None

        return None

    def _detect_meeting_anomaly(self, project_key: str) -> Optional[Dict]:
        """Detect unusual meeting patterns (consecutive skips).

        Args:
            project_key: Project to analyze

        Returns:
            Anomaly dict if detected, None otherwise
        """
        try:
            from sqlalchemy import desc

            # Get recurring meetings for this project
            recurring_meetings = (
                self.db.query(MeetingMetadata)
                .filter(
                    MeetingMetadata.project_key == project_key,
                    MeetingMetadata.recurrence_pattern.isnot(None),
                )
                .all()
            )

            for meeting in recurring_meetings:
                try:
                    # Check if meeting was expected but didn't happen
                    if not meeting.next_expected:
                        continue

                    # If next_expected is in the past by more than 2 days, it was likely skipped
                    now = datetime.now(timezone.utc)
                    days_overdue = (now - meeting.next_expected).days

                    if days_overdue >= 2:
                        # Check for consecutive skips by looking at recent meeting history
                        recent_meetings = (
                            self.db.query(ProcessedMeeting)
                            .filter(
                                ProcessedMeeting.title.ilike(
                                    f"%{meeting.normalized_title}%"
                                )
                            )
                            .order_by(desc(ProcessedMeeting.date))
                            .limit(5)
                            .all()
                        )

                        # Count consecutive skips
                        expected_interval_days = {
                            "daily": 1,
                            "weekly": 7,
                            "biweekly": 14,
                            "monthly": 30,
                        }.get(meeting.recurrence_pattern, 7)

                        skipped_count = 0
                        if recent_meetings:
                            last_meeting_date = recent_meetings[0].date
                            expected_meetings = (
                                now - last_meeting_date
                            ).days // expected_interval_days
                            actual_meetings = len(recent_meetings)
                            skipped_count = expected_meetings - actual_meetings

                        # Alert if 2+ consecutive skips
                        if skipped_count >= 2:
                            severity = "warning"
                            title = (
                                f"{project_key}: Recurring meeting pattern disrupted"
                            )
                            description = (
                                f"Meeting '{meeting.meeting_title}' has been skipped {skipped_count} times "
                                f"consecutively. This may indicate team availability issues or project deprioritization."
                            )

                            return {
                                "title": title,
                                "description": description,
                                "severity": severity,
                                "metadata": {
                                    "project_key": project_key,
                                    "meeting_title": meeting.meeting_title,
                                    "meeting_type": meeting.meeting_type,
                                    "recurrence_pattern": meeting.recurrence_pattern,
                                    "consecutive_skips": skipped_count,
                                    "last_occurrence": (
                                        meeting.last_occurrence.isoformat()
                                        if meeting.last_occurrence
                                        else None
                                    ),
                                    "anomaly_type": "meeting_skip",
                                },
                            }

                except Exception as e:
                    logger.error(f"Error checking meeting {meeting.meeting_title}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error detecting meeting anomaly for {project_key}: {e}")
            return None

        return None

    def _detect_meeting_prep(
        self, user: User, project_keys: List[str]
    ) -> List[ProactiveInsight]:
        """Generate meeting prep for projects with meetings today.

        Args:
            user: User to detect insights for
            project_keys: List of project keys to monitor

        Returns:
            List of meeting prep insights
        """
        insights = []

        try:
            from sqlalchemy import text

            # Get current weekday name (lowercase: "monday", "tuesday", etc.)
            today_weekday = datetime.now(timezone.utc).strftime("%A").lower()

            for project_key in project_keys:
                try:
                    # Check if already generated today
                    if self._recently_alerted(
                        user.id, "meeting_prep", project_key, days=1
                    ):
                        continue

                    # Query projects table for meeting day
                    query = text(
                        """
                        SELECT weekly_meeting_day
                        FROM projects
                        WHERE key = :project_key
                    """
                    )
                    result = self.db.execute(
                        query, {"project_key": project_key}
                    ).fetchone()

                    if not result or not result.weekly_meeting_day:
                        continue

                    # Check if today is meeting day
                    if result.weekly_meeting_day.lower() != today_weekday:
                        continue

                    logger.info(
                        f"Generating meeting prep insight for {project_key} (meeting day: {today_weekday})"
                    )

                    # Create insight that prompts user to generate digest
                    insight = ProactiveInsight(
                        id=str(uuid.uuid4()),
                        user_id=user.id,
                        project_key=project_key,
                        insight_type="meeting_prep",
                        title=f"{project_key}: Meeting prep for today's sync",
                        description=f"Your weekly {project_key} meeting is scheduled today. Click to view the weekly digest with latest activity, action items, and proposed agenda.",
                        severity="info",
                        metadata_json={
                            "meeting_day": today_weekday,
                            "project_key": project_key,
                            "digest_url": f"/api/project-digest/{project_key}",
                            "action": "view_digest",
                            "suggested_params": {"days": 7, "include_context": True},
                        },
                        created_at=datetime.now(timezone.utc),
                    )

                    insights.append(insight)
                    logger.info(f"Created meeting prep insight for {project_key}")

                except Exception as e:
                    logger.error(
                        f"Error generating meeting prep for {project_key}: {e}",
                        exc_info=True,
                    )
                    continue

            logger.info(
                f"Generated {len(insights)} meeting prep insights for user {user.id}"
            )

        except Exception as e:
            logger.error(f"Error in meeting prep detection: {e}", exc_info=True)

        return insights

    def _recently_alerted(
        self, user_id: int, insight_type: str, identifier: Any, days: int = 1
    ) -> bool:
        """Check if user was recently alerted about this insight.

        Args:
            user_id: User ID
            insight_type: Type of insight
            identifier: Unique identifier for the insight (PR number, project key, etc.)
            days: Number of days to check back

        Returns:
            True if recently alerted, False otherwise
        """
        try:
            threshold = datetime.now(timezone.utc) - timedelta(days=days)

            # Check if similar insight exists recently
            existing = (
                self.db.query(ProactiveInsight)
                .filter(
                    ProactiveInsight.user_id == user_id,
                    ProactiveInsight.insight_type == insight_type,
                    ProactiveInsight.created_at >= threshold,
                )
                .all()
            )

            # Check if any match the identifier
            for insight in existing:
                if insight.metadata_json:
                    # For PRs, check pr_number
                    if (
                        insight_type == "stale_pr"
                        and insight.metadata_json.get("pr_number") == identifier
                    ):
                        return True
                    # For budget alerts, check project_key
                    if (
                        insight_type == "budget_alert"
                        and insight.metadata_json.get("project_key") == identifier
                    ):
                        return True
                    # For anomalies, check project_key
                    if (
                        insight_type == "anomaly"
                        and insight.metadata_json.get("project_key") == identifier
                    ):
                        return True
                    # For meeting prep, check project_key
                    if (
                        insight_type == "meeting_prep"
                        and insight.metadata_json.get("project_key") == identifier
                    ):
                        return True

            return False

        except Exception as e:
            logger.error(f"Error checking recent alerts: {e}")
            return False

    def store_insights(self, insights: List[ProactiveInsight]) -> int:
        """Store detected insights in database.

        Args:
            insights: List of insights to store

        Returns:
            Number of insights stored
        """
        try:
            for insight in insights:
                self.db.add(insight)

            self.db.commit()
            logger.info(f"Stored {len(insights)} insights")
            return len(insights)

        except Exception as e:
            logger.error(f"Error storing insights: {e}", exc_info=True)
            self.db.rollback()
            return 0

    def get_undelivered_insights(self, user_id: int) -> List[ProactiveInsight]:
        """Get insights that haven't been delivered to user yet.

        Args:
            user_id: User ID

        Returns:
            List of undelivered insights
        """
        try:
            insights = (
                self.db.query(ProactiveInsight)
                .filter(
                    ProactiveInsight.user_id == user_id,
                    ProactiveInsight.dismissed_at.is_(None),
                    ProactiveInsight.delivered_via_slack.is_(None),
                    ProactiveInsight.delivered_via_email.is_(None),
                )
                .order_by(
                    ProactiveInsight.severity.desc(), ProactiveInsight.created_at.desc()
                )
                .all()
            )

            return insights

        except Exception as e:
            logger.error(f"Error getting undelivered insights: {e}", exc_info=True)
            return []


def detect_insights_for_all_users(db: Optional[Session] = None) -> Dict[str, Any]:
    """Detect insights for all active users.

    This is the main entry point for the scheduled job.

    Args:
        db: Optional database session to use. If not provided, creates a new one.
            IMPORTANT: When called from Celery tasks, always pass the tracker's session
            to avoid duplicate sessions and potential hangs.

    Returns:
        Dictionary with detection statistics
    """
    stats = {
        "users_processed": 0,
        "insights_detected": 0,
        "insights_stored": 0,
        "errors": [],
    }

    # Use provided session or create new one
    should_close_db = False
    if db is None:
        db = next(get_db())
        should_close_db = True

    try:
        # Get all active users with watched projects
        users = db.query(User).filter(User.is_active == True).all()

        for user in users:
            try:
                detector = InsightDetector(db)
                insights = detector.detect_insights_for_user(user)

                if insights:
                    stored = detector.store_insights(insights)
                    stats["insights_detected"] += len(insights)
                    stats["insights_stored"] += stored

                stats["users_processed"] += 1

            except Exception as e:
                logger.error(
                    f"Error detecting insights for user {user.id}: {e}", exc_info=True
                )
                stats["errors"].append(f"User {user.id}: {str(e)}")
                # CRITICAL: Rollback transaction to prevent "InFailedSqlTransaction" errors
                # If we don't rollback, the session remains in a failed state and all
                # subsequent operations will fail
                try:
                    db.rollback()
                except Exception as rollback_error:
                    logger.error(f"Error rolling back transaction: {rollback_error}")
                continue

        logger.info(f"Insight detection complete: {stats}")

    except Exception as e:
        logger.error(f"Error in insight detection job: {e}", exc_info=True)
        stats["errors"].append(str(e))
    finally:
        # Only close if we created the session
        if should_close_db:
            db.close()

    return stats
