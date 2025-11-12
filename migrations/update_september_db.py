#!/usr/bin/env python3
"""
Update database with correct September 2025 hours from our complete analysis.
"""

import sqlite3

# Results from our complete September analysis
september_hours = {
    "BEAN": 30.00,
    "BEAU": 4.17,
    "BEVI": 5.25,
    "BEVS": 51.25,
    "BIDI": 41.25,
    "BIGO": 46.25,
    "BRNS": 2.50,
    "CAR": 1.25,
    "COOP": 125.00,
    "ECAT": 27.43,
    "ECSC": 37.75,
    "ETHEL": 33.75,
    "IRIS": 7.00,
    "MAMS": 36.92,
    "RENW": 19.75,
    "RNWL": 149.17,
    "SBUD": 20.33,
    "SBUG": 0.50,
    "SLABS": 8.00,
    "SRLK": 11.50,
    "SUBS": 109.17,
    "SYDA": 11.75,
    "SYIO": 20.50,
    "SYIT": 305.92,
    "SYWT": 34.75,
    "TOMD": 5.33,
    "TOML": 28.75,
    "TOWN": 4.00,
    "TRK": 3.00,
    "TURK": 32.25,
    "UTC": 0.50,
    "VINY": 4.83,
}


def update_database():
    """Update database with correct September hours."""
    conn = sqlite3.connect("../database/pm_agent.db")
    cursor = conn.cursor()

    updated = 0

    # Get all projects
    cursor.execute("SELECT key FROM projects WHERE is_active = 1")
    active_projects = [row[0] for row in cursor.fetchall()]

    for project_key in active_projects:
        september_hours_value = september_hours.get(project_key, 0)

        # Update current_month_hours with September data
        cursor.execute(
            """
            UPDATE projects
            SET current_month_hours = ?,
                updated_at = datetime('now')
            WHERE key = ?
        """,
            (september_hours_value, project_key),
        )

        if cursor.rowcount > 0:
            updated += 1
            print(
                f"Updated {project_key}: current_month_hours={september_hours_value:.2f}h"
            )

    conn.commit()
    conn.close()

    print(f"\n✅ Updated {updated} projects with correct September 2025 hours")


if __name__ == "__main__":
    update_database()
