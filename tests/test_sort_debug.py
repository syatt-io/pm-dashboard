#!/usr/bin/env python3
"""Debug script to test ticket sorting."""

import asyncio
from datetime import datetime
from src.services.jira_user_tickets_service import JiraUserTicketsService, JiraTicket


async def test_sorting():
    """Test the sorting logic."""
    # Create some test tickets with different priorities and dates
    tickets = [
        JiraTicket(
            key="TEST-1",
            summary="Old Low Priority",
            priority="Low",
            status="Open",
            project_key="TEST",
            url="https://test.atlassian.net/browse/TEST-1",
            created=datetime(2023, 1, 1),
        ),
        JiraTicket(
            key="TEST-2",
            summary="New High Priority",
            priority="High",
            status="Open",
            project_key="TEST",
            url="https://test.atlassian.net/browse/TEST-2",
            created=datetime(2024, 12, 31),
        ),
        JiraTicket(
            key="TEST-3",
            summary="Old High Priority",
            priority="High",
            status="Open",
            project_key="TEST",
            url="https://test.atlassian.net/browse/TEST-3",
            created=datetime(2023, 6, 1),
        ),
        JiraTicket(
            key="TEST-4",
            summary="New Medium Priority",
            priority="Medium",
            status="Open",
            project_key="TEST",
            url="https://test.atlassian.net/browse/TEST-4",
            created=datetime(2024, 11, 1),
        ),
    ]

    print("🧪 Testing ticket sorting\n")
    print("BEFORE sorting:")
    for t in tickets:
        print(f"  {t.key}: {t.priority:7} - {t.created.strftime('%Y-%m-%d')}")

    # Create service and sort
    service = JiraUserTicketsService()
    sorted_tickets = service._sort_tickets(tickets)

    print("\nAFTER sorting (should be: High newest first, then Medium, then Low):")
    for t in sorted_tickets:
        print(f"  {t.key}: {t.priority:7} - {t.created.strftime('%Y-%m-%d')}")

    # Expected order:
    # TEST-2: High    - 2024-12-31 (newest high)
    # TEST-3: High    - 2023-06-01 (oldest high)
    # TEST-4: Medium  - 2024-11-01 (medium)
    # TEST-1: Low     - 2023-01-01 (low)

    print("\n✅ Expected order:")
    print("  TEST-2: High    - 2024-12-31 (newest high)")
    print("  TEST-3: High    - 2023-06-01 (older high)")
    print("  TEST-4: Medium  - 2024-11-01")
    print("  TEST-1: Low     - 2023-01-01")


if __name__ == "__main__":
    asyncio.run(test_sorting())
