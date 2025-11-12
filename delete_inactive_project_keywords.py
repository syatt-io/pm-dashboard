#!/usr/bin/env python3
"""
Delete project keywords for INACTIVE projects.
This script removes keywords from the project_keywords table where the project is not active.
"""

import os
import sys
from sqlalchemy import create_engine, text

# Get database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("Error: DATABASE_URL environment variable not set", file=sys.stderr)
    sys.exit(1)


def main():
    """Delete keywords for inactive projects."""
    print("=" * 80)
    print("DELETE KEYWORDS FOR INACTIVE PROJECTS")
    print("=" * 80)

    engine = create_engine(DATABASE_URL)

    try:
        with engine.begin() as conn:
            # First, let's see what we're deleting
            result = conn.execute(
                text(
                    """
                SELECT pk.project_key, COUNT(*) as keyword_count
                FROM project_keywords pk
                LEFT JOIN projects p ON pk.project_key = p.key
                WHERE p.is_active IS NULL OR p.is_active = false
                GROUP BY pk.project_key
                ORDER BY pk.project_key
            """
                )
            )

            projects_to_clean = list(result)

            if not projects_to_clean:
                print("\n✅ No keywords found for inactive projects!")
                return

            print(
                f"\n📋 Found keywords for {len(projects_to_clean)} inactive projects:"
            )
            print("-" * 80)
            total_keywords = 0
            for project_key, keyword_count in projects_to_clean:
                print(f"  {project_key}: {keyword_count} keyword(s)")
                total_keywords += keyword_count

            print(f"\n🗑️  Total keywords to delete: {total_keywords}")
            print("-" * 80)

            # Confirm deletion
            response = input(
                "\n⚠️  Are you sure you want to delete these keywords? (yes/no): "
            )
            if response.lower() != "yes":
                print("\n❌ Deletion cancelled.")
                return

            # Delete keywords for inactive projects
            delete_result = conn.execute(
                text(
                    """
                DELETE FROM project_keywords
                WHERE project_key IN (
                    SELECT pk.project_key
                    FROM project_keywords pk
                    LEFT JOIN projects p ON pk.project_key = p.key
                    WHERE p.is_active IS NULL OR p.is_active = false
                )
            """
                )
            )

            deleted_count = delete_result.rowcount
            print(
                f"\n✅ Successfully deleted {deleted_count} keyword(s) from {len(projects_to_clean)} inactive projects!"
            )
            print("=" * 80)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
