#!/usr/bin/env python3
"""
Investigation Script: Design Allocation Analysis

Purpose: Investigate why AI forecasts allocate only ~30h (4%) to Design
for 750h projects with custom_designs=3, when expected allocation should
be 12-20% based on characteristic scale.

This script will:
1. Query actual Design allocations from historical data
2. Simulate similar project selection
3. Show which projects AI is learning from
4. Identify data quality issues
5. Determine root cause with evidence

Run: python scripts/investigate_design_allocations.py
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine, text
import math
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database connection
database_url = os.getenv("DATABASE_URL", "sqlite:///pm_agent.db")
engine = create_engine(database_url)


def print_header(title):
    """Print a formatted header"""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")


def query_design_allocations_by_characteristic():
    """Query 1: Design allocations grouped by custom_designs level"""
    print_header("Query 1: Design Allocations by custom_designs Characteristic")

    query = text("""
        WITH project_hours AS (
            SELECT
                eh.project_key,
                SUM(CASE WHEN eh.team = 'Design' THEN eh.hours ELSE 0 END) as design_hours,
                SUM(eh.hours) as total_hours,
                CASE
                    WHEN SUM(eh.hours) > 0
                    THEN (SUM(CASE WHEN eh.team = 'Design' THEN eh.hours ELSE 0 END) * 100.0 / SUM(eh.hours))
                    ELSE 0
                END as design_pct
            FROM epic_hours eh
            GROUP BY eh.project_key
        )
        SELECT
            pc.custom_designs,
            COUNT(DISTINCT pc.project_key) as project_count,
            ROUND(CAST(AVG(ph.design_pct) AS numeric), 2) as avg_design_pct,
            ROUND(CAST(MIN(ph.design_pct) AS numeric), 2) as min_design_pct,
            ROUND(CAST(MAX(ph.design_pct) AS numeric), 2) as max_design_pct,
            ROUND(AVG(ph.design_hours)) as avg_design_hours,
            ROUND(AVG(ph.total_hours)) as avg_total_hours
        FROM project_characteristics pc
        JOIN project_hours ph ON pc.project_key = ph.project_key
        WHERE ph.total_hours > 0
        GROUP BY pc.custom_designs
        ORDER BY pc.custom_designs;
    """)

    with engine.connect() as conn:
        results = conn.execute(query).fetchall()

    if not results:
        print("❌ No data found! epic_hours or project_characteristics table may be empty.")
        return

    print(f"{'Level':<8} {'Projects':<10} {'Avg %':<10} {'Min %':<10} {'Max %':<10} {'Avg Hours':<12} {'Avg Total':<12}")
    print(f"{'-'*8} {'-'*10} {'-'*10} {'-'*10} {'-'*10} {'-'*12} {'-'*12}")

    for row in results:
        level, count, avg_pct, min_pct, max_pct, avg_hours, avg_total = row
        print(f"{level or 'NULL':<8} {count:<10} {avg_pct:<10.2f} {min_pct:<10.2f} {max_pct:<10.2f} {avg_hours:<12.0f} {avg_total:<12.0f}")

    print("\n📊 ANALYSIS:")
    for row in results:
        level = row[0]
        avg_pct = row[2]
        if level == 3:
            if avg_pct < 10:
                print(f"   ⚠️  custom_designs=3 has ONLY {avg_pct:.1f}% Design (expected 12-20%)")
                print(f"   → ROOT CAUSE: Historical projects systematically underfunded Design")
            elif avg_pct >= 12 and avg_pct <= 20:
                print(f"   ✅ custom_designs=3 has {avg_pct:.1f}% Design (within expected range)")
                print(f"   → AI should be allocating correctly. Check similar project selection.")
            else:
                print(f"   🔍 custom_designs=3 has {avg_pct:.1f}% Design (outside expected 12-20%)")


def simulate_similar_project_selection():
    """Query 2: Simulate similar project selection for test case"""
    print_header("Query 2: Similar Project Selection Simulation")

    # Test case: custom_designs=3, be_integrations=1, others=1
    test_characteristics = {
        'be_integrations': 1,
        'custom_theme': 1,
        'custom_designs': 3,
        'ux_research': 1,
        'extensive_customizations': 1,
        'project_oversight': 3
    }

    print(f"Test Case Characteristics:")
    for key, value in test_characteristics.items():
        print(f"  {key}: {value}")
    print()

    # Get all projects with characteristics
    query = text("""
        WITH project_hours AS (
            SELECT
                eh.project_key,
                SUM(CASE WHEN eh.team = 'Design' THEN eh.hours ELSE 0 END) as design_hours,
                SUM(eh.hours) as total_hours,
                CASE
                    WHEN SUM(eh.hours) > 0
                    THEN (SUM(CASE WHEN eh.team = 'Design' THEN eh.hours ELSE 0 END) * 100.0 / SUM(eh.hours))
                    ELSE 0
                END as design_pct
            FROM epic_hours eh
            GROUP BY eh.project_key
        )
        SELECT
            pc.project_key,
            pc.be_integrations,
            pc.custom_theme,
            pc.custom_designs,
            pc.ux_research,
            pc.extensive_customizations,
            pc.project_oversight,
            ph.design_hours,
            ph.total_hours,
            ph.design_pct
        FROM project_characteristics pc
        JOIN project_hours ph ON pc.project_key = ph.project_key
        WHERE ph.total_hours > 0;
    """)

    with engine.connect() as conn:
        projects = conn.execute(query).fetchall()

    if not projects:
        print("❌ No projects found with complete data!")
        return

    # Calculate similarity for each project (same logic as intelligent_forecasting_service.py)
    similarities = []
    for project in projects:
        proj_key = project[0]
        proj_chars = {
            'be_integrations': project[1] or 3,
            'custom_theme': project[2] or 3,
            'custom_designs': project[3] or 3,
            'ux_research': project[4] or 3,
            'extensive_customizations': project[5] or 3,
            'project_oversight': project[6] or 3
        }

        # Calculate Euclidean distance in 6D space
        distance_squared = sum([
            (test_characteristics[key] - proj_chars[key]) ** 2
            for key in test_characteristics.keys()
        ])
        distance = math.sqrt(distance_squared)

        # Similarity score (max distance is sqrt(6*4^2) = 9.8)
        similarity_score = max(0, 1 - (distance / 9.8))

        similarities.append({
            'project_key': proj_key,
            'similarity': similarity_score,
            'distance': distance,
            'characteristics': proj_chars,
            'design_hours': project[7],
            'total_hours': project[8],
            'design_pct': project[9]
        })

    # Sort by similarity (descending) and take top 5
    similarities.sort(key=lambda x: x['similarity'], reverse=True)
    top_5 = similarities[:5]

    print(f"Top 5 Most Similar Projects:")
    print(f"{'Project':<15} {'Similarity':<12} {'Distance':<10} {'Design %':<10} {'Design h':<10} {'Characteristics':<40}")
    print(f"{'-'*15} {'-'*12} {'-'*10} {'-'*10} {'-'*10} {'-'*40}")

    total_design_pct = 0
    for proj in top_5:
        chars_str = f"BE:{proj['characteristics']['be_integrations']} Thm:{proj['characteristics']['custom_theme']} Des:{proj['characteristics']['custom_designs']} UX:{proj['characteristics']['ux_research']}"
        print(f"{proj['project_key']:<15} {proj['similarity']:<12.4f} {proj['distance']:<10.2f} {proj['design_pct']:<10.2f} {proj['design_hours']:<10.0f} {chars_str:<40}")
        total_design_pct += proj['design_pct']

    avg_design_pct = total_design_pct / len(top_5) if top_5 else 0
    print(f"\n📊 ANALYSIS:")
    print(f"   Average Design % in top 5 similar projects: {avg_design_pct:.2f}%")

    if avg_design_pct < 10:
        print(f"   ⚠️  Similar projects have LOW Design allocation ({avg_design_pct:.1f}%)")
        print(f"   → ROOT CAUSE: AI is learning from projects with historically low Design hours")
    elif avg_design_pct >= 12 and avg_design_pct <= 20:
        print(f"   ✅ Similar projects have reasonable Design allocation ({avg_design_pct:.1f}%)")
        print(f"   → AI should be allocating ~{avg_design_pct:.0f}% if following historical patterns")
        print(f"   → If forecasts show 4%, AI is IGNORING historical data!")
    else:
        print(f"   🔍 Similar projects have {avg_design_pct:.1f}% Design (investigate further)")

    # Check if any of top 5 have custom_designs != 3
    different_designs = [p for p in top_5 if p['characteristics']['custom_designs'] != 3]
    if different_designs:
        print(f"\n   ⚠️  {len(different_designs)}/5 similar projects have custom_designs != 3:")
        for p in different_designs:
            print(f"      - {p['project_key']}: custom_designs={p['characteristics']['custom_designs']} (Design: {p['design_pct']:.1f}%)")
        print(f"   → Similar project selection may not be prioritizing custom_designs characteristic")


def check_data_quality():
    """Query 3: Check for missing or zero Design hours"""
    print_header("Query 3: Data Quality Check")

    query = text("""
        WITH project_hours AS (
            SELECT
                eh.project_key,
                SUM(CASE WHEN eh.team = 'Design' THEN eh.hours ELSE 0 END) as design_hours,
                SUM(eh.hours) as total_hours
            FROM epic_hours eh
            GROUP BY eh.project_key
        )
        SELECT
            pc.project_key,
            pc.custom_designs,
            ph.design_hours,
            ph.total_hours,
            CASE
                WHEN ph.design_hours = 0 THEN 'ZERO Design hours'
                WHEN ph.total_hours = 0 THEN 'ZERO total hours'
                WHEN ph.project_key IS NULL THEN 'No epic_hours data'
                ELSE 'OK'
            END as status
        FROM project_characteristics pc
        LEFT JOIN project_hours ph ON pc.project_key = ph.project_key
        WHERE ph.design_hours = 0 OR ph.total_hours = 0 OR ph.project_key IS NULL
        ORDER BY pc.project_key;
    """)

    with engine.connect() as conn:
        results = conn.execute(query).fetchall()

    if not results:
        print("✅ No data quality issues found! All projects have non-zero Design and total hours.")
        return

    print(f"Found {len(results)} projects with data quality issues:\n")
    print(f"{'Project':<15} {'custom_designs':<15} {'Design Hours':<15} {'Total Hours':<15} {'Status':<30}")
    print(f"{'-'*15} {'-'*15} {'-'*15} {'-'*15} {'-'*30}")

    zero_design_count = 0
    for row in results:
        proj_key, custom_designs, design_h, total_h, status = row
        print(f"{proj_key:<15} {custom_designs or 'NULL':<15} {design_h or 0:<15.0f} {total_h or 0:<15.0f} {status:<30}")
        if status == 'ZERO Design hours':
            zero_design_count += 1

    print(f"\n📊 ANALYSIS:")
    print(f"   Projects with ZERO Design hours: {zero_design_count}")
    if zero_design_count > 0:
        print(f"   ⚠️  {zero_design_count} projects have no Design allocation recorded")
        print(f"   → This could bias average Design percentages downward")
        print(f"   → ROOT CAUSE: Data import issue or Design work categorized differently")


def show_full_team_breakdown():
    """Query 4: Show full team breakdown for all projects"""
    print_header("Query 4: Team Allocation Breakdown (All Teams)")

    query = text("""
        WITH team_hours AS (
            SELECT
                eh.project_key,
                eh.team,
                SUM(eh.hours) as hours
            FROM epic_hours eh
            GROUP BY eh.project_key, eh.team
        ),
        project_totals AS (
            SELECT
                project_key,
                SUM(hours) as total_hours
            FROM team_hours
            GROUP BY project_key
        )
        SELECT
            pc.project_key,
            pc.custom_designs,
            th.team,
            th.hours,
            pt.total_hours,
            ROUND((th.hours * 100.0 / pt.total_hours), 2) as percentage
        FROM project_characteristics pc
        JOIN project_totals pt ON pc.project_key = pt.project_key
        JOIN team_hours th ON pc.project_key = th.project_key
        WHERE pt.total_hours > 0 AND pc.custom_designs = 3
        ORDER BY pc.project_key, th.hours DESC;
    """)

    with engine.connect() as conn:
        results = conn.execute(query).fetchall()

    if not results:
        print("❌ No data found for custom_designs=3 projects!")
        return

    current_project = None
    print(f"Projects with custom_designs=3 (showing all team allocations):\n")

    for row in results:
        proj_key, custom_designs, team, hours, total, pct = row

        if proj_key != current_project:
            if current_project is not None:
                print()  # Blank line between projects
            print(f"Project: {proj_key} (Total: {total:.0f}h)")
            print(f"  {'Team':<20} {'Hours':<10} {'Percentage':<10}")
            print(f"  {'-'*20} {'-'*10} {'-'*10}")
            current_project = proj_key

        print(f"  {team:<20} {hours:<10.0f} {pct:<10.2f}%")


def main():
    """Run all investigation queries"""
    print("\n" + "="*80)
    print(" "*20 + "DESIGN ALLOCATION INVESTIGATION")
    print("="*80)
    print("\nPurpose: Understand why AI allocates only ~30h (4%) to Design")
    print("         for 750h projects with custom_designs=3\n")

    try:
        # Run all queries
        query_design_allocations_by_characteristic()
        simulate_similar_project_selection()
        check_data_quality()
        show_full_team_breakdown()

        print_header("Summary & Recommendations")
        print("Review the analyses above to determine root cause:")
        print()
        print("Possible Root Causes:")
        print("  1. Historical projects genuinely had low Design allocations")
        print("     → Fix: Re-categorize historical data or adjust baseline expectations")
        print()
        print("  2. Similar project selection not prioritizing custom_designs")
        print("     → Fix: Add weighting to similarity algorithm for custom_designs")
        print()
        print("  3. Data quality issue (missing/zero Design hours)")
        print("     → Fix: Re-backfill epic_hours with correct team assignments")
        print()
        print("  4. AI ignoring historical patterns in prompt")
        print("     → Fix: Strengthen prompt guidance for Design allocation")
        print()

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
