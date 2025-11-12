#!/usr/bin/env python3
"""Test meeting prep insight detection."""

import os
import sys
from datetime import datetime, timezone

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.utils.database import get_session
from src.models.user import User
from src.services.insight_detector import InsightDetector


def test_meeting_prep():
    """Test meeting prep insight detection for today's weekday."""
    db = get_session()

    try:
        # Get today's weekday (lowercase: "monday", "tuesday", etc.)
        today_weekday = datetime.now(timezone.utc).strftime("%A").lower()
        print(f"Today is: {today_weekday}")
        print()

        # Get a test user
        user = db.query(User).first()
        if not user:
            print("❌ No users found in database")
            return

        print(f"Testing for user: {user.email} (ID: {user.id})")
        print()

        # Create detector
        detector = InsightDetector(db)

        # Run detection
        print("Running insight detection...")
        insights = detector.detect_insights_for_user(user)

        # Filter for meeting prep insights
        meeting_prep_insights = [
            i for i in insights if i.insight_type == "meeting_prep"
        ]

        print(f"Total insights detected: {len(insights)}")
        print(f"Meeting prep insights: {len(meeting_prep_insights)}")
        print()

        if meeting_prep_insights:
            print("✅ Meeting prep insights generated:")
            for insight in meeting_prep_insights:
                print(f"\n  Project: {insight.project_key}")
                print(f"  Title: {insight.title}")
                print(f"  Description: {insight.description}")
                print(f"  Severity: {insight.severity}")
                print(f"  Metadata: {insight.metadata_json}")
        else:
            print(f"ℹ️ No meeting prep insights for today ({today_weekday})")
            print("   This is expected if no projects have meetings scheduled today.")

            # Show which projects have meeting days set
            from sqlalchemy import text

            query = text(
                "SELECT key, weekly_meeting_day FROM projects WHERE weekly_meeting_day IS NOT NULL"
            )
            results = db.execute(query).fetchall()

            if results:
                print("\n   Projects with meeting days configured:")
                for row in results:
                    marker = (
                        "👉"
                        if row.weekly_meeting_day.lower() == today_weekday
                        else "  "
                    )
                    print(f"   {marker} {row.key}: {row.weekly_meeting_day}")
            else:
                print("\n   No projects have meeting days configured yet.")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    test_meeting_prep()
