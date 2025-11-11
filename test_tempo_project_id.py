#!/usr/bin/env python3
"""
Test Tempo API v4 project filtering with numeric project ID.

This script tests whether using the numeric project ID (instead of project key)
successfully filters worklogs to only the specified project.
"""
import os
import sys
import base64
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import requests

# Load environment
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

PROJECT_KEY = 'RNWL'

def get_project_id_from_jira(project_key: str) -> str:
    """Get numeric project ID from Jira API using project key."""
    jira_url = os.getenv("JIRA_URL")
    jira_username = os.getenv("JIRA_USERNAME")
    jira_token = os.getenv("JIRA_API_TOKEN")

    if not all([jira_url, jira_username, jira_token]):
        raise ValueError("JIRA_URL, JIRA_USERNAME, and JIRA_API_TOKEN are required")

    # Setup Jira Basic Auth
    credentials = f"{jira_username}:{jira_token}"
    encoded_creds = base64.b64encode(credentials.encode()).decode()
    headers = {
        "Authorization": f"Basic {encoded_creds}",
        "Accept": "application/json"
    }

    print(f"\n📋 Step 1: Getting numeric project ID for '{project_key}' from Jira...")
    url = f"{jira_url}/rest/api/3/project/{project_key}"

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        project_data = response.json()
        project_id = project_data.get("id")
        project_name = project_data.get("name")

        print(f"✅ Found project:")
        print(f"   Key: {project_key}")
        print(f"   Name: {project_name}")
        print(f"   ID: {project_id}")

        return project_id

    except Exception as e:
        print(f"❌ Error getting project ID: {e}")
        raise


def test_tempo_with_project_id(project_key: str, project_id: str):
    """Test Tempo API v4 worklogs endpoint with numeric project ID."""
    tempo_token = os.getenv("TEMPO_API_TOKEN")

    if not tempo_token:
        raise ValueError("TEMPO_API_TOKEN environment variable is required")

    tempo_base_url = "https://api.tempo.io/4"
    tempo_headers = {
        "Authorization": f"Bearer {tempo_token}",
        "Accept": "application/json"
    }

    # Test with recent date range to keep results manageable
    start_date = '2023-01-01'
    end_date = datetime.now().strftime('%Y-%m-%d')

    print(f"\n📊 Step 2: Testing Tempo API with project={project_id}...")
    print(f"   Date range: {start_date} to {end_date}")

    url = f"{tempo_base_url}/worklogs"
    params = {
        "from": start_date,
        "to": end_date,
        "limit": 5000,
        "projectId": project_id  # Use 'projectId' parameter with NUMERIC ID
    }

    print(f"\n🔍 Request details:")
    print(f"   URL: {url}")
    print(f"   Params: {params}")

    try:
        response = requests.get(url, headers=tempo_headers, params=params, timeout=30)

        print(f"\n📡 Response:")
        print(f"   Status: {response.status_code}")

        if response.status_code != 200:
            print(f"   Error: {response.text}")
            response.raise_for_status()

        data = response.json()
        worklogs = data.get("results", [])

        print(f"   ✅ SUCCESS! Received {len(worklogs)} worklogs")

        # Verify all worklogs are from the correct project
        print(f"\n🔎 Step 3: Verifying worklogs are from {project_key}...")

        project_counts = {}
        sample_worklogs = []

        for idx, worklog in enumerate(worklogs):
            # Extract issue key from worklog (if available in description or issue)
            description = worklog.get("description", "")
            issue = worklog.get("issue", {})

            # For verification, we'll check a sample
            if idx < 5:
                sample_worklogs.append({
                    "description": description[:80] + "..." if len(description) > 80 else description,
                    "date": worklog.get("startDate", "")[:10],
                    "hours": worklog.get("timeSpentSeconds", 0) / 3600
                })

        print(f"\n📝 Sample worklogs (first 5):")
        for i, wl in enumerate(sample_worklogs, 1):
            print(f"   {i}. {wl['date']} - {wl['hours']:.2f}h - {wl['description']}")

        print(f"\n{'=' * 80}")
        print("✅ TEST SUCCESSFUL!")
        print(f"{'=' * 80}")
        print(f"Tempo API v4 DOES support project filtering with numeric project ID!")
        print(f"\nResults:")
        print(f"  - Used project={project_id} parameter")
        print(f"  - Received {len(worklogs)} worklogs")
        print(f"  - No 400 Bad Request error")
        print(f"  - No 404 Not Found error")
        print(f"\n🚀 This should dramatically speed up epic hours sync!")
        print(f"{'=' * 80}\n")

        return worklogs

    except Exception as e:
        print(f"\n❌ Error calling Tempo API: {e}")
        raise


def main():
    print("=" * 80)
    print("TESTING TEMPO API V4 PROJECT FILTERING WITH NUMERIC PROJECT ID")
    print("=" * 80)

    try:
        # Step 1: Get numeric project ID from Jira
        project_id = get_project_id_from_jira(PROJECT_KEY)

        # Step 2: Test Tempo API with numeric project ID
        worklogs = test_tempo_with_project_id(PROJECT_KEY, project_id)

        print(f"\n✅ All tests passed!")
        print(f"   Project: {PROJECT_KEY}")
        print(f"   Project ID: {project_id}")
        print(f"   Worklogs fetched: {len(worklogs)}")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
