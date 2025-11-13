#!/usr/bin/env python3
"""
Export all Jira users who have logged hours in Tempo to CSV for team mapping.

This script:
1. Fetches all worklogs from Tempo for the last 2 years
2. Extracts unique users (account_id, display_name)
3. Exports to CSV with empty 'team' column for manual assignment

Usage:
    python scripts/get_jira_users.py [--output users_to_map.csv]
"""

import os
import sys
import csv
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from collections import OrderedDict

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.integrations.tempo import TempoAPIClient
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_unique_users_from_worklogs(tempo_client: TempoAPIClient) -> dict:
    """
    Fetch worklogs and extract unique users.

    Returns:
        OrderedDict: {account_id: display_name} sorted by display_name
    """
    logger.info("Fetching worklogs from Tempo API...")

    # Get worklogs from last 2 years
    start_date = (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")

    logger.info(f"  Date range: {start_date} to {end_date}")
    worklogs = tempo_client.get_worklogs(from_date=start_date, to_date=end_date)

    if not worklogs:
        logger.warning("  No worklogs found")
        return OrderedDict()

    logger.info(f"  Found {len(worklogs):,} worklogs")

    # Extract unique users
    users = {}  # {account_id: display_name}

    for worklog in worklogs:
        author = worklog.get("author", {})
        account_id = author.get("accountId")

        if account_id and account_id not in users:
            # Get display name from Jira API
            display_name = tempo_client.get_user_name(account_id)
            if display_name:
                users[account_id] = display_name
                logger.debug(f"    Found user: {display_name} ({account_id})")

    logger.info(f"\n  Extracted {len(users)} unique users")

    # Sort by display name
    sorted_users = OrderedDict(sorted(users.items(), key=lambda x: x[1].lower()))

    return sorted_users


def export_to_csv(users: dict, output_file: str):
    """
    Export users to CSV file with empty team column.

    Args:
        users: Dictionary of {account_id: display_name}
        output_file: Path to output CSV file
    """
    logger.info(f"\nExporting to {output_file}...")

    # Import valid teams to show in CSV header
    from src.models.user_team import UserTeam

    valid_teams = UserTeam.valid_teams()

    with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)

        # Write header with instructions
        writer.writerow(["# USER/TEAM MAPPING FILE"])
        writer.writerow(['# Instructions: Fill in the "team" column for each user'])
        writer.writerow([f'# Valid teams: {", ".join(valid_teams)}'])
        writer.writerow(
            ['# Leave team empty or use "Unassigned" for users without a team']
        )
        writer.writerow([])

        # Column headers
        writer.writerow(["account_id", "display_name", "team"])

        # Write user rows
        for account_id, display_name in users.items():
            writer.writerow([account_id, display_name, ""])  # Empty team column

    logger.info(f"  ✅ Exported {len(users)} users to {output_file}")
    logger.info(f"\nNext steps:")
    logger.info(f"  1. Open {output_file} in a spreadsheet editor")
    logger.info(f"  2. Fill in the 'team' column for each user")
    logger.info(f"  3. Valid teams: {', '.join(valid_teams)}")
    logger.info(f"  4. Run: python scripts/populate_user_teams.py {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Export Jira users who logged hours to CSV for team mapping"
    )
    parser.add_argument(
        "--output",
        default="users_to_map.csv",
        help="Output CSV file path (default: users_to_map.csv)",
    )
    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("EXTRACTING JIRA USERS FROM TEMPO WORKLOGS")
    logger.info("=" * 80)

    try:
        # Initialize Tempo client
        tempo_client = TempoAPIClient()

        # Get unique users from worklogs
        users = get_unique_users_from_worklogs(tempo_client)

        if not users:
            logger.error("No users found in worklogs")
            return 1

        # Export to CSV
        export_to_csv(users, args.output)

        logger.info("\n" + "=" * 80)
        logger.info("EXPORT COMPLETE")
        logger.info("=" * 80)

        return 0

    except Exception as e:
        logger.error(f"\n❌ Error during export: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
