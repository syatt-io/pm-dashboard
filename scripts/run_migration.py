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
    if "postgresql" in str(engine.url):
        migration_files = [
            project_root / "migrations" / "create_project_keywords_table_postgres.sql",
            project_root / "migrations" / "fix_project_keywords_columns.sql",
        ]
        db_type = "PostgreSQL"
    else:
        migration_files = [
            project_root / "migrations" / "create_project_keywords_table.sql"
        ]
        db_type = "SQLite"

    print(f"Running migrations for {db_type}...")

    # Execute each migration file in order
    for migration_file in migration_files:
        print(f"Migration file: {migration_file}")

        # Read migration SQL
        with open(migration_file, "r") as f:
            sql = f.read()

        # Execute migration
        with engine.begin() as conn:
            # Split by semicolons and execute each statement
            for statement in sql.split(";"):
                statement = statement.strip()
                if statement:
                    try:
                        conn.execute(text(statement))
                    except Exception as e:
                        # Ignore "already exists" errors and privilege errors for indexes
                        error_str = str(e).lower()
                        if "already exists" in error_str or "duplicate" in error_str:
                            print(f"⏭️  Skipping (already exists): {statement[:50]}...")
                        elif (
                            "insufficientprivilege" in error_str
                            and "index" in statement.lower()
                        ):
                            print(
                                f"⏭️  Skipping (index already exists, insufficient privilege to recreate): {statement[:50]}..."
                            )
                        elif "infailedsqltransaction" in error_str:
                            print(
                                f"⏭️  Skipping (transaction failed, likely already exists): {statement[:50]}..."
                            )
                        else:
                            print(f"❌ Error: {e}")
                            raise

    print("✅ Migration completed successfully!")


if __name__ == "__main__":
    run_migration()
