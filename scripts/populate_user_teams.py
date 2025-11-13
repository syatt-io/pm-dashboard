#!/usr/bin/env python3
"""
Populate user_teams table from CSV file with user/team mappings.

This script:
1. Reads CSV file with account_id, display_name, team columns
2. Validates team names against UserTeam.valid_teams()
3. Inserts/updates records in user_teams table

Usage:
    python scripts/populate_user_teams.py users_to_map.csv [--dry-run]
"""

import os
import sys
import csv
import argparse
from pathlib import Path
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.user_team import UserTeam
from src.utils.database import get_session
from sqlalchemy import insert
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def read_csv_file(csv_file: str) -> list:
    """
    Read CSV file and extract user/team mappings.

    Args:
        csv_file: Path to CSV file

    Returns:
        List of dicts: [{'account_id': ..., 'display_name': ..., 'team': ...}, ...]
    """
    logger.info(f"Reading CSV file: {csv_file}")

    if not os.path.exists(csv_file):
        raise FileNotFoundError(f"CSV file not found: {csv_file}")

    mappings = []
    valid_teams = UserTeam.valid_teams()

    with open(csv_file, 'r', encoding='utf-8') as f:
        # Skip comment lines starting with #
        lines = [line for line in f if not line.strip().startswith('#')]

        # Reset to start and use csv.DictReader
        reader = csv.DictReader(lines)

        for row_num, row in enumerate(reader, start=1):
            account_id = row.get('account_id', '').strip()
            display_name = row.get('display_name', '').strip()
            team = row.get('team', '').strip()

            # Skip rows with empty account_id
            if not account_id:
                continue

            # Default to "Unassigned" if team is empty
            if not team:
                team = "Unassigned"

            # Validate team name
            if team not in valid_teams:
                logger.warning(
                    f"  Row {row_num}: Invalid team '{team}' for user {display_name}. "
                    f"Valid teams: {', '.join(valid_teams)}. Skipping..."
                )
                continue

            mappings.append({
                'account_id': account_id,
                'display_name': display_name,
                'team': team,
            })

    logger.info(f"  Found {len(mappings)} valid user/team mappings")
    return mappings


def populate_database(mappings: list, dry_run: bool = False):
    """
    Insert/update user_teams table with mappings from CSV.

    Args:
        mappings: List of user/team mapping dicts
        dry_run: If True, only show what would be done without modifying database
    """
    if dry_run:
        logger.info("\n🔍 DRY RUN MODE - No changes will be made to database\n")
    else:
        logger.info("\n💾 Writing to database...\n")

    session = get_session()

    try:
        # Show summary by team
        team_counts = {}
        for mapping in mappings:
            team = mapping['team']
            team_counts[team] = team_counts.get(team, 0) + 1

        logger.info("Summary by team:")
        for team, count in sorted(team_counts.items()):
            logger.info(f"  {team}: {count} users")

        if dry_run:
            logger.info("\nDry run complete. Run without --dry-run to apply changes.")
            return

        # Insert/update records
        inserted = 0
        updated = 0

        for mapping in mappings:
            # Check if record exists
            existing = (
                session.query(UserTeam)
                .filter_by(account_id=mapping['account_id'])
                .first()
            )

            if existing:
                # Update existing record
                existing.display_name = mapping['display_name']
                existing.team = mapping['team']
                existing.updated_at = datetime.now(timezone.utc)
                updated += 1
            else:
                # Insert new record
                new_user_team = UserTeam(
                    account_id=mapping['account_id'],
                    display_name=mapping['display_name'],
                    team=mapping['team'],
                    updated_at=datetime.now(timezone.utc),
                )
                session.add(new_user_team)
                inserted += 1

            # Commit in batches of 50
            if (inserted + updated) % 50 == 0:
                session.commit()
                logger.info(f"  Committed {inserted + updated} records...")

        # Final commit
        session.commit()

        logger.info(f"\n✅ Database updated successfully")
        logger.info(f"  Inserted: {inserted} new users")
        logger.info(f"  Updated: {updated} existing users")
        logger.info(f"  Total: {inserted + updated} users")

    except Exception as e:
        logger.error(f"\n❌ Error during database update: {e}")
        session.rollback()
        raise
    finally:
        session.close()


def verify_results(session):
    """Show summary of user_teams table after update."""
    logger.info("\nVerifying results...")

    # Count by team
    from sqlalchemy import func

    team_counts = (
        session.query(UserTeam.team, func.count(UserTeam.account_id))
        .group_by(UserTeam.team)
        .order_by(UserTeam.team)
        .all()
    )

    logger.info("\nuser_teams table summary:")
    total = 0
    for team, count in team_counts:
        logger.info(f"  {team}: {count} users")
        total += count

    logger.info(f"\n  Total: {total} users")


def main():
    parser = argparse.ArgumentParser(
        description="Populate user_teams table from CSV file with user/team mappings"
    )
    parser.add_argument(
        'csv_file',
        help='CSV file with account_id, display_name, team columns'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without modifying database'
    )
    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("POPULATING USER_TEAMS TABLE FROM CSV")
    logger.info("=" * 80)

    try:
        # Read CSV file
        mappings = read_csv_file(args.csv_file)

        if not mappings:
            logger.error("No valid mappings found in CSV file")
            return 1

        # Populate database
        populate_database(mappings, dry_run=args.dry_run)

        # Verify results (only if not dry run)
        if not args.dry_run:
            session = get_session()
            try:
                verify_results(session)
            finally:
                session.close()

            logger.info("\n" + "=" * 80)
            logger.info("POPULATION COMPLETE")
            logger.info("=" * 80)
            logger.info("\nNext steps:")
            logger.info("  1. Re-run epic hours backfill to use new team mappings:")
            logger.info("     python scripts/backfill_epic_hours.py")
            logger.info("  2. Rebuild forecasting baselines:")
            logger.info("     python scripts/build_forecasting_baselines.py")
            logger.info("  3. Test forecasting with new team data")

        return 0

    except Exception as e:
        logger.error(f"\n❌ Error during population: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
