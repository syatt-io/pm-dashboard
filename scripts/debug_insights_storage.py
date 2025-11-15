#!/usr/bin/env python3
"""Debug script to check insights detection and storage issues."""

import sys
import os
from datetime import datetime, timedelta, timezone
from sqlalchemy import text

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.utils.database import get_db
from src.models import ProactiveInsight, User, UserWatchedProject
from src.services.insight_detector import InsightDetector
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def check_existing_insights():
    """Check what insights are currently in the database."""
    db = next(get_db())
    try:
        # Total insights
        total = db.query(ProactiveInsight).count()
        logger.info(f"📊 Total insights in database: {total}")

        # Recent insights (last 24 hours)
        yesterday = datetime.now(timezone.utc) - timedelta(hours=24)
        recent = (
            db.query(ProactiveInsight)
            .filter(ProactiveInsight.created_at >= yesterday)
            .count()
        )
        logger.info(f"📊 Insights created in last 24 hours: {recent}")

        # Insights by type
        type_query = text(
            """
            SELECT insight_type, COUNT(*) as count
            FROM proactive_insights
            GROUP BY insight_type
            ORDER BY count DESC
        """
        )
        type_results = db.execute(type_query).fetchall()
        logger.info("📊 Insights by type:")
        for row in type_results:
            logger.info(f"  - {row.insight_type}: {row.count}")

        # Insights by severity
        severity_query = text(
            """
            SELECT severity, COUNT(*) as count
            FROM proactive_insights
            WHERE dismissed_at IS NULL
            GROUP BY severity
            ORDER BY count DESC
        """
        )
        severity_results = db.execute(severity_query).fetchall()
        logger.info("📊 Active insights by severity:")
        for row in severity_results:
            logger.info(f"  - {row.severity}: {row.count}")

        # Recent insights details
        recent_insights = (
            db.query(ProactiveInsight)
            .filter(ProactiveInsight.created_at >= yesterday)
            .order_by(ProactiveInsight.created_at.desc())
            .limit(10)
            .all()
        )

        if recent_insights:
            logger.info(f"\n📝 Recent insights (last {len(recent_insights)}):")
            for insight in recent_insights:
                logger.info(
                    f"\n  ID: {insight.id}"
                    f"\n  Type: {insight.insight_type}"
                    f"\n  Severity: {insight.severity}"
                    f"\n  Title: {insight.title}"
                    f"\n  Project: {insight.project_key or 'N/A'}"
                    f"\n  Created: {insight.created_at}"
                    f"\n  Description: {insight.description[:100]}..."
                )

    finally:
        db.close()


