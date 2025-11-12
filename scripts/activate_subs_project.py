#!/usr/bin/env python3
"""Activate SUBS project in the database.

This script ensures SUBS project is marked as active so it's included in backfills.
Run this from production before triggering a Jira backfill.
"""
import sys
from src.utils.database import get_engine
from sqlalchemy import text
from datetime import datetime


def activate_subs():
    """Activate SUBS project in database."""
    engine = get_engine()

    print("🔍 Checking SUBS project status...\n")

    with engine.connect() as conn:
        # Check if SUBS exists
        result = conn.execute(
            text("SELECT key, name, is_active FROM projects WHERE key = 'SUBS'")
        )
        subs_row = result.fetchone()

        if subs_row:
            key, name, is_active = subs_row
            print(f"📋 SUBS project found:")
            print(f"   Key: {key}")
            print(f"   Name: {name}")
            print(f"   Active: {is_active}\n")

            if not is_active:
                print("⚠️  SUBS is NOT active. Activating now...")
                conn.execute(
                    text(
                        """
                        UPDATE projects
                        SET is_active = true, updated_at = :updated_at
                        WHERE key = 'SUBS'
                    """
                    ),
                    {"updated_at": datetime.now()},
                )
                conn.commit()
                print("✅ SUBS has been activated!\n")
            else:
                print("✅ SUBS is already active!\n")
        else:
            print("❌ SUBS project NOT FOUND in database.")
            print("Creating SUBS project now...\n")

            # Insert with minimal columns
            conn.execute(
                text(
                    """
                    INSERT INTO projects (key, name, is_active, created_at, updated_at)
                    VALUES (:key, :name, :is_active, :created_at, :updated_at)
                """
                ),
                {
                    "key": "SUBS",
                    "name": "Snuggle Bugz - Shopify",
                    "is_active": True,
                    "created_at": datetime.now(),
                    "updated_at": datetime.now(),
                },
            )
            conn.commit()
            print("✅ SUBS project has been created and activated!\n")

    # Verify active projects
    print("Verifying active projects:")
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT key, name FROM projects WHERE is_active = true ORDER BY key")
        )
        active_projects = result.fetchall()
        print(f"Total: {len(active_projects)} active projects\n")

        subs_found = False
        for key, name in active_projects:
            if key == "SUBS":
                print(f"👉 {key}: {name}")
                subs_found = True
                break

        if not subs_found:
            print("❌ WARNING: SUBS not found in active projects!")
            return False

    print("\n✅ SUBS is confirmed active and ready for backfill!")
    return True


if __name__ == "__main__":
    try:
        success = activate_subs()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
