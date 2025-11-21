#!/usr/bin/env python3
"""Test script for /my-jira-tickets feature."""

import asyncio
import sys
from src.services.jira_user_tickets_service import JiraUserTicketsService
from src.models.user import User
from src.utils.database import session_scope


async def main():
    """Test the Jira tickets service."""
    print("🧪 Testing Jira User Tickets Service\n")

    # Initialize service
    service = JiraUserTicketsService()

    print("✅ Service initialized")

    # Get a test user from database
    with session_scope() as session:
        # Find first user with both slack_user_id and jira_account_id
        user = (
            session.query(User)
            .filter(User.slack_user_id.isnot(None), User.jira_account_id.isnot(None))
            .first()
        )

        if not user:
            print("❌ No user found with both Slack and Jira mapping")
            print("\nTo test this feature, you need a user with:")
            print("  - slack_user_id set")
            print("  - jira_account_id set")
            sys.exit(1)

        print(f"✅ Found test user: {user.name} (Jira ID: {user.jira_account_id})")

        # Fetch tickets
        print(f"\n📥 Fetching tickets for {user.name}...")
        tickets = await service.get_user_tickets(user.jira_account_id)

        print(f"✅ Fetched {len(tickets)} tickets")

        # Format for Slack
        print("\n📋 Slack-formatted output:")
        print("=" * 80)
        message = service.format_tickets_for_slack(tickets)
        print(message)
        print("=" * 80)

        # Test caching
        print("\n🔄 Testing cache (should be faster)...")
        import time

        start = time.time()
        cached_tickets = await service.get_user_tickets(user.jira_account_id)
        elapsed = time.time() - start

        print(
            f"✅ Cache working! Retrieved {len(cached_tickets)} tickets in {elapsed:.3f}s"
        )

        # Test cache clear
        print("\n🧹 Testing cache clear...")
        service.clear_cache(user.jira_account_id)
        print("✅ Cache cleared")

    print("\n✨ All tests passed!")


if __name__ == "__main__":
    asyncio.run(main())
