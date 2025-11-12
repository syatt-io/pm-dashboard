#!/usr/bin/env python3
"""
Test optimized epic hours sync with description extraction
"""
import os
import sys
import re
from pathlib import Path
from datetime import datetime, date
from collections import defaultdict
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.integrations.tempo import TempoAPIClient

PROJECT_KEY = "RNWL"


def test_optimized_sync():
    """Test optimized sync with description extraction."""
    print(f"\n{'=' * 80}")
    print(f"Testing Optimized Epic Hours Sync for {PROJECT_KEY}")
    print(f"{'=' * 80}\n")

    tempo = TempoAPIClient()

    # Fetch worklogs (2023-present)
    start_date = "2023-01-01"
    end_date = datetime.now().strftime("%Y-%m-%d")

    print(f"Fetching worklogs from {start_date} to {end_date}...")
    print(
        "(Note: project_key filter doesn't work server-side, still fetches all worklogs)"
    )

    start_time = datetime.now()
    worklogs = tempo.get_worklogs(start_date, end_date, project_key=PROJECT_KEY)
    fetch_duration = (datetime.now() - start_time).total_seconds()

    print(f"✅ Fetched {len(worklogs):,} total worklogs in {fetch_duration:.1f}s\n")

    # Process with OPTIMIZED approach (description extraction first)
    print("Processing worklogs with OPTIMIZED approach (description extraction)...")

    # Issue key pattern: PROJECT-NUMBER (e.g., RNWL-123)
    issue_pattern = re.compile(r"([A-Z]+-\d+)")

    fast_path_count = 0  # Issue key from description
    slow_path_count = 0  # Jira API lookup needed
    rnwl_count = 0
    processed = 0
    skipped = 0

    epic_month_team_hours = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))

    process_start = datetime.now()

    for idx, worklog in enumerate(worklogs):
        issue = worklog.get("issue", {})
        issue_id = issue.get("id")
        if not issue_id:
            skipped += 1
            continue

        # OPTIMIZED: Try description extraction FIRST
        issue_key = None
        description = worklog.get("description", "")

        # Fast path: Extract from description
        issue_match = issue_pattern.search(description)
        if issue_match:
            issue_key = issue_match.group(1)
            fast_path_count += 1
        else:
            # Fallback: Jira API lookup (slow but accurate)
            issue_key = tempo.get_issue_key_from_jira(issue_id)
            slow_path_count += 1

        if not issue_key:
            skipped += 1
            continue

        # Filter for RNWL
        project_key = issue_key.split("-")[0] if "-" in issue_key else None
        if not project_key or project_key != PROJECT_KEY:
            continue

        rnwl_count += 1

        # Get epic from Tempo attributes
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

        # Get month
        started = worklog.get("startDate")
        if not started:
            skipped += 1
            continue

        worklog_date = datetime.strptime(started[:10], "%Y-%m-%d").date()
        month = date(worklog_date.year, worklog_date.month, 1)

        # Get hours
        time_spent_seconds = worklog.get("timeSpentSeconds", 0)
        hours = time_spent_seconds / 3600.0

        # Get team
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
            print(
                f"  Processed {processed} RNWL worklogs... (fast: {fast_path_count}, slow: {slow_path_count})"
            )

    process_duration = (datetime.now() - process_start).total_seconds()

    print(f"\n{'=' * 80}")
    print("OPTIMIZATION RESULTS")
    print(f"{'=' * 80}\n")

    print(f"Total worklogs fetched: {len(worklogs):,}")
    print(f"RNWL worklogs: {rnwl_count:,}")
    print(f"Successfully processed: {processed:,}")
    print(f"Skipped: {skipped:,}\n")

    print(f"🚀 OPTIMIZATION METRICS:")
    print(
        f"  Fast path (description): {fast_path_count:,} ({fast_path_count / len(worklogs) * 100:.1f}%)"
    )
    print(
        f"  Slow path (Jira API): {slow_path_count:,} ({slow_path_count / len(worklogs) * 100:.1f}%)"
    )
    print(f"  API calls avoided: {fast_path_count:,}")
    print(f"\n⏱️  PERFORMANCE:")
    print(f"  Fetch time: {fetch_duration:.1f}s")
    print(f"  Processing time: {process_duration:.1f}s")
    print(f"  Total time: {fetch_duration + process_duration:.1f}s")

    # Estimate time saved
    if fast_path_count > 0:
        api_calls_saved = fast_path_count
        time_saved = (
            api_calls_saved * 0.1
        )  # Each API call takes ~0.1s with rate limiting
        print(
            f"  Estimated time saved: {time_saved / 60:.1f} minutes ({time_saved:.0f}s)"
        )

    # Show epic breakdown
    print(f"\n{'=' * 80}")
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


if __name__ == "__main__":
    test_optimized_sync()
