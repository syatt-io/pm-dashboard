"""
Import users from CSV file into the database.
Creates User records with all team tracking fields.
"""

import os
import sys
import csv
import logging
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.user import User, UserRole
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


class UserCSVImporter:
    """Import users from CSV file."""

    def __init__(self):
        self.database_url = os.getenv("DATABASE_URL")
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable is required")

        self.engine = create_engine(self.database_url)
        self.Session = sessionmaker(bind=self.engine)

    def validate_csv_row(self, row, row_num):
        """Validate required fields in CSV row."""
        errors = []

        if not row.get('email'):
            errors.append(f"Row {row_num}: Missing email")

        if not row.get('name'):
            errors.append(f"Row {row_num}: Missing name")

        if not row.get('google_id'):
            errors.append(f"Row {row_num}: Missing google_id")
        elif row['google_id'].startswith('GOOGLE_ID_'):
            errors.append(f"Row {row_num}: google_id is still a placeholder - needs real Google ID")

        if not row.get('jira_account_id'):
            errors.append(f"Row {row_num}: Missing jira_account_id")

        return errors

    def import_from_csv(self, csv_path):
        """Import users from CSV file."""
        csv_path = Path(csv_path)

        if not csv_path.exists():
            logger.error(f"CSV file not found: {csv_path}")
            return

        logger.info("=" * 60)
        logger.info("USER CSV IMPORTER")
        logger.info("=" * 60)
        logger.info(f"Reading: {csv_path}\n")

        session = self.Session()
        imported = 0
        skipped = 0
        errors = []

        try:
            with open(csv_path, 'r') as f:
                reader = csv.DictReader(f)

                for row_num, row in enumerate(reader, start=2):  # Start at 2 (row 1 is header)
                    # Validate row
                    validation_errors = self.validate_csv_row(row, row_num)
                    if validation_errors:
                        errors.extend(validation_errors)
                        skipped += 1
                        continue

                    # Check if user already exists
                    existing = session.query(User).filter(
                        (User.email == row['email']) | (User.google_id == row['google_id'])
                    ).first()

                    if existing:
                        logger.warning(f"⚠️  Row {row_num}: User {row['email']} already exists - SKIPPING")
                        skipped += 1
                        continue

                    # Create user
                    try:
                        user = User(
                            email=row['email'],
                            name=row['name'],
                            google_id=row['google_id'],
                            jira_account_id=row['jira_account_id'] or None,
                            slack_user_id=row['slack_user_id'] or None,
                            team=row['team'] or None,
                            project_team=row['project_team'] or None,
                            weekly_hours_minimum=float(row.get('weekly_hours_minimum', 32.0)),
                            role=UserRole[row.get('role', 'MEMBER').upper()],
                            is_active=row.get('is_active', 'True').lower() == 'true'
                        )

                        session.add(user)
                        session.flush()  # Get the ID

                        logger.info(f"✅ Row {row_num}: Created {row['email']} (ID: {user.id})")
                        imported += 1

                    except Exception as e:
                        logger.error(f"❌ Row {row_num}: Error creating {row['email']}: {e}")
                        errors.append(f"Row {row_num}: {str(e)}")
                        skipped += 1

            # Commit all changes
            if imported > 0:
                session.commit()
                logger.info(f"\n✅ Successfully committed {imported} users to database")
            else:
                logger.warning("\n⚠️  No users were imported")

        except Exception as e:
            session.rollback()
            logger.error(f"\n❌ Import failed: {e}")
            raise

        finally:
            session.close()

        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("IMPORT SUMMARY")
        logger.info("=" * 60)
        logger.info(f"✅ Imported: {imported}")
        logger.info(f"⚠️  Skipped:  {skipped}")
        logger.info(f"❌ Errors:   {len(errors)}")

        if errors:
            logger.info("\nERROR DETAILS:")
            for error in errors:
                logger.info(f"  • {error}")

        logger.info("=" * 60 + "\n")

        return imported, skipped, errors


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Import users from CSV file")
    parser.add_argument(
        "csv_file",
        nargs='?',
        default="scripts/tempo_users.csv",
        help="Path to CSV file (default: scripts/tempo_users.csv)"
    )

    args = parser.parse_args()

    importer = UserCSVImporter()
    importer.import_from_csv(args.csv_file)
