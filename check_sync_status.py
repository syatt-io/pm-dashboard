#!/usr/bin/env python3
"""Check vector sync status from the database."""

import os
from datetime import datetime
from sqlalchemy import create_engine, text

# Get database URL from environment
database_url = os.getenv('DATABASE_URL')
if not database_url:
    print("❌ DATABASE_URL not set in environment")
    print("Please run: export DATABASE_URL=<your_production_db_url>")
    exit(1)

# Ensure proper format for SQLAlchemy
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

engine = create_engine(database_url)

print("🔍 Checking vector sync status...\n")

try:
    with engine.connect() as conn:
        # Check if table exists
        result = conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'vector_sync_status'
            )
        """))
        table_exists = result.fetchone()[0]

        if not table_exists:
            print("⚠️  Table 'vector_sync_status' does not exist!")
            print("This suggests vector ingestion has never been set up or the migration hasn't run.")
            exit(1)

        # Query sync status
        result = conn.execute(text("""
            SELECT source, last_sync
            FROM vector_sync_status
            ORDER BY last_sync DESC NULLS LAST
        """))

        rows = result.fetchall()

        if not rows:
            print("⚠️  No sync records found in database!")
            print("This means vector ingestion tasks have never successfully completed.")
        else:
            print("Last sync timestamps:\n")
            print(f"{'Source':<15} {'Last Sync':<30} {'Age':<20}")
            print("-" * 65)

            for row in rows:
                source = row[0]
                last_sync = row[1]

                if last_sync:
                    age = datetime.now() - last_sync
                    days = age.days
                    hours = age.seconds // 3600
                    minutes = (age.seconds % 3600) // 60

                    age_str = f"{days}d {hours}h {minutes}m ago" if days > 0 else f"{hours}h {minutes}m ago"

                    # Warn if over 1 day old
                    emoji = "🔴" if days >= 1 else "🟢"

                    print(f"{emoji} {source:<14} {last_sync.strftime('%Y-%m-%d %H:%M:%S UTC'):<30} {age_str}")
                else:
                    print(f"⚪ {source:<14} {'Never synced':<30}")

            print("\n📊 Summary:")
            stale_sources = [r[0] for r in rows if r[1] and (datetime.now() - r[1]).days >= 1]
            if stale_sources:
                print(f"🔴 Stale sources (>1 day): {', '.join(stale_sources)}")
            else:
                print("🟢 All sources synced within last 24 hours")

except Exception as e:
    print(f"❌ Error querying database: {e}")
    exit(1)
