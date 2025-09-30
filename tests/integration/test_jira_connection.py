#!/usr/bin/env python3
"""Test script to verify Jira API connectivity."""

import os
import base64
import requests
from dotenv import load_dotenv

load_dotenv()

# Get credentials from environment
jira_url = os.getenv("JIRA_URL")
username = os.getenv("JIRA_USERNAME")
api_token = os.getenv("JIRA_API_TOKEN")

print("Testing Jira API Connection")
print("=" * 50)
print(f"Jira URL: {jira_url}")
print(f"Username: {username}")
print(f"API Token: {'*' * 20 if api_token else 'NOT SET'}")
print()

if not all([jira_url, username, api_token]):
    print("ERROR: Missing required environment variables!")
    print(f"JIRA_URL: {'✓' if jira_url else '✗'}")
    print(f"JIRA_USERNAME: {'✓' if username else '✗'}")
    print(f"JIRA_API_TOKEN: {'✓' if api_token else '✗'}")
    exit(1)

# Create auth header
auth_string = base64.b64encode(f"{username}:{api_token}".encode()).decode()

# Test API call
print("Making API request...")
response = requests.get(
    f"{jira_url}/rest/api/3/project",
    headers={
        "Authorization": f"Basic {auth_string}",
        "Accept": "application/json"
    }
)

print(f"Status Code: {response.status_code}")
print()

if response.status_code == 200:
    projects = response.json()
    print(f"✓ SUCCESS! Retrieved {len(projects)} projects")
    print()
    print("Projects:")
    for project in projects[:5]:  # Show first 5
        print(f"  - {project.get('key')}: {project.get('name')}")
    if len(projects) > 5:
        print(f"  ... and {len(projects) - 5} more")
else:
    print(f"✗ FAILED!")
    print(f"Response: {response.text}")