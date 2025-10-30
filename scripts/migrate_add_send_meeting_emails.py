#!/usr/bin/env python3
"""Migration script to add send_meeting_emails column to projects table."""

import sys
import os
from sqlalchemy import create_engine, text, inspect

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    """Run database migration."""
    print("=" * 80)
    print("Database Migration: Add send_meeting_emails to projects table")
    print("=" * 80)
    print()

    try:
        # Get database URL from environment
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            print("❌ DATABASE_URL environment variable not set")
            sys.exit(1)

        engine = create_engine(database_url)
        inspector = inspect(engine)

        # Check if column already exists
        columns = [col['name'] for col in inspector.get_columns('projects')]

        if 'send_meeting_emails' in columns:
            print("⚠️  Column 'send_meeting_emails' already exists - skipping")
            print()
            sys.exit(0)

        # Add column
        print("📋 Adding column 'send_meeting_emails' to projects table...")

        with engine.connect() as conn:
            # PostgreSQL-compatible ADD COLUMN with IF NOT EXISTS
            conn.execute(text("""
                ALTER TABLE projects
                ADD COLUMN IF NOT EXISTS send_meeting_emails BOOLEAN NOT NULL DEFAULT FALSE
            """))
            conn.commit()

        print("✅ Column added successfully!")
        print()

        # Verify
        inspector = inspect(engine)
        columns = [col['name'] for col in inspector.get_columns('projects')]

        if 'send_meeting_emails' in columns:
            print("✅ Migration completed successfully!")
            print()
            print("Column details:")
            for col in inspector.get_columns('projects'):
                if col['name'] == 'send_meeting_emails':
                    print(f"  Name: {col['name']}")
                    print(f"  Type: {col['type']}")
                    print(f"  Nullable: {col['nullable']}")
                    print(f"  Default: {col.get('default', 'None')}")
            sys.exit(0)
        else:
            print("❌ Migration failed - column not found after creation")
            sys.exit(1)

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
