#!/usr/bin/env python3
"""Production endpoint tests for agent-pm application."""

import requests
import json
import time
import sys

BASE_URL = "https://agent-pm-tsbbb.ondigitalocean.app"

def test_health_check():
    """Test the health endpoint."""
    try:
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        if response.status_code == 200:
            print("✅ Health check passed")
            return True
        else:
            print(f"❌ Health check failed: Status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

def test_watched_projects():
    """Test the watched projects endpoint."""
    try:
        response = requests.get(f"{BASE_URL}/api/watched-projects", timeout=10)
        if response.status_code in [200, 401]:  # 401 is OK if not authenticated
            print(f"✅ Watched projects endpoint responding (Status: {response.status_code})")
            return True
        else:
            print(f"❌ Watched projects failed: Status {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False
    except Exception as e:
        print(f"❌ Watched projects failed: {e}")
        return False

def test_fireflies_validate():
    """Test the Fireflies API key validation endpoint."""
    try:
        # Test with invalid key first (should still respond without errors)
        response = requests.post(
            f"{BASE_URL}/api/user/fireflies-key/validate",
            json={"api_key": "test_key_12345"},
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        if response.status_code in [200, 400, 401, 403]:
            print(f"✅ Fireflies validation endpoint responding (Status: {response.status_code})")
            return True
        else:
            print(f"❌ Fireflies validation failed: Status {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False
    except Exception as e:
        print(f"❌ Fireflies validation failed: {e}")
        return False

def test_jira_projects():
    """Test the Jira projects endpoint."""
    try:
        response = requests.get(f"{BASE_URL}/api/jira/projects", timeout=10)
        if response.status_code in [200, 401]:  # 401 is OK if not authenticated
            print(f"✅ Jira projects endpoint responding (Status: {response.status_code})")
            return True
        else:
            print(f"❌ Jira projects failed: Status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Jira projects failed: {e}")
        return False

def run_all_tests():
    """Run all production tests."""
    print(f"\n{'='*60}")
    print(f"Running Production Tests for {BASE_URL}")
    print(f"{'='*60}\n")

    tests = [
        ("Health Check", test_health_check),
        ("Watched Projects", test_watched_projects),
        ("Fireflies Validation", test_fireflies_validate),
        ("Jira Projects", test_jira_projects)
    ]

    results = []
    for test_name, test_func in tests:
        print(f"\nTesting: {test_name}")
        print("-" * 40)
        result = test_func()
        results.append((test_name, result))
        time.sleep(1)  # Small delay between tests

    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print(f"{'='*60}")

    passed = 0
    failed = 0
    for test_name, result in results:
        status = "PASSED" if result else "FAILED"
        symbol = "✅" if result else "❌"
        print(f"{symbol} {test_name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1

    print(f"\nTotal: {passed} passed, {failed} failed")
    print(f"{'='*60}\n")

    return failed == 0

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)