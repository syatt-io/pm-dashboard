#!/usr/bin/env python3
"""
Test script to debug keyword matching logic for meeting filtering.
This simulates the matching logic from src/routes/meetings.py lines 235-238.
"""

import os
import sys
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

# Get database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    pytest.skip("DATABASE_URL environment variable not set", allow_module_level=True)

# Problematic meeting title
MEETING_TITLE = "Jon <> Brit <> Mike | Projections & PhillyN/A"
MEETING_SUMMARY = ""  # Unknown summary for now


def get_project_keywords():
    """Fetch all project keywords from production database."""
    engine = create_engine(DATABASE_URL)
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                SELECT project_key, keyword
                FROM project_keywords
                ORDER BY project_key, keyword
            """
                )
            )
            keywords_by_project = {}
            for row in result:
                project_key, keyword = row
                if project_key not in keywords_by_project:
                    keywords_by_project[project_key] = []
                keywords_by_project[project_key].append(keyword.lower())
            return keywords_by_project
    except OperationalError as e:
        pytest.skip(f"project_keywords table not found: {e}")


def test_matching():
    """Test keyword matching against the problematic meeting."""
    print("=" * 80)
    print("KEYWORD MATCHING DEBUG")
    print("=" * 80)
    print(f"\nMeeting Title: {MEETING_TITLE}")
    print(f"Meeting Title (lowercase): {MEETING_TITLE.lower()}")
    print("\n" + "-" * 80)

    # Get all project keywords
    keywords_by_project = get_project_keywords()

    print(f"\nTotal projects with keywords: {len(keywords_by_project)}")
    print("\nAll Project Keywords:")
    for project_key, keywords in sorted(keywords_by_project.items()):
        print(f"  {project_key}: {keywords}")

    print("\n" + "-" * 80)
    print("\nTesting which keywords match this meeting title:")
    print("-" * 80)

    title_lower = MEETING_TITLE.lower()
    summary_lower = MEETING_SUMMARY.lower()

    matching_projects = []
    for project_key, keywords in keywords_by_project.items():
        matches = []
        for keyword in keywords:
            # This is the exact logic from src/routes/meetings.py:235-238
            if keyword in title_lower or keyword in summary_lower:
                matches.append(keyword)

        if matches:
            matching_projects.append((project_key, matches))
            print(f"✅ {project_key} MATCHES via keywords: {matches}")

    if not matching_projects:
        print("❌ No project keywords match this meeting")

    print("\n" + "=" * 80)
    print(f"CONCLUSION: {len(matching_projects)} project(s) would show this meeting")
    if matching_projects:
        print(f"Projects: {[p[0] for p in matching_projects]}")
    print("=" * 80)


if __name__ == "__main__":
    try:
        test_matching()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
