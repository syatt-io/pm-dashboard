#!/usr/bin/env python3
"""
Database migration: Add fireflies_api_key_encrypted column to users table.

This migration adds support for user-specific Fireflies API keys by adding
an encrypted storage column to the users table.

Usage:
    python migrations/add_fireflies_api_key_column.py

Requirements:
    - The application database must already exist
    - The users table must already exist
"""

import os
import sys
import logging
from sqlalchemy import create_engine, text, MetaData, Table, Column, Text
from sqlalchemy.exc import SQLAlchemyError

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_column_exists(engine, table_name: str, column_name: str) -> bool:
    """Check if a column already exists in a table."""
    try:
        with engine.connect() as conn:
            # SQLite-specific query to check column existence
            result = conn.execute(text(f"PRAGMA table_info({table_name})"))
            columns = [row[1] for row in result.fetchall()]  # row[1] is column name
            return column_name in columns
    except Exception as e:
        logger.error(f"Error checking column existence: {e}")
        return False


def add_column_to_table(engine, table_name: str, column_name: str, column_type: str):
    """Add a column to an existing table."""
    try:
        with engine.connect() as conn:
            # Begin transaction
            trans = conn.begin()
            try:
                # Add the column
                alter_sql = (
                    f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
                )
                conn.execute(text(alter_sql))
                trans.commit()
                logger.info(f"Successfully added column {column_name} to {table_name}")
            except Exception as e:
                trans.rollback()
                raise e
    except Exception as e:
        logger.error(f"Error adding column {column_name} to {table_name}: {e}")
        raise


def main():
    """Run the migration."""
    logger.info("Starting migration: Add fireflies_api_key_encrypted column")

    try:
        # Get database settings
        engine = create_engine(settings.agent.database_url)

        # Check if the column already exists
        if check_column_exists(engine, "users", "fireflies_api_key_encrypted"):
            logger.info(
                "Column 'fireflies_api_key_encrypted' already exists in users table"
            )
            logger.info("Migration not needed - skipping")
            return

        # Add the column
        logger.info("Adding fireflies_api_key_encrypted column to users table...")
        add_column_to_table(engine, "users", "fireflies_api_key_encrypted", "TEXT")

        logger.info("Migration completed successfully!")
        logger.info("Users can now store encrypted Fireflies API keys")

    except SQLAlchemyError as e:
        logger.error(f"Database error during migration: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error during migration: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
