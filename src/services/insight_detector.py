"""Proactive insight detection service for monitoring projects and surfacing important events."""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from config.settings import settings
from src.models import ProactiveInsight, User, UserWatchedProject
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
        if settings.github.token:
            self.github_client = GitHubClient(
                token=settings.github.token,
                organization=settings.github.organization
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
            watched_projects = self.db.query(UserWatchedProject).filter(
                UserWatchedProject.user_id == user.id
            ).all()

            project_keys = [wp.project_key for wp in watched_projects]

            if not project_keys:
                logger.info(f"No watched projects for user {user.id}")
                return insights

            # Run all detectors
            insights.extend(self._detect_stale_prs(user, project_keys))
            insights.extend(self._detect_budget_alerts(user, project_keys))

            logger.info(f"Detected {len(insights)} insights for user {user.id}")

        except Exception as e:
            logger.error(f"Error detecting insights for user {user.id}: {e}", exc_info=True)

        return insights

    def _detect_stale_prs(self, user: User, project_keys: List[str]) -> List[ProactiveInsight]:
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
            prs = self.github_client.list_pull_requests(state='open')

            for pr in prs:
                try:
                    # Check if PR is stale (older than 3 days, no reviews)
                    created_at = datetime.fromisoformat(pr['created_at'].replace('Z', '+00:00'))

                    if created_at > stale_threshold:
                        continue  # Not stale yet

                    # Check if already alerted in last 24 hours
                    if self._recently_alerted(user.id, 'stale_pr', pr['number']):
                        continue

                    # Get review count
                    reviews = self.github_client.get_pr_reviews(pr['number'])
                    if len(reviews) > 0:
                        continue  # Has reviews, not stale

                    # Calculate days open
                    days_open = (datetime.now(timezone.utc) - created_at).days

                    # Create insight
                    insight = ProactiveInsight(
                        id=str(uuid.uuid4()),
                        user_id=user.id,
                        project_key=None,  # Could map repo to project if needed
                        insight_type='stale_pr',
                        title=f"PR #{pr['number']} needs review",
                        description=f"Pull request '{pr['title']}' has been open for {days_open} days without reviews.",
                        severity='warning',
                        metadata_json={
                            'pr_number': pr['number'],
                            'pr_url': pr['html_url'],
                            'pr_title': pr['title'],
                            'days_open': days_open,
                            'author': pr['user']['login'],
                            'repo': pr['base']['repo']['name']
                        },
                        created_at=datetime.now(timezone.utc)
                    )

                    insights.append(insight)

                except Exception as e:
                    logger.error(f"Error processing PR {pr.get('number')}: {e}")
                    continue

            logger.info(f"Detected {len(insights)} stale PRs for user {user.id}")

        except Exception as e:
            logger.error(f"Error detecting stale PRs: {e}", exc_info=True)

        return insights

    def _detect_budget_alerts(self, user: User, project_keys: List[str]) -> List[ProactiveInsight]:
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
                    if self._recently_alerted(user.id, 'budget_alert', project_key, days=7):
                        continue

                    # Query to get current month's hours and budget
                    query = text("""
                        SELECT
                            p.project_key,
                            p.monthly_forecasted_hours as budget,
                            COALESCE(SUM(th.hours), 0) as hours_used
                        FROM projects p
                        LEFT JOIN tempo_hours_log th ON th.project_key = p.project_key
                            AND DATE_TRUNC('month', th.date) = DATE_TRUNC('month', CURRENT_DATE)
                        WHERE p.project_key = :project_key
                        GROUP BY p.project_key, p.monthly_forecasted_hours
                    """)

                    result = self.db.execute(query, {'project_key': project_key}).fetchone()

                    if not result or not result.budget:
                        continue

                    budget = float(result.budget)
                    hours_used = float(result.hours_used)
                    usage_pct = (hours_used / budget * 100) if budget > 0 else 0

                    # Calculate time passed in month
                    now = datetime.now(timezone.utc)
                    days_in_month = (datetime(now.year, now.month + 1 if now.month < 12 else 1, 1) - timedelta(days=1)).day
                    days_passed = now.day
                    time_passed_pct = (days_passed / days_in_month * 100)

                    # Alert if >75% budget used with >40% time remaining
                    if usage_pct >= 75 and (100 - time_passed_pct) >= 40:
                        # Determine severity
                        if usage_pct >= 90:
                            severity = 'critical'
                        else:
                            severity = 'warning'

                        insight = ProactiveInsight(
                            id=str(uuid.uuid4()),
                            user_id=user.id,
                            project_key=project_key,
                            insight_type='budget_alert',
                            title=f"{project_key} approaching budget limit",
                            description=f"Project has used {usage_pct:.0f}% of budget with {100 - time_passed_pct:.0f}% of month remaining. Consider scope adjustment.",
                            severity=severity,
                            metadata_json={
                                'project_key': project_key,
                                'budget_used_pct': round(usage_pct, 1),
                                'time_passed_pct': round(time_passed_pct, 1),
                                'hours_used': round(hours_used, 1),
                                'hours_budgeted': round(budget, 1),
                                'hours_remaining': round(budget - hours_used, 1)
                            },
                            created_at=datetime.now(timezone.utc)
                        )

                        insights.append(insight)

                except Exception as e:
                    logger.error(f"Error checking budget for project {project_key}: {e}")
                    continue

            logger.info(f"Detected {len(insights)} budget alerts for user {user.id}")

        except Exception as e:
            logger.error(f"Error detecting budget alerts: {e}", exc_info=True)

        return insights

    def _recently_alerted(self, user_id: int, insight_type: str, identifier: Any, days: int = 1) -> bool:
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
            existing = self.db.query(ProactiveInsight).filter(
                ProactiveInsight.user_id == user_id,
                ProactiveInsight.insight_type == insight_type,
                ProactiveInsight.created_at >= threshold
            ).all()

            # Check if any match the identifier
            for insight in existing:
                if insight.metadata_json:
                    # For PRs, check pr_number
                    if insight_type == 'stale_pr' and insight.metadata_json.get('pr_number') == identifier:
                        return True
                    # For budget alerts, check project_key
                    if insight_type == 'budget_alert' and insight.metadata_json.get('project_key') == identifier:
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
            insights = self.db.query(ProactiveInsight).filter(
                ProactiveInsight.user_id == user_id,
                ProactiveInsight.dismissed_at.is_(None),
                ProactiveInsight.delivered_via_slack.is_(None),
                ProactiveInsight.delivered_via_email.is_(None)
            ).order_by(
                ProactiveInsight.severity.desc(),
                ProactiveInsight.created_at.desc()
            ).all()

            return insights

        except Exception as e:
            logger.error(f"Error getting undelivered insights: {e}", exc_info=True)
            return []


def detect_insights_for_all_users() -> Dict[str, Any]:
    """Detect insights for all active users.

    This is the main entry point for the scheduled job.

    Returns:
        Dictionary with detection statistics
    """
    stats = {
        'users_processed': 0,
        'insights_detected': 0,
        'insights_stored': 0,
        'errors': []
    }

    db = next(get_db())

    try:
        # Get all active users with watched projects
        users = db.query(User).filter(
            User.is_active == True
        ).all()

        for user in users:
            try:
                detector = InsightDetector(db)
                insights = detector.detect_insights_for_user(user)

                if insights:
                    stored = detector.store_insights(insights)
                    stats['insights_detected'] += len(insights)
                    stats['insights_stored'] += stored

                stats['users_processed'] += 1

            except Exception as e:
                logger.error(f"Error detecting insights for user {user.id}: {e}", exc_info=True)
                stats['errors'].append(f"User {user.id}: {str(e)}")
                continue

        logger.info(f"Insight detection complete: {stats}")

    except Exception as e:
        logger.error(f"Error in insight detection job: {e}", exc_info=True)
        stats['errors'].append(str(e))
    finally:
        db.close()

    return stats
