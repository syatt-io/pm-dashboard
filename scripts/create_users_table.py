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
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set")
        sys.exit(1)

    # PostgreSQL requires postgresql:// instead of postgres://
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    print(f"Connecting to database...")
    engine = create_engine(database_url)

    print("Creating tables...")

    # Try SQLAlchemy first
    try:
        Base.metadata.create_all(engine)
        print("Tables created successfully with SQLAlchemy!")
    except Exception as e:
        print(f"SQLAlchemy failed: {e}")
        print("Trying raw SQL...")

        # Fallback to raw SQL
        try:
            with engine.connect() as conn:
                trans = conn.begin()
                try:
                    conn.execute(
                        text(
                            """
                        CREATE TABLE IF NOT EXISTS users (
                            id SERIAL PRIMARY KEY,
                            email VARCHAR(255) UNIQUE NOT NULL,
                            name VARCHAR(255),
                            google_id VARCHAR(255) UNIQUE,
                            role VARCHAR(50) DEFAULT 'member',
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            last_login TIMESTAMP,
                            is_active BOOLEAN DEFAULT TRUE,
                            fireflies_api_key_encrypted TEXT
                        )
                    """
                        )
                    )
                    trans.commit()
                    print("Users table created successfully with raw SQL!")
                except Exception as e:
                    trans.rollback()
                    print(f"Failed to create users table: {e}")
                    raise
        except Exception as e:
            print(f"Error creating tables with raw SQL: {e}")
            sys.exit(1)


if __name__ == "__main__":
    create_tables()
