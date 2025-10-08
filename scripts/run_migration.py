"""Run database migration for project_keywords table."""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.database import get_engine
from sqlalchemy import text


def run_migration():
    """Run the project_keywords migration."""
    engine = get_engine()

    # Detect database type
    if 'postgresql' in str(engine.url):
        migration_file = project_root / 'migrations' / 'create_project_keywords_table_postgres.sql'
        db_type = 'PostgreSQL'
    else:
        migration_file = project_root / 'migrations' / 'create_project_keywords_table.sql'
        db_type = 'SQLite'

    print(f"Running migration for {db_type}...")
    print(f"Migration file: {migration_file}")

    # Read migration SQL
    with open(migration_file, 'r') as f:
        sql = f.read()

    # Execute migration
    with engine.connect() as conn:
        # Split by semicolons and execute each statement
        for statement in sql.split(';'):
            statement = statement.strip()
            if statement:
                try:
                    conn.execute(text(statement))
                except Exception as e:
                    # Ignore "already exists" errors
                    if 'already exists' in str(e).lower() or 'duplicate' in str(e).lower():
                        print(f"⏭️  Skipping (already exists): {statement[:50]}...")
                    else:
                        print(f"❌ Error: {e}")
                        raise

        conn.commit()

    print("✅ Migration completed successfully!")


if __name__ == '__main__':
    run_migration()
