#!/usr/bin/env python3
"""Trigger Jira backfill from production environment."""
import os
import requests
import sys

# Get API key from environment
admin_api_key = os.getenv('ADMIN_API_KEY')
if not admin_api_key:
    print("ERROR: ADMIN_API_KEY not set in environment")
    sys.exit(1)

# Trigger backfill (using localhost since we're running from within the container)
response = requests.post(
    'http://localhost:8080/api/backfill/jira?days=30',
    headers={
        'X-Admin-Key': admin_api_key,
        'Content-Type': 'application/json'
    },
    timeout=30
)

print(f"Status: {response.status_code}")
print(f"Response: {response.text}")

if response.status_code == 200:
    print("\n✅ Jira backfill triggered successfully!")
    print("Check logs with: doctl apps logs a2255a3b-23cc-4fd0-baa8-91d622bb912a --type run --follow")
else:
    print(f"\n❌ Failed to trigger backfill: {response.status_code}")
    sys.exit(1)
