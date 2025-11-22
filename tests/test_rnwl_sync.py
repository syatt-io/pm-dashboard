#!/usr/bin/env python3
"""
Test epic hours sync for RNWL project only (using proven backfill approach)
"""
import os
import pytest
import sys
from pathlib import Path
from datetime import datetime, date
from collections import defaultdict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.integrations.tempo import TempoAPIClient

# Just test RNWL
PROJECT_KEY = "RNWL"


@pytest.fixture
def tempo():
    """Create TempoAPIClient instance for testing."""
    return TempoAPIClient()


def test_rnwl_sync(tempo):
    """Test epic hours extraction for RNWL."""
    print(f"\n{'=' * 80}")
    print(f"Testing Epic Hours Sync for {PROJECT_KEY}")
    print(f"{'=' * 80}\n")

    # Fetch all worklogs for last 2 years
    start_date = "2023-01-01"
    end_date = datetime.now().strftime("%Y-%m-%d")

    print(f"Fetching worklogs from {start_date} to {end_date}...")
    worklogs = tempo.get_worklogs(from_date=start_date, to_date=end_date)

    if not worklogs:
        print("  No worklogs found")
        return

    print(f"✅ Found {len(worklogs)} total worklogs\n")

    # Group by epic → month → team
    epic_month_team_hours = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))

    processed = 0
    skipped = 0
    rnwl_count = 0

    print("Processing worklogs...")
    for idx, worklog in enumerate(worklogs):
        # Get issue key for this worklog
        issue = worklog.get("issue", {})
        issue_id = issue.get("id")
        if not issue_id:
            skipped += 1
            continue

        # Resolve issue ID to key via Jira API
        issue_key = tempo.get_issue_key_from_jira(issue_id)
        if not issue_key:
            skipped += 1
            continue

        # Extract project key from issue key (e.g., "RNWL-123" → "RNWL")
        project_key = issue_key.split("-")[0] if "-" in issue_key else None
        if not project_key or project_key != PROJECT_KEY:
            skipped += 1
            continue

        rnwl_count += 1

        # Get epic from worklog attributes (Tempo stores this)
        epic_key = None
        attributes = worklog.get("attributes", {})
        if attributes:
            values = attributes.get("values", [])
            for attr in values:
                if attr.get("key") == "_Epic_":
                    epic_key = attr.get("value")
                    break

        if not epic_key:
            epic_key = "NO_EPIC"

        # Get month from worklog date
        started = worklog.get("startDate")
        if not started:
            skipped += 1
            continue

        worklog_date = datetime.strptime(started[:10], "%Y-%m-%d").date()
        month = date(worklog_date.year, worklog_date.month, 1)

        # Get hours
        time_spent_seconds = worklog.get("timeSpentSeconds", 0)
        hours = time_spent_seconds / 3600.0

        # Get team from account ID
        author = worklog.get("author", {})
        account_id = author.get("accountId")
        if account_id:
            team = tempo.get_user_team(account_id)
            if not team or team == "Unassigned":
                team = "Other"
        else:
            team = "Other"

        # Accumulate
        epic_month_team_hours[epic_key][month][team] += hours
        processed += 1

        if processed % 500 == 0:
            print(f"  Processed {processed} RNWL worklogs...")

    print(f"\n{'=' * 80}")
    print("RESULTS")
    print(f"{'=' * 80}\n")

    print(f"Total worklogs fetched: {len(worklogs):,}")
    print(f"RNWL worklogs: {rnwl_count:,}")
    print(f"Successfully processed: {processed:,}")
    print(f"Skipped: {skipped:,}\n")

    # Show epic breakdown
    print(f"{'=' * 80}")
    print(f"Epic Breakdown for {PROJECT_KEY}")
    print(f"{'=' * 80}\n")

    total_hours = 0
    for epic_key in sorted(epic_month_team_hours.keys()):
        epic_total = sum(
            sum(teams.values()) for teams in epic_month_team_hours[epic_key].values()
        )
        total_hours += epic_total
        num_months = len(epic_month_team_hours[epic_key])

        print(f"{epic_key}:")
        print(f"  Total hours: {epic_total:,.1f}")
        print(f"  Months with data: {num_months}")

        # Show team breakdown
        team_totals = defaultdict(float)
        for month_data in epic_month_team_hours[epic_key].values():
            for team, hours in month_data.items():
                team_totals[team] += hours

        if team_totals:
            print(f"  Teams:")
            for team, hours in sorted(team_totals.items()):
                print(f"    {team}: {hours:,.1f} hours")
        print()

    print(f"{'=' * 80}")
    print(f"TOTAL HOURS: {total_hours:,.1f}")
    print(f"{'=' * 80}\n")

    # Check for NO_EPIC percentage
    if "NO_EPIC" in epic_month_team_hours:
        no_epic_hours = sum(
            sum(teams.values()) for teams in epic_month_team_hours["NO_EPIC"].values()
        )
        no_epic_pct = (no_epic_hours / total_hours * 100) if total_hours > 0 else 0
        print(f"⚠️  NO_EPIC: {no_epic_hours:,.1f} hours ({no_epic_pct:.1f}% of total)")

    epics_with_data = len([e for e in epic_month_team_hours.keys() if e != "NO_EPIC"])
    print(f"✅ Epics with data: {epics_with_data}")
    print()


def main():
    print("=" * 80)
    print("RNWL EPIC HOURS SYNC TEST")
    print("Using proven backfill script approach (Tempo attributes only)")
    print("=" * 80)

    tempo = TempoAPIClient()

    try:
        test_rnwl_sync(tempo)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return

    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
