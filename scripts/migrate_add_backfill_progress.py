#!/usr/bin/env python3
"""Database migration to add backfill_progress table for checkpointing."""

import sys
from sqlalchemy import create_engine, inspect
from src.utils.database import get_engine
from src.models import Base, BackfillProgress


def main():
    """Run database migration."""
    print("=" * 80)
    print("Database Migration: Add backfill_progress table")
    print("=" * 80)
    print()

    try:
        engine = get_engine()
        inspector = inspect(engine)

        # Check if table already exists
        if "backfill_progress" in inspector.get_table_names():
            print("⚠️  Table 'backfill_progress' already exists - skipping creation")
            print()
            sys.exit(0)

        # Create table
        print("📋 Creating table 'backfill_progress'...")
        BackfillProgress.__table__.create(engine)
        print("✅ Table created successfully!")
        print()

        # Verify
        if "backfill_progress" in inspect(engine).get_table_names():
            print("✅ Migration completed successfully!")
            sys.exit(0)
        else:
            print("❌ Migration failed - table not found after creation")
            sys.exit(1)

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
