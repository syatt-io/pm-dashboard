#!/usr/bin/env python3
"""
Migration script to ensure user_watched_projects table exists.
This should be run on app startup or as a one-time migration.
"""
import os
import sys
from sqlalchemy import text

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.database import get_engine

def ensure_user_watched_projects_table():
    """Create user_watched_projects table if it doesn't exist."""
    engine = get_engine()

    create_table_sql = text("""
    CREATE TABLE IF NOT EXISTS user_watched_projects (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        project_key VARCHAR(50) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, project_key)
    );
    """)

    try:
        with engine.connect() as conn:
            conn.execute(create_table_sql)
            conn.commit()
            print("✓ user_watched_projects table ensured")
    except Exception as e:
        print(f"✗ Error creating user_watched_projects table: {e}")
        raise

if __name__ == "__main__":
    ensure_user_watched_projects_table()
