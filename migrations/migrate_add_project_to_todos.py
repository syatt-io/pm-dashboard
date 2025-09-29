#!/usr/bin/env python3
"""
Add project_key column to todo_items table.
"""

import sqlite3

def add_project_column():
    """Add project_key column to todo_items table."""
    conn = sqlite3.connect('pm_agent.db')
    cursor = conn.cursor()

    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(todo_items)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'project_key' not in columns:
            print("Adding project_key column to todo_items table...")
            cursor.execute("ALTER TABLE todo_items ADD COLUMN project_key TEXT")
            conn.commit()
            print("✅ Added project_key column successfully")
        else:
            print("✅ project_key column already exists")

    except Exception as e:
        print(f"❌ Error adding project_key column: {e}")
        conn.rollback()

    finally:
        conn.close()

if __name__ == "__main__":
    add_project_column()