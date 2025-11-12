"""Test script for job execution tracking functionality.

This script tests the Phase 1 job monitoring implementation:
- job_monitoring_config module
- JobExecutionTracker service
- Database integration
"""

import logging
from datetime import datetime
from src.utils.database import get_db
from src.services.job_execution_tracker import JobExecutionTracker, get_recent_failures
from src.config.job_monitoring_config import (
    get_job_config,
    get_critical_jobs,
    should_send_immediate_alert,
    get_job_stats,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_config_module():
    """Test job monitoring configuration module."""
    print("\n" + "=" * 70)
    print("TEST 1: Job Monitoring Configuration")
    print("=" * 70 + "\n")

    # Test get_job_config
    try:
        config = get_job_config("ingest-slack-daily")
        print(f"✅ Successfully loaded config for 'ingest-slack-daily'")
        print(f"   Category: {config.category}")
        print(f"   Priority: {config.priority}")
        print(f"   Expected duration: {config.expected_duration_seconds}s")
        print(f"   Alert on failure: {config.alert_on_failure}")
    except Exception as e:
        print(f"❌ Failed to load job config: {e}")
        return False

    # Test get_critical_jobs
    critical_jobs = get_critical_jobs()
    print(f"\n✅ Found {len(critical_jobs)} critical jobs:")
    for job_name in list(critical_jobs.keys())[:3]:
        print(f"   - {job_name}")

    # Test should_send_immediate_alert
    should_alert = should_send_immediate_alert("ingest-slack-daily")
    print(f"\n✅ Immediate alert for ingest-slack-daily: {should_alert}")

    # Test get_job_stats
    stats = get_job_stats()
    print(f"\n✅ Job statistics:")
    print(f"   Total jobs: {stats['total_jobs']}")
    print(f"   Immediate alerts enabled: {stats['immediate_alerts_enabled']}")

    return True


def test_tracker_success():
    """Test JobExecutionTracker with successful execution."""
    print("\n" + "=" * 70)
    print("TEST 2: JobExecutionTracker - Successful Execution")
    print("=" * 70 + "\n")

    db = next(get_db())

    try:
        # Create tracker for a test job
        tracker = JobExecutionTracker(
            db_session=db,
            job_name="ingest-slack-daily",
            task_id="test-task-success-123",
            worker_name="test-worker",
            celery_queue="default",
        )

        # Start tracking
        execution = tracker.start()
        print(f"✅ Started tracking execution (ID: {execution.id})")
        print(f"   Job: {execution.job_name}")
        print(f"   Status: {execution.status}")
        print(f"   Started at: {execution.started_at}")

        # Simulate successful work
        result_data = {"success": True, "channels_processed": 5, "total_ingested": 150}
        tracker.set_result(result_data)

        # Complete tracking
        tracker.complete()
        print(f"\n✅ Completed tracking")
        print(f"   Duration: {execution.duration_seconds}s")
        print(f"   Status: {execution.status}")
        print(f"   Result data: {execution.result_data}")

        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        db.close()


def test_tracker_failure():
    """Test JobExecutionTracker with failed execution."""
    print("\n" + "=" * 70)
    print("TEST 3: JobExecutionTracker - Failed Execution")
    print("=" * 70 + "\n")

    db = next(get_db())

    try:
        # Create tracker
        tracker = JobExecutionTracker(
            db_session=db, job_name="ingest-jira-daily", task_id="test-task-failure-456"
        )

        # Start tracking
        execution = tracker.start()
        print(f"✅ Started tracking execution (ID: {execution.id})")

        # Simulate failure
        try:
            raise ValueError("Test error: Failed to connect to Jira API")
        except Exception as e:
            tracker.fail(error=e, retry_count=1)
            print(f"\n✅ Recorded failure")
            print(f"   Status: {execution.status}")
            print(f"   Error message: {execution.error_message}")
            print(f"   Retry count: {execution.retry_count}")
            print(f"   Has traceback: {execution.error_traceback is not None}")

        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        db.close()


def test_tracker_context_manager():
    """Test JobExecutionTracker context manager."""
    print("\n" + "=" * 70)
    print("TEST 4: JobExecutionTracker - Context Manager")
    print("=" * 70 + "\n")

    db = next(get_db())

    try:
        # Test successful context manager usage
        tracker = JobExecutionTracker(
            db_session=db,
            job_name="ingest-notion-daily",
            task_id="test-task-context-789",
        )

        with tracker:
            print("✅ Entered context manager")
            result = {"success": True, "pages_ingested": 42}
            tracker.set_result(result)
            print("✅ Set result data")

        print(f"✅ Exited context manager")
        print(f"   Execution status: {tracker.execution.status}")
        print(f"   Duration: {tracker.execution.duration_seconds}s")

        # Test failed context manager usage
        tracker2 = JobExecutionTracker(
            db_session=db,
            job_name="ingest-fireflies-daily",
            task_id="test-task-context-error-101",
        )

        try:
            with tracker2:
                print("\n✅ Entered context manager (will fail)")
                raise RuntimeError("Test error in context manager")
        except RuntimeError:
            print("✅ Caught expected error")
            print(f"   Execution status: {tracker2.execution.status}")
            print(f"   Error captured: {tracker2.execution.error_message}")

        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        db.close()


def test_query_helpers():
    """Test query helper functions."""
    print("\n" + "=" * 70)
    print("TEST 5: Query Helper Functions")
    print("=" * 70 + "\n")

    db = next(get_db())

    try:
        # Get recent failures
        failures = get_recent_failures(db, limit=5)
        print(f"✅ Found {len(failures)} recent failures:")
        for failure in failures[:3]:
            print(
                f"   - {failure.job_name} (ID: {failure.id}, Status: {failure.status})"
            )
            print(f"     Started: {failure.started_at}")
            if failure.error_message:
                print(f"     Error: {failure.error_message[:100]}")

        # Get recent failures for specific job
        slack_failures = get_recent_failures(db, job_name="ingest-slack-daily", limit=5)
        print(f"\n✅ Found {len(slack_failures)} failures for 'ingest-slack-daily'")

        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        db.close()


def main():
    """Run all tests."""
    print("\n" + "🔬 JOB EXECUTION TRACKING - PHASE 1 TESTS 🔬".center(70, "="))
    print("Running comprehensive tests for job monitoring system...\n")

    tests = [
        test_config_module,
        test_tracker_success,
        test_tracker_failure,
        test_tracker_context_manager,
        test_query_helpers,
    ]

    results = []
    for test_func in tests:
        try:
            result = test_func()
            results.append((test_func.__name__, result))
        except Exception as e:
            print(f"\n❌ Test {test_func.__name__} crashed: {e}")
            results.append((test_func.__name__, False))

    # Print summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70 + "\n")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")

    print(f"\n{'='*70}")
    print(f"Results: {passed}/{total} tests passed")
    print(f"{'='*70}\n")

    if passed == total:
        print("🎉 ALL TESTS PASSED! Phase 1 implementation is working correctly.")
        return 0
    else:
        print("⚠️  SOME TESTS FAILED. Review errors above.")
        return 1


if __name__ == "__main__":
    exit(main())
