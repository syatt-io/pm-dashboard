"""Data migration script to create notification preferences for existing users.

This script ensures all users in the system have a notification preferences record.
All preferences default to FALSE (opt-in system) as per requirements.

Usage:
    python scripts/migrate_notification_preferences.py [--dry-run]

Options:
    --dry-run: Show what would be done without making changes
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.orm import Session
from src.utils.database import get_session, close_session
from src.models.user import User
from src.models.notification_preferences import UserNotificationPreferences
from src.services.notification_preference_checker import NotificationPreferenceChecker


def migrate_notification_preferences(dry_run: bool = False):
    """Create notification preferences for users that don't have them.

    Args:
        dry_run: If True, only show what would be done without making changes
    """
    db = get_session()

    try:
        # Get all users
        users = db.query(User).all()
        total_users = len(users)

        print(f"Found {total_users} users in database")

        # Check which users already have preferences
        existing_prefs = db.query(UserNotificationPreferences).all()
        existing_user_ids = {pref.user_id for pref in existing_prefs}

        print(
            f"Found {len(existing_user_ids)} users with existing notification preferences"
        )

        # Find users without preferences
        users_without_prefs = [
            user for user in users if user.id not in existing_user_ids
        ]

        if not users_without_prefs:
            print("\nAll users already have notification preferences!")
            print("No migration needed.")
            return

        print(
            f"\nFound {len(users_without_prefs)} users without notification preferences:"
        )
        for user in users_without_prefs:
            print(f"  - User ID {user.id}: {user.email} ({user.name})")

        if dry_run:
            print("\n[DRY RUN] Would create notification preferences for these users")
            print("[DRY RUN] All preferences would default to FALSE (opt-in system)")
            return

        # Create preferences for users that don't have them
        checker = NotificationPreferenceChecker(db)
        created_count = 0

        print("\nCreating notification preferences...")
        for user in users_without_prefs:
            print(
                f"  Creating preferences for user {user.id} ({user.email})...", end=" "
            )
            try:
                checker.create_default_preferences(user)
                created_count += 1
                print("✓")
            except Exception as e:
                print(f"✗ Error: {e}")

        print(f"\nMigration complete!")
        print(f"  Total users: {total_users}")
        print(f"  Already had preferences: {len(existing_user_ids)}")
        print(f"  Created new preferences: {created_count}")
        print(f"\nAll new preferences set to FALSE (opt-in system)")

    except Exception as e:
        print(f"\nError during migration: {e}")
        db.rollback()
        raise
    finally:
        close_session(db)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Migrate notification preferences for existing users"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )

    args = parser.parse_args()

    print("=" * 80)
    print("Notification Preferences Migration Script")
    print("=" * 80)

    if args.dry_run:
        print("\n⚠️  DRY RUN MODE - No changes will be made\n")

    migrate_notification_preferences(dry_run=args.dry_run)

    print("\n" + "=" * 80)
