#!/usr/bin/env python3
"""
Quick test to verify BEVS data is now correct in historical context.
Expected: 766h total, 53.5h Design (6.98%)
Bug was: 717.5h total, 26.5h Design (3.7%)
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.services.intelligent_forecasting_service import IntelligentForecastingService
from src.utils.database import get_session

session = get_session()
service = IntelligentForecastingService(session)

# Get similar projects for a test case
config_dict = {
    "project_key": "TEST",
    "total_hours": 750,
    "duration_months": 5,
    "be_integrations": 1,
    "custom_theme": 1,
    "custom_designs": 3,
    "ux_research": 1,
    "extensive_customizations": 1,
    "project_oversight": 3,
    "forecasting_start_date": "2024-11-01",
    "forecasting_end_date": "2025-04-01",
}

# Get similar projects
similar_projects = service._find_similar_projects(config_dict, limit=5)

# Find BEVS
bevs = next((p for p in similar_projects if p["project_key"] == "BEVS"), None)

if bevs:
    print("✅ BEVS found in similar projects!")
    print(f"\nTotal Hours: {bevs['total_hours']}h")
    print(f"Date Range: {bevs['date_range']['start']} to {bevs['date_range']['end']}")
    print(f"\nTeam Hours:")
    for team, hours in sorted(bevs["team_hours"].items(), key=lambda x: -x[1]):
        pct = (hours / bevs['total_hours'] * 100) if bevs['total_hours'] > 0 else 0
        print(f"  - {team}: {hours}h ({pct:.1f}%)")

    # Check Design allocation
    design_hours = bevs["team_hours"].get("Design", 0)
    design_pct = (design_hours / bevs['total_hours'] * 100) if bevs['total_hours'] > 0 else 0

    print(f"\n🎯 Design Allocation Test:")
    print(f"   Expected: 53.5h (6.98%)")
    print(f"   Actual:   {design_hours}h ({design_pct:.2f}%)")

    if abs(design_hours - 53.5) < 1 and abs(bevs['total_hours'] - 766.25) < 1:
        print("\n✅✅✅ FIX SUCCESSFUL! Data matches expected values!")
    else:
        print(f"\n❌ FIX FAILED! Data still incorrect.")
        print(f"   Total Hours - Expected: 766.25h, Got: {bevs['total_hours']}h")
        print(f"   Design Hours - Expected: 53.5h, Got: {design_hours}h")
else:
    print("❌ BEVS not found in similar projects!")

session.close()
