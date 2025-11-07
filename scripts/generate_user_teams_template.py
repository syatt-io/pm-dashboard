#!/usr/bin/env python3
"""Generate a CSV template for user team assignments.

This script fetches all users who have logged time in Tempo over the last 6 months
and creates a CSV file with account_id, display_name, and team columns.
The team column is pre-filled with "Unassigned" and should be manually edited.

Usage:
    python scripts/generate_user_teams_template.py
"""

import os
import sys
import csv
from datetime import datetime, timedelta
from collections import OrderedDict

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from src.integrations.tempo import TempoAPIClient

# Valid team values
VALID_TEAMS = ['PMs', 'Design', 'UX', 'FE Devs', 'BE Devs', 'Data', 'Unassigned']

def fetch_all_users(tempo_client):
    """Fetch all unique users from Tempo worklogs (last 6 months)."""
    print("📊 Fetching users from Tempo worklogs...")

    # Calculate date range (last 6 months)
    to_date = datetime.now().date()
    from_date = to_date - timedelta(days=180)

    print(f"   Date range: {from_date} to {to_date}")

    # Fetch worklogs using TempoAPIClient
    worklogs = tempo_client.get_worklogs(
        from_date=str(from_date),
        to_date=str(to_date)
    )

    print(f"   Retrieved {len(worklogs)} worklogs")

    # Extract unique account IDs
    account_ids = set()
    for worklog in worklogs:
        author = worklog.get("author", {})
        account_id = author.get("accountId")
        if account_id:
            account_ids.add(account_id)

    print(f"   Found {len(account_ids)} unique account IDs")
    print(f"   Resolving account IDs to display names via Jira API...")

    # Resolve account IDs to display names using Jira API
    users = {}  # account_id -> display_name
    for i, account_id in enumerate(sorted(account_ids), 1):
        display_name = tempo_client.get_user_name(account_id)
        if display_name:
            users[account_id] = display_name
        else:
            users[account_id] = f"Unknown ({account_id})"

        if i % 5 == 0:
            print(f"   Resolved {i}/{len(account_ids)} users...")

    print(f"✅ Found {len(users)} users with display names")
    return users


def generate_template_csv(users, output_file='user_teams_template.csv'):
    """Generate CSV template with users and default team assignment."""
    print(f"\n📝 Generating CSV template: {output_file}")

    # Sort users by display name for easier manual editing
    sorted_users = OrderedDict(sorted(users.items(), key=lambda x: x[1].lower()))

    with open(output_file, 'w', newline='') as csvfile:
        fieldnames = ['account_id', 'display_name', 'team']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()

        for account_id, display_name in sorted_users.items():
            writer.writerow({
                'account_id': account_id,
                'display_name': display_name,
                'team': 'Unassigned'
            })

    print(f"✅ CSV template generated with {len(users)} users")
    return output_file


def main():
    """Main entry point."""
    print("=" * 80)
    print("USER TEAM TEMPLATE GENERATOR")
    print("=" * 80)
    print()

    # Initialize Tempo API client
    try:
        tempo_client = TempoAPIClient()
    except Exception as e:
        print(f"❌ Error initializing Tempo client: {e}")
        sys.exit(1)

    # Fetch all users from Tempo
    users = fetch_all_users(tempo_client)

    # Generate CSV template
    output_file = generate_template_csv(users)

    print()
    print("=" * 80)
    print("📋 NEXT STEPS")
    print("=" * 80)
    print()
    print(f"1. Open the file: {output_file}")
    print(f"2. Edit the 'team' column for each user")
    print(f"3. Valid team values: {', '.join(VALID_TEAMS)}")
    print(f"4. Save the file")
    print(f"5. Run: python scripts/load_user_teams.py {output_file}")
    print()
    print("=" * 80)


if __name__ == '__main__':
    main()
