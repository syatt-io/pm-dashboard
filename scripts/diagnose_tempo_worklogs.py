#!/usr/bin/env python3
"""
Diagnose Tempo worklog structure to understand epic extraction.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.integrations.tempo import TempoAPIClient
from datetime import datetime
import json

tempo = TempoAPIClient()

print("="* 80)
print("TEMPO WORKLOG DIAGNOSTIC")
print("=" * 80)
print()

# Fetch a small sample of worklogs
print("Fetching sample worklogs...")
worklogs = tempo.get_worklogs(
    from_date='2024-01-01',
    to_date='2024-01-31'
)

print(f"Found {len(worklogs)} worklogs in January 2024")
print()

# Show structure of first 5 worklogs
for i, wl in enumerate(worklogs[:5], 1):
    print(f"--- Worklog {i} ---")
    print(f"Issue ID: {wl.get('issue', {}).get('id')}")
    print(f"Time spent: {wl.get('timeSpentSeconds', 0) / 3600:.2f}h")
    print(f"Start date: {wl.get('startDate')}")
    print(f"Author: {wl.get('author', {}).get('accountId')}")

    # Show attributes structure
    attributes = wl.get('attributes', {})
    if attributes:
        print(f"Attributes keys: {list(attributes.keys())}")

        values = attributes.get('values', [])
        if values:
            print(f"  Found {len(values)} attribute values:")
            for attr in values:
                print(f"    key='{attr.get('key')}', value='{attr.get('value')}'")
        else:
            print("  No 'values' in attributes")
    else:
        print("No attributes")

    print()
