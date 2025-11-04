#!/usr/bin/env python3
"""
Standalone script to run Jira backfill directly.

Usage:
    python run_jira_backfill.py [days_back]

Example:
    python run_jira_backfill.py 2555    # Backfill last 7 years
"""

import sys
import asyncio

# Add project root to path
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.tasks.backfill_jira import backfill_jira_issues

if __name__ == "__main__":
    # Get days from command line args, default to 2555 (7 years)
    days_back = int(sys.argv[1]) if len(sys.argv) > 1 else 2555

    print(f"Starting Jira backfill for {days_back} days...")
    result = asyncio.run(backfill_jira_issues(days_back=days_back))

    if result.get("success"):
        print(f"✅ Backfill completed successfully!")
        print(f"   - Issues found: {result.get('issues_found', 0)}")
        print(f"   - Issues ingested: {result.get('issues_ingested', 0)}")
        sys.exit(0)
    else:
        print(f"❌ Backfill failed: {result.get('error', 'Unknown error')}")
        sys.exit(1)
