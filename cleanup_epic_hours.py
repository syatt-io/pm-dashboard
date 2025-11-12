"""
Clean up invalid epic_hours data (NO_EPIC and date-string epics).
Run this on production via: doctl apps exec <app-id> web -- python cleanup_epic_hours.py
"""

import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

# Get database URL from environment
database_url = os.getenv("DATABASE_URL")
if not database_url:
    print("ERROR: DATABASE_URL not set")
    exit(1)

# Create engine
engine = create_engine(database_url)

# Projects to clean up
projects_to_clean = ["RNWL", "BEVS"]

with engine.connect() as conn:
    for project_key in projects_to_clean:
        print(f"\n{'='*60}")
        print(f"Cleaning up {project_key}")
        print(f"{'='*60}")

        # Delete NO_EPIC rows
        result = conn.execute(
            text(
                "DELETE FROM epic_hours WHERE project_key = :project AND epic_key = 'NO_EPIC'"
            ),
            {"project": project_key},
        )
        print(f"Deleted {result.rowcount} NO_EPIC rows")

        # Delete rows where epic_key looks like a date (YYYY-MM-DD pattern)
        result = conn.execute(
            text(
                """
                DELETE FROM epic_hours
                WHERE project_key = :project
                AND epic_key ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
            """
            ),
            {"project": project_key},
        )
        print(f"Deleted {result.rowcount} date-string epic rows")

        conn.commit()

print("\n✅ Cleanup complete! Now re-run the sync from the UI.")
