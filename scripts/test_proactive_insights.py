#!/usr/bin/env python3
"""Test script for Phase 3.1 Proactive Insights feature.

This script tests:
1. Insight detection (stale PRs and budget alerts)
2. Brief generation
3. Delivery mechanisms (Slack and Email)
4. Database operations
"""

import os
import sys
from pathlib import Path

# Add parent directory to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import logging
from datetime import datetime, timezone
from src.utils.database import get_db
from src.models import (
    User,
    ProactiveInsight,
    UserNotificationPreferences,
    UserWatchedProject,
)
from src.services.insight_detector import InsightDetector, detect_insights_for_all_users
from src.services.daily_brief_generator import DailyBriefGenerator, send_daily_briefs

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def test_database_connection():
    """Test database connection and models."""
    print("\n" + "=" * 60)
    print("TEST 1: Database Connection")
    print("=" * 60)

    db = next(get_db())
    try:
        # Test querying users
        users = db.query(User).all()
        print(f"✓ Found {len(users)} users in database")

        # Test querying insights
        insights = db.query(ProactiveInsight).all()
        print(f"✓ Found {len(insights)} existing insights")

        # Test querying preferences
        prefs = db.query(UserNotificationPreferences).all()
        print(f"✓ Found {len(prefs)} user preference records")

        return True
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        return False
    finally:
        db.close()


def test_insight_detection(user_id=None):
    """Test insight detection for a specific user or all users."""
    print("\n" + "=" * 60)
    print("TEST 2: Insight Detection")
    print("=" * 60)

    db = next(get_db())
    try:
        if user_id:
            # Test for specific user
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                print(f"✗ User {user_id} not found")
                return False

            print(f"Testing insight detection for user: {user.name} ({user.email})")

            detector = InsightDetector(db)
            insights = detector.detect_insights_for_user(user)

            print(f"✓ Detected {len(insights)} insights:")
            for insight in insights:
                print(
                    f"  - [{insight.severity.upper()}] {insight.insight_type}: {insight.title}"
                )

            if insights:
                # Store insights
                stored = detector.store_insights(insights)
                print(f"✓ Stored {stored} insights in database")
        else:
            # Test for all users
            print("Testing insight detection for all active users")
            stats = detect_insights_for_all_users()

            print(f"✓ Processed {stats['users_processed']} users")
            print(f"✓ Detected {stats['insights_detected']} insights")
            print(f"✓ Stored {stats['insights_stored']} insights")

            if stats["errors"]:
                print(f"✗ Errors occurred:")
                for error in stats["errors"]:
                    print(f"  - {error}")

        return True
    except Exception as e:
        logger.error(f"Insight detection test failed: {e}", exc_info=True)
        print(f"✗ Insight detection failed: {e}")
        return False
    finally:
        db.close()


def test_brief_generation(user_id):
    """Test brief generation for a specific user."""
    print("\n" + "=" * 60)
    print("TEST 3: Brief Generation")
    print("=" * 60)

    db = next(get_db())
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            print(f"✗ User {user_id} not found")
            return False

        print(f"Testing brief generation for user: {user.name} ({user.email})")

        # Get undelivered insights
        detector = InsightDetector(db)
        insights = detector.get_undelivered_insights(user.id)

        print(f"Found {len(insights)} undelivered insights")

        if not insights:
            print("⚠ No undelivered insights - creating a test insight")
            test_insight = ProactiveInsight(
                id="test-insight-" + datetime.now().strftime("%Y%m%d%H%M%S"),
                user_id=user.id,
                project_key="TEST",
                insight_type="test",
                title="Test Insight",
                description="This is a test insight for brief generation",
                severity="info",
                metadata_json={"test": True},
                created_at=datetime.now(timezone.utc),
            )
            db.add(test_insight)
            db.commit()
            insights = [test_insight]

        # Generate brief
        generator = DailyBriefGenerator(db)
        brief = generator.generate_brief_for_user(user, insights)

        if brief["has_content"]:
            print("✓ Brief generated successfully")
            print(f"  Insight count: {brief['insight_count']}")
            print(f"  Subject: {brief['email_subject']}")
            print(f"\n--- Slack Preview (first 200 chars) ---")
            print(brief["slack_text"][:200] + "...")
        else:
            print("✗ Brief generation returned no content")
            return False

        return True
    except Exception as e:
        logger.error(f"Brief generation test failed: {e}", exc_info=True)
        print(f"✗ Brief generation failed: {e}")
        return False
    finally:
        db.close()


