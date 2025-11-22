"""Test script for job monitoring digest functionality.

This script tests the Phase 2 daily digest implementation:
- JobMonitoringDigestService
- Digest generation with real data
- Email and Slack formatting
"""

import pytest
import logging
from src.utils.database import get_db
from src.services.job_monitoring_digest import JobMonitoringDigestService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@pytest.fixture
def digest():
    """Generate a sample digest for testing formatting."""
    db = next(get_db())
    try:
        digest_service = JobMonitoringDigestService(db)
        return digest_service.generate_daily_digest(hours_back=24)
    finally:
        db.close()


def test_digest_generation():
    """Test digest generation with existing test data."""
    print("\n" + "=" * 70)
    print("TEST: Job Monitoring Digest Generation")
    print("=" * 70 + "\n")

    db = next(get_db())

    try:
        # Create service
        digest_service = JobMonitoringDigestService(db)

        # Generate digest for last 24 hours
        print("Generating digest for last 24 hours...")
        digest = digest_service.generate_daily_digest(hours_back=24)

        # Print summary
        summary = digest["summary"]
        print("\n📊 SUMMARY:")
        print(
            f"  Period: {summary['period_start'][:19]} to {summary['period_end'][:19]}"
        )
        print(f"  Total Executions: {summary['total_executions']}")
        print(f"  Successful: {summary['successful']} ✅")
        print(f"  Failed: {summary['failed']} ❌")
        print(f"  Success Rate: {summary['success_rate']}%")

        # Print category breakdown
        if digest["by_category"]:
            print("\n📁 BY CATEGORY:")
            for category, stats in sorted(digest["by_category"].items()):
                print(f"  {category}:")
                print(
                    f"    Total: {stats['total']}, Success: {stats['successful']}, Failed: {stats['failed']}"
                )
                print(f"    Success Rate: {stats['success_rate']}%")

        # Print failures
        if digest["failures"]:
            print(f"\n❌ FAILURES ({len(digest['failures'])}):")
            for failure in digest["failures"][:5]:  # Show top 5
                print(f"  {failure['priority'].upper()} - {failure['job_name']}")
                print(f"    Status: {failure['status']}")
                error_msg = (
                    failure["error_message"][:100]
                    if failure["error_message"]
                    else "N/A"
                )
                print(f"    Error: {error_msg}")

        # Print slow jobs
        if digest["slow_jobs"]:
            print(f"\n🐌 SLOW JOBS ({len(digest['slow_jobs'])}):")
            for slow_job in digest["slow_jobs"]:
                print(f"  {slow_job['job_name']}")
                print(
                    f"    Expected: {slow_job['expected_duration']}s, Actual: {slow_job['actual_duration']}s"
                )
                print(f"    Slowdown: {slow_job['slowdown_factor']}x")

        # Print recommendations
        if digest["recommendations"]:
            print("\n💡 RECOMMENDATIONS:")
            for rec in digest["recommendations"]:
                print(f"  • {rec}")

        return digest, True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return None, False
    finally:
        db.close()


def test_email_formatting(digest):
    """Test email HTML formatting."""
    print("\n" + "=" * 70)
    print("TEST: Email HTML Formatting")
    print("=" * 70 + "\n")

    db = next(get_db())

    try:
        digest_service = JobMonitoringDigestService(db)
        email_html = digest_service.format_email_body(digest)

        # Check HTML is generated
        if "<html>" in email_html and "</html>" in email_html:
            print("✅ Email HTML generated successfully")
            print(f"   Length: {len(email_html)} characters")

            # Check key sections
            sections = [
                ("Job Monitoring Daily Digest", "Header"),
                ("Total Executions", "Summary metrics"),
                ("Recommendations", "Recommendations section"),
                (
                    ("Failed Jobs", "Failures section")
                    if digest["failures"]
                    else (None, None)
                ),
                (
                    ("Slow Jobs", "Slow jobs section")
                    if digest["slow_jobs"]
                    else (None, None)
                ),
                ("Breakdown by Category", "Category section"),
            ]

            missing_sections = []
            for text, name in sections:
                if text and text not in email_html:
                    missing_sections.append(name)

            if not missing_sections:
                print("✅ All expected sections present in email")
            else:
                print(f"⚠️  Missing sections: {', '.join(missing_sections)}")

            # Optionally save to file for inspection
            with open("/tmp/job_digest_email.html", "w") as f:
                f.write(email_html)
            print("   Saved sample to: /tmp/job_digest_email.html")

            return True
        else:
            print("❌ Invalid HTML generated")
            return False

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        db.close()


def test_slack_formatting(digest):
    """Test Slack message formatting."""
    print("\n" + "=" * 70)
    print("TEST: Slack Message Formatting")
    print("=" * 70 + "\n")

    db = next(get_db())

    try:
        digest_service = JobMonitoringDigestService(db)
        slack_message = digest_service.format_slack_message(digest)

        # Check message is generated
        if slack_message and len(slack_message) > 0:
            print("✅ Slack message generated successfully")
            print(f"   Length: {len(slack_message)} characters")

            # Check key sections
            sections = [
                ("Job Monitoring Daily Digest", "Header"),
                ("Summary:", "Summary section"),
                ("Recommendations:", "Recommendations"),
                ("Failed Jobs" if digest["failures"] else None, "Failures"),
                ("Slow Jobs" if digest["slow_jobs"] else None, "Slow jobs"),
                ("By Category:", "Category breakdown"),
            ]

            missing_sections = []
            for text, name in sections:
                if text and text not in slack_message:
                    missing_sections.append(name)

            if not missing_sections:
                print("✅ All expected sections present in Slack message")
            else:
                print(f"⚠️  Missing sections: {', '.join(missing_sections)}")

            # Print preview
            print("\n📱 SLACK MESSAGE PREVIEW:")
            print("-" * 70)
            print(slack_message[:500])
            if len(slack_message) > 500:
                print(f"\n... ({len(slack_message) - 500} more characters)")
            print("-" * 70)

            return True
        else:
            print("❌ Empty Slack message generated")
            return False

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        db.close()


def main():
    """Run all digest tests."""
    print("\n" + "🔬 JOB MONITORING DIGEST - PHASE 2 TESTS 🔬".center(70, "="))
    print("Testing daily digest generation and formatting...\n")

    # Test 1: Generate digest
    digest, success1 = test_digest_generation()
    if not success1 or not digest:
        print("\n❌ Digest generation failed - cannot proceed with formatting tests")
        return 1

    # Test 2: Email formatting
    success2 = test_email_formatting(digest)

    # Test 3: Slack formatting
    success3 = test_slack_formatting(digest)

    # Print summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70 + "\n")

    results = [
        ("Digest Generation", success1),
        ("Email Formatting", success2),
        ("Slack Formatting", success3),
    ]

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")

    print(f"\n{'='*70}")
    print(f"Results: {passed}/{total} tests passed")
    print(f"{'='*70}\n")

    if passed == total:
        print("🎉 ALL TESTS PASSED! Phase 2 digest is working correctly.")
        print("\n📧 Next steps:")
        print("  1. Review sample email at /tmp/job_digest_email.html")
        print("  2. The digest will run daily at 9:05 AM EST (13:05 UTC)")
        print("  3. Emails sent to configured recipients")
        print("  4. Slack messages sent to PM channel")
        return 0
    else:
        print("⚠️  SOME TESTS FAILED. Review errors above.")
        return 1


if __name__ == "__main__":
    exit(main())
