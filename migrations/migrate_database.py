#!/usr/bin/env python3
"""Database migration script to add new columns to processed_meetings table."""

import sqlite3
import logging
from pathlib import Path
from config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate_database():
    """Add new columns to processed_meetings table."""
    # Extract database path from URL
    db_url = settings.agent.database_url
    if db_url.startswith('sqlite:///'):
        db_path = db_url[10:]  # Remove 'sqlite:///' prefix
    else:
        logger.error(f"Unsupported database URL: {db_url}")
        return False

    logger.info(f"Migrating database: {db_path}")

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check current table structure
        cursor.execute("PRAGMA table_info(processed_meetings)")
        columns = [row[1] for row in cursor.fetchall()]
        logger.info(f"Current columns: {columns}")

        # Add missing columns
        new_columns = [
            ('analyzed_at', 'DATETIME'),
            ('summary', 'TEXT'),
            ('key_decisions', 'TEXT'),  # JSON stored as TEXT
            ('blockers', 'TEXT'),       # JSON stored as TEXT
            ('todos_created', 'TEXT')   # JSON stored as TEXT
        ]

        for column_name, column_type in new_columns:
            if column_name not in columns:
                try:
                    sql = f"ALTER TABLE processed_meetings ADD COLUMN {column_name} {column_type}"
                    logger.info(f"Adding column: {sql}")
                    cursor.execute(sql)
                    logger.info(f"✅ Added column: {column_name}")
                except sqlite3.OperationalError as e:
                    logger.warning(f"⚠️  Column {column_name} might already exist: {e}")
            else:
                logger.info(f"✅ Column {column_name} already exists")

        conn.commit()

        # Verify the migration
        cursor.execute("PRAGMA table_info(processed_meetings)")
        updated_columns = [row[1] for row in cursor.fetchall()]
        logger.info(f"Updated columns: {updated_columns}")

        conn.close()
        logger.info("🎉 Database migration completed successfully!")
        return True

    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        return False


if __name__ == "__main__":
    success = migrate_database()
    exit(0 if success else 1)