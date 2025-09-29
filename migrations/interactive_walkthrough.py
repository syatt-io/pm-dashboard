#!/usr/bin/env python3
"""Walkthrough of interactive mode decisions."""

import asyncio
from datetime import datetime
from config.settings import settings
from src.integrations.fireflies import FirefliesClient
from src.processors.transcript_analyzer import TranscriptAnalyzer


def simulate_interactive_decisions():
    """Simulate the interactive decision-making process."""

    print("🎭 INTERACTIVE MODE WALKTHROUGH")
    print("="*50)
    print("This simulates the decisions you would make in interactive mode\n")

    # Mock decisions for each action item
    decisions = [
        {
            "action": "Investigate Amazon Project",
            "assignee": "Jessica Dutton, Mike Samimi",
            "user_choice": "jira",
            "reasoning": "Technical investigation needs ticket tracking",
            "modifications": {
                "title": "Clarify Amazon Project Status with Thomas",
                "assignee": "Mike Samimi",
                "priority": "High",
                "jira_project": "SNUGGLE",
                "issue_type": "Task"
            }
        },
        {
            "action": "Investigate Partial Fulfillments",
            "assignee": "Jessica Dutton",
            "user_choice": "jira",
            "reasoning": "Feature investigation needs proper tracking",
            "modifications": {
                "jira_project": "SNUGGLE",
                "issue_type": "Story"
            }
        },
        {
            "action": "Follow up on UI updates",
            "assignee": "Mike Samimi",
            "user_choice": "todo",
            "reasoning": "Simple follow-up, doesn't need formal ticket",
            "modifications": {
                "due_date": "2025-09-25"
            }
        },
        {
            "action": "Investigate Special Order App",
            "assignee": "Jessica Dutton",
            "user_choice": "jira",
            "reasoning": "Technical issue requiring development work",
            "modifications": {
                "priority": "High",
                "jira_project": "SNUGGLE",
                "issue_type": "Bug"
            }
        },
        {
            "action": "Follow up on Registry Report",
            "assignee": "Mike Samimi",
            "user_choice": "todo",
            "reasoning": "Status check, better as TODO",
            "modifications": {
                "due_date": "2025-09-24"
            }
        }
    ]

    print("👤 USER DECISIONS SIMULATION:")
    print("-" * 30)

    jira_count = 0
    todo_count = 0

    for i, decision in enumerate(decisions, 1):
        print(f"\n🎯 Action Item {i}: {decision['action']}")
        print(f"   Assignee: {decision['assignee']}")
        print(f"   👤 User chooses: {decision['user_choice'].upper()}")
        print(f"   💭 Reasoning: {decision['reasoning']}")

        if decision['user_choice'] == 'jira':
            jira_count += 1
            mods = decision.get('modifications', {})
            if mods:
                print(f"   ✏️  Modifications:")
                for key, value in mods.items():
                    print(f"      • {key}: {value}")
        else:
            todo_count += 1
            mods = decision.get('modifications', {})
            if mods:
                print(f"   ✏️  Modifications:")
                for key, value in mods.items():
                    print(f"      • {key}: {value}")

    print(f"\n" + "="*50)
    print("📊 FINAL CONFIRMATION")
    print("="*50)

    print(f"\n✅ Will create {jira_count} Jira tickets:")
    for decision in decisions:
        if decision['user_choice'] == 'jira':
            mods = decision.get('modifications', {})
            title = mods.get('title', decision['action'])
            project = mods.get('jira_project', 'PM')
            assignee = mods.get('assignee', decision['assignee'])
            issue_type = mods.get('issue_type', 'Task')
            print(f"   • [{project}] {title} ({issue_type}) → {assignee}")

    print(f"\n📝 Will add {todo_count} TODO items:")
    for decision in decisions:
        if decision['user_choice'] == 'todo':
            mods = decision.get('modifications', {})
            title = mods.get('title', decision['action'])
            due = mods.get('due_date', 'No due date')
            assignee = mods.get('assignee', decision['assignee'])
            print(f"   • {title} → {assignee} (Due: {due})")

    print(f"\n👤 User confirms: ✅ YES, proceed with creation")

    print(f"\n" + "="*50)
    print("🚀 SIMULATED EXECUTION")
    print("="*50)

    print("\n✅ Results:")
    print("   • 3 Jira tickets created successfully")
    print("   • 2 TODO items added to database")
    print("   • Slack notification sent to #pm-updates")
    print("   • Meeting marked as processed")

    return {
        'jira_tickets': jira_count,
        'todo_items': todo_count,
        'decisions': decisions
    }


async def show_actual_vs_interactive():
    """Compare automated vs interactive processing."""

    print("\n" + "="*60)
    print("🔄 AUTOMATED vs INTERACTIVE COMPARISON")
    print("="*60)

    # Get real analysis
    fireflies = FirefliesClient(settings.fireflies.api_key)
    analyzer = TranscriptAnalyzer()

    meetings = fireflies.get_recent_meetings(days_back=10)
    snuggle_meeting = None

    for meeting in meetings:
        if "snuggle" in meeting.get('title', '').lower():
            snuggle_meeting = meeting
            break

    if snuggle_meeting:
        transcript = fireflies.get_meeting_transcript(snuggle_meeting['id'])
        analysis = analyzer.analyze_transcript(
            transcript.transcript,
            snuggle_meeting['title'],
            transcript.date
        )

        print("\n🤖 AUTOMATED MODE (what agent would do automatically):")
        print("   • Creates Jira tickets for ALL action items")
        print("   • Uses original titles and assignments")
        print("   • Default priority: Medium")
        print("   • Default project: PM")
        print(f"   • Result: {len(analysis.action_items)} tickets in PM project")

        print("\n👤 INTERACTIVE MODE (with user control):")
        print("   • User reviews each item individually")
        print("   • Can choose Jira ticket, TODO, or skip")
        print("   • Can edit titles, assignees, priorities")
        print("   • Can set specific Jira projects")
        print("   • Result: 3 tickets (SNUGGLE project) + 2 TODOs")

        print("\n💡 BENEFITS OF INTERACTIVE MODE:")
        print("   ✅ Better organization (right items in right places)")
        print("   ✅ Proper project categorization")
        print("   ✅ Prevents ticket spam")
        print("   ✅ Maintains context and reasoning")
        print("   ✅ User stays in control")


if __name__ == "__main__":
    # Run the simulation
    results = simulate_interactive_decisions()

    # Show comparison
    asyncio.run(show_actual_vs_interactive())

    print("\n" + "="*60)
    print("🎯 HOW TO USE INTERACTIVE MODE")
    print("="*60)
    print("\n1. Run: python main_interactive.py")
    print("2. Select meeting from list (or use --meeting-id)")
    print("3. Review AI analysis and action items")
    print("4. For each item, choose: Jira / TODO / Skip")
    print("5. Optionally edit details (title, assignee, etc.)")
    print("6. Review final summary")
    print("7. Confirm to proceed")
    print("8. Get results and notifications")

    print(f"\n🎉 Interactive mode gives you full control over your PM workflow!")