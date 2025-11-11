"""
Backfill epic_hours table with historical data from Tempo API.

Fetches worklog data for all 7 projects and stores by:
- Project
- Epic
- Month
- Team (discipline)
"""

import os
import sys
from pathlib import Path
from datetime import datetime, date
from collections import defaultdict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.integrations.tempo import TempoAPIClient
from src.models import EpicHours
from src.utils.database import get_session
from sqlalchemy.dialects.postgresql import insert

# Just process RNWL for validation
PROJECTS = ['RNWL']


def backfill_all_projects(tempo, session):
    """Backfill epic hours for all projects."""
    print(f"\nFetching ALL worklogs from Tempo API...")

    # Fetch all worklogs for last 2 years
    start_date = '2023-01-01'
    end_date = datetime.now().strftime('%Y-%m-%d')

    print(f"  Date range: {start_date} to {end_date}")
    worklogs = tempo.get_worklogs(
        from_date=start_date,
        to_date=end_date
    )

    if not worklogs:
        print("  No worklogs found")
        return

    print(f"  Found {len(worklogs)} total worklogs")

    # Group by project → epic → month → team
    project_epic_month_team_hours = defaultdict(
        lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    )

    processed = 0
    skipped = 0

    for worklog in worklogs:
        # Get issue key for this worklog
        issue = worklog.get('issue', {})
        issue_id = issue.get('id')
        if not issue_id:
            skipped += 1
            continue

        # Resolve issue ID to key via Jira API
        issue_key = tempo.get_issue_key_from_jira(issue_id)
        if not issue_key:
            skipped += 1
            continue

        # Extract project key from issue key (e.g., "BIGO-123" → "BIGO")
        project_key = issue_key.split('-')[0] if '-' in issue_key else None
        if not project_key or project_key not in PROJECTS:
            skipped += 1
            continue

        # Get epic from worklog attributes (Tempo stores this)
        epic_key = None
        attributes = worklog.get('attributes', {})
        if attributes:
            values = attributes.get('values', [])
            for attr in values:
                if attr.get('key') == '_Epic_':
                    epic_key = attr.get('value')
                    break

        if not epic_key:
            epic_key = 'NO_EPIC'

        # Get month from worklog date
        started = worklog.get('startDate')
        if not started:
            skipped += 1
            continue

        worklog_date = datetime.strptime(started[:10], '%Y-%m-%d').date()
        month = date(worklog_date.year, worklog_date.month, 1)

        # Get hours
        time_spent_seconds = worklog.get('timeSpentSeconds', 0)
        hours = time_spent_seconds / 3600.0

        # Get team from account ID
        author = worklog.get('author', {})
        account_id = author.get('accountId')
        if account_id:
            team = tempo.get_user_team(account_id)
            if not team or team == 'Unassigned':
                team = 'Other'
        else:
            team = 'Other'

        # Accumulate
        project_epic_month_team_hours[project_key][epic_key][month][team] += hours
        processed += 1

        if processed % 500 == 0:
            print(f"  Processed {processed} worklogs...")

    print(f"\n  Total processed: {processed}")
    print(f"  Total skipped: {skipped}")

    # Insert into database
    print(f"\n  Inserting records into epic_hours table...")
    records_inserted = 0

    for project_key, epics in project_epic_month_team_hours.items():
        print(f"\n  {project_key}: {len(epics)} epics")

        for epic_key, months in epics.items():
            for month, teams in months.items():
                for team, hours in teams.items():
                    if hours > 0:
                        # Upsert
                        stmt = insert(EpicHours).values(
                            project_key=project_key,
                            epic_key=epic_key,
                            epic_summary=epic_key,  # We'll update summaries later
                            month=month,
                            team=team,
                            hours=round(hours, 2),
                            created_at=datetime.now(),
                            updated_at=datetime.now()
                        )
                        stmt = stmt.on_conflict_do_update(
                            index_elements=['project_key', 'epic_key', 'month', 'team'],
                            set_={
                                'hours': stmt.excluded.hours,
                                'updated_at': datetime.now()
                            }
                        )
                        session.execute(stmt)
                        records_inserted += 1

        session.commit()
        print(f"    ✅ Committed {records_inserted} records for {project_key}")

    print(f"\n  Total records inserted/updated: {records_inserted}")


def main():
    print("=" * 80)
    print("BACKFILLING EPIC HOURS FROM TEMPO API")
    print("=" * 80)

    tempo = TempoAPIClient()
    session = get_session()

    try:
        backfill_all_projects(tempo, session)
    except Exception as e:
        print(f"\n❌ Error during backfill: {e}")
        import traceback
        traceback.print_exc()
        session.rollback()
        session.close()
        return

    # Close session after successful backfill
    session.close()

    print("\n" + "=" * 80)
    print("BACKFILL COMPLETE")
    print("=" * 80)

    # Create NEW session for summary queries (don't reuse closed session)
    session = get_session()
    try:
        # Show summary
        total = session.query(EpicHours).count()
        projects_count = session.query(EpicHours.project_key).distinct().count()
        epics_count = session.query(EpicHours.epic_key).distinct().count()

        print(f"\nTotal records: {total:,}")
        print(f"Projects: {projects_count}")
        print(f"Unique epics: {epics_count}")

        # Show breakdown by project
        print("\nRecords by project:")
        for project_key in PROJECTS:
            count = session.query(EpicHours).filter_by(project_key=project_key).count()
            print(f"  {project_key}: {count:,} records")
    finally:
        session.close()


if __name__ == '__main__':
    main()