def test_detection_for_user(user_id: int = None):
    """Test insight detection for a specific user or first active user."""
    db = next(get_db())
    try:
        # Get user
        if user_id:
            user = db.query(User).filter(User.id == user_id).first()
        else:
            user = db.query(User).filter(User.is_active == True).first()

        if not user:
            logger.error("❌ No active user found")
            return

        logger.info(f"\n🔍 Testing insight detection for user: {user.email} (ID: {user.id})")

        # Check watched projects
        watched = (
            db.query(UserWatchedProject)
            .filter(UserWatchedProject.user_id == user.id)
            .all()
        )
        logger.info(f"👀 User watches {len(watched)} projects:")
        for wp in watched:
            logger.info(f"  - {wp.project_key}")

        # Run detection (without storing)
        detector = InsightDetector(db)
        insights = detector.detect_insights_for_user(user)

        logger.info(f"\n✅ Detected {len(insights)} insights:")
        for insight in insights:
            logger.info(
                f"\n  Type: {insight.insight_type}"
                f"\n  Severity: {insight.severity}"
                f"\n  Title: {insight.title}"
                f"\n  Project: {insight.project_key or 'N/A'}"
                f"\n  Description: {insight.description}"
                f"\n  Metadata: {insight.metadata_json}"
            )

        # Try to store them
        if insights:
            logger.info(f"\n💾 Attempting to store {len(insights)} insights...")
            try:
                stored_count = detector.store_insights(insights)
                logger.info(f"✅ Successfully stored {stored_count} insights")
            except Exception as e:
                logger.error(f"❌ Failed to store insights: {e}", exc_info=True)
                db.rollback()
        else:
            logger.info("ℹ️ No insights to store")

    except Exception as e:
        logger.error(f"❌ Error during detection test: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()


def check_detection_errors():
    """Check for common issues that prevent detection/storage."""
    db = next(get_db())
    try:
        logger.info("\n🔍 Checking for common issues...\n")

        # 1. Check active users
        active_users = db.query(User).filter(User.is_active == True).count()
        logger.info(f"👥 Active users: {active_users}")

        # 2. Check users with watched projects
        users_with_projects = (
            db.query(User)
            .join(UserWatchedProject)
            .filter(User.is_active == True)
            .distinct()
            .count()
        )
        logger.info(f"👥 Active users with watched projects: {users_with_projects}")

        # 3. Check if Tempo client can be initialized
        try:
            from src.integrations.tempo import TempoAPIClient

            tempo = TempoAPIClient()
            logger.info("✅ Tempo client initialized successfully")
        except Exception as e:
            logger.warning(f"⚠️ Tempo client initialization failed: {e}")

        # 4. Check if GitHub client can be initialized
        try:
            from config.settings import settings
            if settings.github.api_token:
                logger.info("✅ GitHub token configured")
            else:
                logger.warning("⚠️ GitHub token not configured (stale PR detection disabled)")
        except Exception as e:
            logger.warning(f"⚠️ GitHub settings check failed: {e}")

        # 5. Check for recent Tempo data
        tempo_query = text(
            """
            SELECT COUNT(*) as count
            FROM tempo_worklogs
            WHERE started >= CURRENT_DATE - INTERVAL '7 days'
        """
        )
        tempo_count = db.execute(tempo_query).scalar()
        logger.info(f"📊 Tempo worklogs in last 7 days: {tempo_count}")

        # 6. Check for recent Jira tickets
        jira_query = text(
            """
            SELECT COUNT(*) as count
            FROM jira_tickets
            WHERE updated >= CURRENT_DATE - INTERVAL '7 days'
        """
        )
        jira_count = db.execute(jira_query).scalar()
        logger.info(f"📊 Jira tickets updated in last 7 days: {jira_count}")

    except Exception as e:
        logger.error(f"❌ Error checking for issues: {e}", exc_info=True)
    finally:
        db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Debug insights detection and storage")
    parser.add_argument(
        "--check-db", action="store_true", help="Check existing insights in database"
    )
    parser.add_argument(
        "--test-detection",
        action="store_true",
        help="Test detection for a user (specify --user-id or uses first active user)",
    )
    parser.add_argument("--user-id", type=int, help="User ID to test detection for")
    parser.add_argument(
        "--check-issues", action="store_true", help="Check for common issues"
    )
    parser.add_argument("--all", action="store_true", help="Run all checks")

    args = parser.parse_args()

    if args.all:
        logger.info("=" * 80)
        logger.info("CHECKING EXISTING INSIGHTS")
        logger.info("=" * 80)
        check_existing_insights()

        logger.info("\n" + "=" * 80)
        logger.info("CHECKING FOR COMMON ISSUES")
        logger.info("=" * 80)
        check_detection_errors()

        logger.info("\n" + "=" * 80)
        logger.info("TESTING DETECTION")
        logger.info("=" * 80)
        test_detection_for_user(args.user_id)

    elif args.check_db:
        check_existing_insights()
    elif args.test_detection:
        test_detection_for_user(args.user_id)
    elif args.check_issues:
        check_detection_errors()
    else:
        parser.print_help()
        print("\n💡 Quick start: python scripts/debug_insights_storage.py --all")
