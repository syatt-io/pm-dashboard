#!/usr/bin/env python3
"""
Test script to verify the fixed keyword matching logic with word boundaries.
"""

import os
import sys
import re
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


def matches_keyword(text, keyword):
    """Check if keyword matches as a whole word in text."""
    # Escape special regex characters in the keyword
    escaped_keyword = re.escape(keyword)
    # Match whole words only using word boundaries
    pattern = r"\b" + escaped_keyword + r"\b"
    return bool(re.search(pattern, text, re.IGNORECASE))


def test_matching():
    """Test keyword matching against the problematic meeting."""
    print("=" * 80)
    print("FIXED KEYWORD MATCHING DEBUG (With Word Boundaries)")
    print("=" * 80)
    print(f"\nMeeting Title: {MEETING_TITLE}")
    print(f"Meeting Title (lowercase): {MEETING_TITLE.lower()}")
    print("\n" + "-" * 80)

    # Get all project keywords
    keywords_by_project = get_project_keywords()

    print(f"\nTotal projects with keywords: {len(keywords_by_project)}")

    print("\n" + "-" * 80)
    print("\nTesting with FIXED word boundary matching:")
    print("-" * 80)

    title_lower = MEETING_TITLE.lower()
    summary_lower = MEETING_SUMMARY.lower()

    matching_projects = []
    for project_key, keywords in keywords_by_project.items():
        matches = []
        for keyword in keywords:
            # Use word boundary matching (FIXED)
            if matches_keyword(title_lower, keyword) or matches_keyword(
                summary_lower, keyword
            ):
                matches.append(keyword)

        if matches:
            matching_projects.append((project_key, matches))
            print(f"✅ {project_key} MATCHES via keywords: {matches}")

    if not matching_projects:
        print("❌ No project keywords match this meeting (CORRECT!)")

    print("\n" + "=" * 80)
    print(f"RESULT: {len(matching_projects)} project(s) would show this meeting")
    if matching_projects:
        print(f"Projects: {[p[0] for p in matching_projects]}")
    else:
        print("✅ SUCCESS: Meeting correctly excluded from all projects!")
    print("=" * 80)

    # Test a few specific cases
    print("\n" + "=" * 80)
    print("SPECIFIC TEST CASES:")
    print("=" * 80)
    test_cases = [
        ("project", "projections", False),  # Should NOT match
        ("project", "the project is done", True),  # Should match
        ("bugz", "snugglebugz", False),  # Should NOT match
        ("bugz", "snuggle bugz rocks", True),  # Should match
    ]

    for keyword, text, should_match in test_cases:
        result = matches_keyword(text.lower(), keyword)
        status = "✅" if result == should_match else "❌"
        expected = "MATCH" if should_match else "NO MATCH"
        actual = "MATCH" if result else "NO MATCH"
        print(
            f"{status} Keyword '{keyword}' in '{text}': Expected {expected}, Got {actual}"
        )


if __name__ == "__main__":
    try:
        test_matching()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)
