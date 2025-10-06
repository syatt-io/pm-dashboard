#!/usr/bin/env python3
"""
Script to clear existing meeting-project connections so we can re-analyze
using the new title-only matching approach.
"""

import sqlite3
import os

def clear_meeting_connections():
    """Clear all meeting-project connections from the database."""
    db_path = "../database/pm_agent.db"

    if not os.path.exists(db_path):
        print(f"Database {db_path} not found")
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Count existing connections before deletion
        cursor.execute("SELECT COUNT(*) FROM meeting_project_connections")
        count_before = cursor.fetchone()[0]
        print(f"Found {count_before} existing meeting-project connections")

        # Clear all meeting-project connections
        cursor.execute("DELETE FROM meeting_project_connections")
        conn.commit()

        # Verify deletion
        cursor.execute("SELECT COUNT(*) FROM meeting_project_connections")
        count_after = cursor.fetchone()[0]
        print(f"After deletion: {count_after} connections remain")

        conn.close()
        print("✅ Successfully cleared all meeting-project connections!")
        print("🔄 The system will now re-analyze meetings using title-only matching")

    except Exception as e:
        print(f"❌ Error clearing connections: {e}")
        return False

    return True

if __name__ == "__main__":
    clear_meeting_connections()