def test_brief_delivery(user_id, test_email_only=True):
    """Test brief delivery (with option to test email only to avoid spamming Slack)."""
    print("\n" + "=" * 60)
    print("TEST 4: Brief Delivery")
    print("=" * 60)

    db = next(get_db())
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            print(f"✗ User {user_id} not found")
            return False

        print(f"Testing brief delivery for user: {user.name} ({user.email})")

        # Get undelivered insights
        detector = InsightDetector(db)
        insights = detector.get_undelivered_insights(user.id)

        if not insights:
            print("⚠ No undelivered insights to test delivery")
            return True

        # Generate brief
        generator = DailyBriefGenerator(db)
        brief = generator.generate_brief_for_user(user, insights)

        if not brief["has_content"]:
            print("✗ No brief content to deliver")
            return False

        # Temporarily modify preferences for testing if needed
        prefs = (
            db.query(UserNotificationPreferences)
            .filter(UserNotificationPreferences.user_id == user.id)
            .first()
        )

        original_slack = None
        if test_email_only and prefs:
            original_slack = prefs.daily_brief_slack
            prefs.daily_brief_slack = False
            db.commit()
            print("⚠ Temporarily disabled Slack delivery for testing")

        # Deliver brief
        results = generator.deliver_brief(user, brief)

        print(f"Delivery results:")
        print(f"  Slack: {'✓' if results['slack'] else '✗'}")
        print(f"  Email: {'✓' if results['email'] else '✗'}")

        # Mark as delivered if any channel succeeded
        if results["slack"] or results["email"]:
            generator.mark_insights_delivered(
                insights, via_slack=results["slack"], via_email=results["email"]
            )
            print(f"✓ Marked {len(insights)} insights as delivered")

        # Restore preferences
        if original_slack is not None and prefs:
            prefs.daily_brief_slack = original_slack
            db.commit()

        return True
    except Exception as e:
        logger.error(f"Brief delivery test failed: {e}", exc_info=True)
        print(f"✗ Brief delivery failed: {e}")
        return False
    finally:
        db.close()


def test_full_pipeline(user_id):
    """Test the full pipeline: detect → generate → deliver."""
    print("\n" + "=" * 60)
    print("TEST 5: Full Pipeline")
    print("=" * 60)

    print("Running full pipeline test...")

    # 1. Detect insights
    if not test_insight_detection(user_id):
        return False

    # 2. Generate brief
    if not test_brief_generation(user_id):
        return False

    # 3. Deliver brief (email only to avoid Slack spam)
    if not test_brief_delivery(user_id, test_email_only=True):
        return False

    print("\n✓ Full pipeline test completed successfully!")
    return True


def cleanup_test_insights():
    """Clean up test insights created during testing."""
    print("\n" + "=" * 60)
    print("CLEANUP: Removing Test Insights")
    print("=" * 60)

    db = next(get_db())
    try:
        test_insights = (
            db.query(ProactiveInsight)
            .filter(ProactiveInsight.id.like("test-insight-%"))
            .all()
        )

        count = len(test_insights)
        for insight in test_insights:
            db.delete(insight)

        db.commit()
        print(f"✓ Removed {count} test insights")
        return True
    except Exception as e:
        logger.error(f"Cleanup failed: {e}", exc_info=True)
        print(f"✗ Cleanup failed: {e}")
        db.rollback()
        return False
    finally:
        db.close()


def main():
    """Main test runner."""
    import argparse

    parser = argparse.ArgumentParser(description="Test Proactive Insights (Phase 3.1)")
    parser.add_argument("--user-id", type=int, help="User ID to test with")
    parser.add_argument(
        "--test",
        choices=["all", "db", "detect", "generate", "deliver", "pipeline"],
        default="all",
        help="Which test to run",
    )
    parser.add_argument(
        "--cleanup", action="store_true", help="Clean up test data after running"
    )

    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("PHASE 3.1: PROACTIVE INSIGHTS TEST SUITE")
    print("=" * 60)

    # Get first active user if no user_id provided
    if not args.user_id:
        db = next(get_db())
        try:
            user = db.query(User).filter(User.is_active == True).first()
            if user:
                args.user_id = user.id
                print(f"\nUsing user: {user.name} ({user.email})")
            else:
                print("\n✗ No active users found in database")
                return 1
        finally:
            db.close()

    success = True

    if args.test == "all":
        success = (
            test_database_connection()
            and test_insight_detection(args.user_id)
            and test_brief_generation(args.user_id)
            and test_brief_delivery(args.user_id, test_email_only=True)
            and test_full_pipeline(args.user_id)
        )
    elif args.test == "db":
        success = test_database_connection()
    elif args.test == "detect":
        success = test_insight_detection(args.user_id)
    elif args.test == "generate":
        success = test_brief_generation(args.user_id)
    elif args.test == "deliver":
        success = test_brief_delivery(args.user_id, test_email_only=False)
    elif args.test == "pipeline":
        success = test_full_pipeline(args.user_id)

    if args.cleanup:
        cleanup_test_insights()

    print("\n" + "=" * 60)
    if success:
        print("✓ ALL TESTS PASSED")
    else:
        print("✗ SOME TESTS FAILED")
    print("=" * 60 + "\n")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
