#!/usr/bin/env python3
"""
Backfill epic_hours using MCP Tempo tool (FAST - no Jira API calls needed!)

The MCP Tempo tool returns IssueKey directly, avoiding 59k+ Jira API calls.
This is the approach that worked on Nov 6 for the 7 projects.
"""

import os
import sys
import re
from pathlib import Path
from datetime import datetime, date
from collections import defaultdict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.integrations.tempo import TempoAPIClient
from src.models import EpicHours
from src.utils.database import get_session
from sqlalchemy.dialects.postgresql import insert

# Process RNWL for validation
PROJECT_KEY = "RNWL"


def parse_mcp_tempo_output(output: str) -> list:
    """Parse MCP Tempo worklog output into structured data."""
    worklogs = []

    # Each worklog is on one line with pipe-separated fields
    # Format: TempoWorklogId: X | IssueKey: Y | IssueId: Z | Date: YYYY-MM-DD | Hours: H.HH | Description: ...
    lines = output.strip().split("\n")

    for line in lines:
        if not line.strip() or "TempoWorklogId" not in line:
            continue

        worklog = {}

        # Extract IssueKey
        issue_key_match = re.search(r"IssueKey:\s*([A-Z]+-\d+)", line)
        if issue_key_match:
            worklog["issue_key"] = issue_key_match.group(1)

        # Extract Date
        date_match = re.search(r"Date:\s*(\d{4}-\d{2}-\d{2})", line)
        if date_match:
            worklog["date"] = date_match.group(1)

        # Extract Hours
        hours_match = re.search(r"Hours:\s*([\d.]+)", line)
        if hours_match:
            worklog["hours"] = float(hours_match.group(1))

        # Extract Description (for epic info)
        desc_match = re.search(r"Description:\s*(.+)$", line)
        if desc_match:
            worklog["description"] = desc_match.group(1)

        if worklog.get("issue_key") and worklog.get("hours"):
            worklogs.append(worklog)

    return worklogs


def backfill_with_mcp_tempo(project_key, session):
    """Backfill epic hours using MCP Tempo tool."""
    print(f"\n{'=' * 80}")
    print(f"Backfilling {project_key} using MCP Tempo (FAST method)")
    print(f"{'=' * 80}\n")

    # Use MCP Tempo tool to fetch worklogs (2023-present)
    print("Calling MCP Tempo tool...")
    from src.services.project_activity_aggregator import (
        mcp__Jira_Tempo__retrieveWorklogs,
    )

    start_date = "2023-01-01"
    end_date = datetime.now().strftime("%Y-%m-%d")

    raw_output = mcp__Jira_Tempo__retrieveWorklogs(
        startDate=start_date, endDate=end_date
    )

    print(f"✅ Received response from MCP Tempo")

    # Parse the output
    all_worklogs = parse_mcp_tempo_output(raw_output)
    print(f"Parsed {len(all_worklogs):,} total worklogs")

    # Filter for target project
    project_worklogs = [
        w for w in all_worklogs if w["issue_key"].startswith(f"{project_key}-")
    ]
    print(f"Found {len(project_worklogs):,} worklogs for {project_key}")

    # Group by epic → month → team (using Tempo API for epic/team lookup)
    tempo = TempoAPIClient()
    epic_month_team_hours = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))

    processed = 0
    skipped = 0

    # Get epic info from Tempo attributes
    print("\nFetching epic associations from Tempo attributes...")
    tempo_worklogs = tempo.get_worklogs(start_date, end_date, project_key=project_key)

    # Build mapping: (issue_key, date) → epic_key
    epic_map = {}
    team_map = {}

    for tw in tempo_worklogs:
        issue = tw.get("issue", {})
        issue_id = issue.get("id")
        if not issue_id:
            continue

        # Get issue key from Tempo
        issue_key = tempo.get_issue_key_from_jira(str(issue_id))
        if not issue_key:
            continue

        # Get date
        worklog_date = tw.get("startDate", "")[:10]

        # Get epic from attributes
        epic_key = None
        attributes = tw.get("attributes", {})
        if attributes:
            values = attributes.get("values", [])
            for attr in values:
                if attr.get("key") == "_Epic_":
                    epic_key = attr.get("value")
                    break

        if not epic_key:
            epic_key = "NO_EPIC"

        # Get team
        author = tw.get("author", {})
        account_id = author.get("accountId")
        team = "Other"
        if account_id:
            team = tempo.get_user_team(account_id) or "Other"
            if team == "Unassigned":
                team = "Other"

        # Store mapping
        key = (issue_key, worklog_date)
        epic_map[key] = epic_key
        team_map[key] = team

    print(f"Built epic/team mappings for {len(epic_map)} worklogs")

    # Process MCP worklogs using the mappings
    print("\nProcessing worklogs with epic/team associations...")
    for worklog in project_worklogs:
        issue_key = worklog["issue_key"]
        worklog_date_str = worklog["date"]
        hours = worklog["hours"]

        # Parse date to get month
        worklog_date = datetime.strptime(worklog_date_str, "%Y-%m-%d").date()
        month = date(worklog_date.year, worklog_date.month, 1)

        # Get epic and team from mappings
        key = (issue_key, worklog_date_str)
        epic_key = epic_map.get(key, "NO_EPIC")
        team = team_map.get(key, "Other")

        # Accumulate
        epic_month_team_hours[epic_key][month][team] += hours
        processed += 1

        if processed % 500 == 0:
            print(f"  Processed {processed} worklogs...")

    print(f"\n✅ Processed {processed} worklogs")
    print(f"  Skipped: {skipped}")

    # Insert into database
    print(f"\nInserting into epic_hours table...")
    records_inserted = 0

    for epic_key, months in epic_month_team_hours.items():
        for month, teams in months.items():
            for team, hours in teams.items():
                if hours > 0:
                    stmt = insert(EpicHours).values(
                        project_key=project_key,
                        epic_key=epic_key,
                        epic_summary=epic_key,
                        month=month,
                        team=team,
                        hours=round(hours, 2),
                        created_at=datetime.now(),
                        updated_at=datetime.now(),
                    )
                    stmt = stmt.on_conflict_do_update(
                        index_elements=["project_key", "epic_key", "month", "team"],
                        set_={
                            "hours": stmt.excluded.hours,
                            "updated_at": datetime.now(),
                        },
                    )
                    session.execute(stmt)
                    records_inserted += 1

    session.commit()
    print(f"✅ Committed {records_inserted} records for {project_key}")

    return processed, records_inserted


def main():
    print("=" * 80)
    print("EPIC HOURS BACKFILL - MCP TEMPO METHOD (FAST!)")
    print("=" * 80)

    session = get_session()

    try:
        processed, inserted = backfill_with_mcp_tempo(PROJECT_KEY, session)

        print(f"\n{'=' * 80}")
        print("BACKFILL COMPLETE")
        print(f"{'=' * 80}")
        print(f"Processed: {processed:,} worklogs")
        print(f"Inserted: {inserted:,} records")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        session.rollback()
    finally:
        session.close()


if __name__ == "__main__":
    main()
