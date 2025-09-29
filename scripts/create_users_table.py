#!/usr/bin/env python3
"""Create users table in production database."""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from src.models.user import Base

def create_tables():
    """Create all tables in the database."""
    # Get database URL from environment
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set")
        sys.exit(1)

    # PostgreSQL requires postgresql:// instead of postgres://
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)

    print(f"Connecting to database...")
    engine = create_engine(database_url)

    print("Creating tables...")
    try:
        Base.metadata.create_all(engine)
        print("Tables created successfully!")
    except Exception as e:
        print(f"Error creating tables: {e}")
        sys.exit(1)

if __name__ == "__main__":
    create_tables()