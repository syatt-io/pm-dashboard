#!/usr/bin/env python3
"""Check hours for all projects in database"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models import EpicHours
from src.utils.database import get_session
from collections import defaultdict

session = get_session()

PROJECTS = ["BIGO", "BMBY", "SRLK", "COOP", "CAR", "BEVS", "IRIS"]

print("=" * 80)
print("EPIC HOURS BY PROJECT")
print("=" * 80)
print()

for project in PROJECTS:
    records = session.query(EpicHours).filter_by(project_key=project).all()
    total_hours = sum([r.hours for r in records])

    print(f"{project}:")
    print(f"  Records: {len(records)}")
    print(f"  Total hours: {total_hours:.2f}h")
    print()

# Overall stats
all_records = session.query(EpicHours).all()
print("=" * 80)
print(f"TOTAL: {len(all_records)} records across all projects")
print("=" * 80)

session.close()
