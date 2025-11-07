#!/usr/bin/env python3
"""
Load epic hours data into the database from CSV file.

Usage:
    python scripts/load_epic_hours.py /tmp/coop_hours_by_epic.csv
"""

import sys
import csv
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models import EpicHours
from src.utils.database import get_session
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_epic_hours_from_csv(csv_path: str):
    """Load epic hours from CSV file into database."""
    session = get_session()

    try:
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)

            loaded = 0
            updated = 0
            skipped = 0

            for row in reader:
                try:
                    project_key = row['Project']
                    epic_key = row['Epic']
                    team = row['Team']
                    epic_summary = row['Epic_Summary']
                    month_str = row['Month']  # e.g., "2025-01"
                    hours = float(row['Hours'])

                    # Parse month as first day of month
                    month_date = datetime.strptime(f"{month_str}-01", "%Y-%m-%d").date()

                    # Check if record exists (now includes team in unique constraint)
                    existing = session.query(EpicHours).filter(
                        EpicHours.project_key == project_key,
                        EpicHours.epic_key == epic_key,
                        EpicHours.month == month_date,
                        EpicHours.team == team
                    ).first()

                    if existing:
                        # Update existing record
                        existing.hours = hours
                        existing.epic_summary = epic_summary
                        existing.updated_at = datetime.utcnow()
                        updated += 1
                    else:
                        # Create new record
                        epic_hours = EpicHours(
                            project_key=project_key,
                            epic_key=epic_key,
                            epic_summary=epic_summary,
                            month=month_date,
                            team=team,
                            hours=hours
                        )
                        session.add(epic_hours)
                        loaded += 1

                except Exception as e:
                    logger.error(f"Error processing row {row}: {e}")
                    skipped += 1
                    continue

            # Commit all changes
            session.commit()

            logger.info(f"✅ Loaded {loaded} new records, updated {updated} records, skipped {skipped}")

    except Exception as e:
        logger.error(f"Error loading CSV: {e}")
        session.rollback()
        raise
    finally:
        session.close()


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/load_epic_hours.py <csv_file>")
        print("Example: python scripts/load_epic_hours.py /tmp/coop_hours_by_epic.csv")
        sys.exit(1)

    csv_path = sys.argv[1]

    if not Path(csv_path).exists():
        print(f"Error: File not found: {csv_path}")
        sys.exit(1)

    logger.info(f"Loading epic hours from: {csv_path}")
    load_epic_hours_from_csv(csv_path)
    logger.info("Done!")


if __name__ == "__main__":
    main()
