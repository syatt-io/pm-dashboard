#!/usr/bin/env python3
"""Check SRLK hours in database"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models import EpicHours
from src.utils.database import get_session
from collections import defaultdict

session = get_session()

# Get SRLK total hours
srlk_records = session.query(EpicHours).filter_by(project_key="SRLK").all()
total_hours = sum([r.hours for r in srlk_records])

print(f"SRLK total hours in DB: {total_hours:.2f}h")
print(f"Expected: 1737h")
if total_hours > 0:
    print(f"Ratio: {total_hours / 1737:.2f}x")
print()

# Show breakdown by epic
print("Breakdown by epic:")
epic_hours = defaultdict(float)
for r in srlk_records:
    epic_hours[r.epic_key] += r.hours

for epic, hours in sorted(epic_hours.items(), key=lambda x: -x[1]):
    print(f"  {epic}: {hours:.2f}h")

print()
print(f"Total records: {len(srlk_records)}")

session.close()
