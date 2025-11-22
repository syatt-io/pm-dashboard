#!/usr/bin/env python3
"""Test the Follow-up on Last Meeting feature."""

import asyncio
from src.services.project_activity_aggregator import ProjectActivityAggregator


async def main():
    print("=" * 80)
    print("🧪 Testing Follow-up on Last Meeting Feature")
    print("=" * 80)
    print()

    # Aggregate activity
    print("📊 Aggregating activity for SUBS...")
    aggregator = ProjectActivityAggregator()
    activity = await aggregator.aggregate_project_activity(
        project_key="SUBS",
        project_name="Snuggle Bugz - Shopify",
        days_back=7,
        include_context=False,
    )

    # Show follow-up data
    if activity.last_meeting_followup:
        followup = activity.last_meeting_followup
        print(f"\n✅ Follow-up data collected:")
        print(f"   Meeting: {followup['meeting_title']}")
        print(f"   Date: {followup['meeting_date']}")
        print(f"   Topics: {len(followup['topics'])}")

        print(f"\n📋 Topics breakdown:")
        for i, topic in enumerate(followup["topics"], 1):
            status = "✅" if topic["has_activity"] else "❌"
            print(f"   {i}. {status} {topic['title']}")
            if topic["has_activity"]:
                print(
                    f"      → {len(topic['tickets'])} tickets, {len(topic['prs'])} PRs, {len(topic['slack_messages'])} Slack, {topic['time_logged']}h"
                )
    else:
        print("\n❌ No follow-up data found")
        return

    # Format digest
    print(f"\n📝 Formatting weekly digest...")
    digest = aggregator.format_client_agenda(activity)

    # Save digest
    output_file = (
        "/Users/msamimi/syatt/projects/agent-pm/test_outputs/digest_with_followup.md"
    )
    with open(output_file, "w") as f:
        f.write(digest)

    print(f"\n✅ Digest saved to: {output_file}")
    print(f"\n📄 Preview (first 1500 chars):")
    print("-" * 80)
    print(digest[:1500])
    print("-" * 80)
    print(f"\n✅ Test complete! Open the file to see full digest.")


if __name__ == "__main__":
    asyncio.run(main())
