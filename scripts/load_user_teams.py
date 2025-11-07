#!/usr/bin/env python3
"""Load user team assignments from CSV file into database.

This script reads a CSV file with user team assignments and loads them
into the user_teams table. It performs validation and upserts records.

Usage:
    python scripts/load_user_teams.py user_teams_template.csv
"""

import os
import sys
import csv
from typing import List, Dict

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models import UserTeam

# Valid team values
VALID_TEAMS = ['PMs', 'Design', 'UX', 'FE Devs', 'BE Devs', 'Data', 'Unassigned']


def validate_csv_file(file_path: str) -> List[Dict[str, str]]:
    """
    Read and validate CSV file.

    Args:
        file_path: Path to CSV file

    Returns:
        List of valid user team records

    Raises:
        SystemExit: If validation fails
    """
    if not os.path.exists(file_path):
        print(f"❌ Error: File not found: {file_path}")
        sys.exit(1)

    records = []
    errors = []

    try:
        with open(file_path, 'r') as csvfile:
            reader = csv.DictReader(csvfile)

            # Validate header
            required_fields = ['account_id', 'display_name', 'team']
            if not all(field in reader.fieldnames for field in required_fields):
                print(f"❌ Error: CSV must have columns: {', '.join(required_fields)}")
                print(f"   Found columns: {', '.join(reader.fieldnames)}")
                sys.exit(1)

            # Validate records
            for line_num, row in enumerate(reader, start=2):  # Start at 2 (after header)
                account_id = row.get('account_id', '').strip()
                display_name = row.get('display_name', '').strip()
                team = row.get('team', '').strip()

                # Validate account_id
                if not account_id:
                    errors.append(f"Line {line_num}: Missing account_id")
                    continue

                # Validate team
                if not team:
                    errors.append(f"Line {line_num}: Missing team for {display_name or account_id}")
                    continue

                if team not in VALID_TEAMS:
                    errors.append(f"Line {line_num}: Invalid team '{team}' for {display_name or account_id}")
                    errors.append(f"             Valid teams: {', '.join(VALID_TEAMS)}")
                    continue

                records.append({
                    'account_id': account_id,
                    'display_name': display_name or None,
                    'team': team
                })

        if errors:
            print("❌ Validation errors found:")
            for error in errors:
                print(f"   {error}")
            sys.exit(1)

        return records

    except Exception as e:
        print(f"❌ Error reading CSV file: {e}")
        sys.exit(1)


def load_user_teams(records: List[Dict[str, str]]):
    """
    Load user team records into database.

    Args:
        records: List of validated user team records
    """
    # Get database URL
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ Error: DATABASE_URL environment variable not set")
        sys.exit(1)

    # Create database session
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        created = 0
        updated = 0

        for record in records:
            # Check if user already exists
            existing = session.query(UserTeam).filter_by(
                account_id=record['account_id']
            ).first()

            if existing:
                # Update existing record
                existing.display_name = record['display_name']
                existing.team = record['team']
                updated += 1
            else:
                # Create new record
                user_team = UserTeam(
                    account_id=record['account_id'],
                    display_name=record['display_name'],
                    team=record['team']
                )
                session.add(user_team)
                created += 1

        # Commit changes
        session.commit()

        print(f"✅ Successfully loaded {len(records)} user team assignments:")
        print(f"   - Created: {created}")
        print(f"   - Updated: {updated}")

        # Show summary by team
        print(f"\n📊 Team distribution:")
        team_counts = {}
        for record in records:
            team = record['team']
            team_counts[team] = team_counts.get(team, 0) + 1

        for team in sorted(team_counts.keys()):
            count = team_counts[team]
            print(f"   - {team}: {count} user(s)")

    except Exception as e:
        session.rollback()
        print(f"❌ Error loading data: {e}")
        sys.exit(1)
    finally:
        session.close()


def main():
    """Main entry point."""
    if len(sys.argv) != 2:
        print("Usage: python scripts/load_user_teams.py <csv_file>")
        print()
        print("Example:")
        print("  python scripts/load_user_teams.py user_teams_template.csv")
        sys.exit(1)

    csv_file = sys.argv[1]

    print("=" * 80)
    print("USER TEAM LOADER")
    print("=" * 80)
    print()

    # Validate CSV file
    print(f"📂 Reading CSV file: {csv_file}")
    records = validate_csv_file(csv_file)
    print(f"✅ Validated {len(records)} records")
    print()

    # Load into database
    print("💾 Loading into database...")
    load_user_teams(records)

    print()
    print("=" * 80)
    print("✅ USER TEAMS LOADED SUCCESSFULLY")
    print("=" * 80)


if __name__ == '__main__':
    main()
