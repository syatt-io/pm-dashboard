#!/usr/bin/env python3
"""Test script for /my-jira-tickets parameter parsing and service functionality."""

import asyncio
import sys
import pytest
from src.services.jira_user_tickets_service import JiraUserTicketsService
from src.models.user import User
from src.utils.database import session_scope


def test_parameter_parsing():
    """Test parameter parsing logic."""
    print("🧪 Testing parameter parsing logic\n")

    test_cases = [
        ("", None, 20),  # No params - defaults
        ("--project SUBS", "SUBS", 20),  # Project only
        ("--project=SUBS", "SUBS", 20),  # Project with =
        ("--num-results 50", None, 50),  # Num results only
        ("--num-results=50", None, 50),  # Num results with =
        ("--project SUBS --num-results 10", "SUBS", 10),  # Both params
        ("--num-results 30 --project SATG", "SATG", 30),  # Reversed order
        ("--project=SUBS --num-results=5", "SUBS", 5),  # Both with =
    ]

    all_passed = True

    for text, expected_project, expected_max in test_cases:
        # Parse parameters (simulating the Slack command handler logic)
        project_key = None
        max_results = 20  # Default

        if text:
            args = text.split()
            i = 0
            while i < len(args):
                # Handle --project PROJ or --project=PROJ
                if args[i] == "--project" and i + 1 < len(args):
                    project_key = args[i + 1].upper()
                    i += 2
                    continue
                elif args[i].startswith("--project="):
                    project_key = args[i].split("=", 1)[1].upper()
                    i += 1
                    continue
                # Handle --num-results N or --num-results=N
                elif args[i] == "--num-results" and i + 1 < len(args):
                    try:
                        max_results = int(args[i + 1])
                        i += 2
                        continue
                    except ValueError:
                        print(f"  ❌ FAIL: Invalid num-results for '{text}'")
                        all_passed = False
                        break
                elif args[i].startswith("--num-results="):
                    try:
                        max_results = int(args[i].split("=", 1)[1])
                        i += 1
                        continue
                    except (ValueError, IndexError):
                        print(f"  ❌ FAIL: Invalid num-results for '{text}'")
                        all_passed = False
                        break

        # Verify results
        passed = project_key == expected_project and max_results == expected_max
        status = "✅ PASS" if passed else "❌ FAIL"

        print(f"{status}: '{text}'")
        print(f"  Expected: project={expected_project}, max={expected_max}")
        print(f"  Got:      project={project_key}, max={max_results}")
        print()

        if not passed:
            all_passed = False

    return all_passed


@pytest.mark.asyncio
async def test_service_with_params():
    """Test the service with different parameter combinations."""
    print("🧪 Testing JiraUserTicketsService with parameters\n")

    service = JiraUserTicketsService()

    # Get a test user from database
    with session_scope() as session:
        user = (
            session.query(User)
            .filter(User.slack_user_id.isnot(None), User.jira_account_id.isnot(None))
            .first()
        )

        if not user:
            print("❌ No user found with both Slack and Jira mapping")
            return False

        print(f"✅ Found test user: {user.name} (Jira ID: {user.jira_account_id})\n")

        # Test 1: Default parameters
        print("Test 1: Default parameters (20 tickets, no project filter)")
        tickets = await service.get_user_tickets(
            jira_account_id=user.jira_account_id,
        )
        print(f"  ✅ Fetched {len(tickets)} tickets")
        print()

        # Test 2: Custom max_results
        print("Test 2: Custom max_results (5 tickets)")
        tickets = await service.get_user_tickets(
            jira_account_id=user.jira_account_id,
            max_results=5,
        )
        print(f"  ✅ Fetched {len(tickets)} tickets (should be ≤5)")
        if len(tickets) > 5:
            print(f"  ❌ FAIL: Expected ≤5 tickets, got {len(tickets)}")
            return False
        print()

        # Test 3: Project filter (use first ticket's project if available)
        if tickets:
            project_key = tickets[0].project_key
            print(f"Test 3: Project filter (project={project_key})")
            tickets = await service.get_user_tickets(
                jira_account_id=user.jira_account_id,
                project_key=project_key,
            )
            print(f"  ✅ Fetched {len(tickets)} tickets from project {project_key}")

            # Verify all tickets are from the specified project
            wrong_project = [t for t in tickets if t.project_key != project_key]
            if wrong_project:
                print(
                    f"  ❌ FAIL: Found {len(wrong_project)} tickets from wrong project!"
                )
                return False
            print()

        # Test 4: Both parameters
        print("Test 4: Both parameters (project + max_results)")
        if tickets:
            project_key = tickets[0].project_key
            tickets = await service.get_user_tickets(
                jira_account_id=user.jira_account_id,
                project_key=project_key,
                max_results=3,
            )
            print(
                f"  ✅ Fetched {len(tickets)} tickets from {project_key} (should be ≤3)"
            )
            if len(tickets) > 3:
                print(f"  ❌ FAIL: Expected ≤3 tickets, got {len(tickets)}")
                return False
            print()

        # Test 5: Cache key uniqueness
        print("Test 5: Cache key uniqueness (different params = different cache)")

        # Clear cache first
        service.clear_cache(user.jira_account_id)

        # Fetch with different parameters - should create 2 cache entries
        await service.get_user_tickets(
            jira_account_id=user.jira_account_id,
            max_results=10,
        )
        await service.get_user_tickets(
            jira_account_id=user.jira_account_id,
            max_results=20,
        )

        # Check cache has 2 entries
        cache_entries = [
            k for k in service._cache.keys() if k.startswith(f"{user.jira_account_id}:")
        ]
        print(f"  ✅ Created {len(cache_entries)} cache entries (expected 2)")
        if len(cache_entries) != 2:
            print(f"  ❌ FAIL: Expected 2 cache entries, got {len(cache_entries)}")
            return False

        print(f"  Cache keys: {cache_entries}")
        print()

    print("✨ All service tests passed!")
    return True


async def main():
    """Run all tests."""
    print("=" * 80)
    print("Testing /my-jira-tickets parameter support")
    print("=" * 80)
    print()

    # Test 1: Parameter parsing
    parsing_passed = test_parameter_parsing()

    if not parsing_passed:
        print("❌ Parameter parsing tests FAILED")
        sys.exit(1)

    print("✅ Parameter parsing tests PASSED\n")
    print("=" * 80)
    print()

    # Test 2: Service with parameters
    service_passed = await test_service_with_params()

    if not service_passed:
        print("\n❌ Service tests FAILED")
        sys.exit(1)

    print("\n✅ All tests PASSED!")


if __name__ == "__main__":
    asyncio.run(main())
