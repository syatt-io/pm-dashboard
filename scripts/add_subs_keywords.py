#!/usr/bin/env python3
"""Add keywords for SUBS project to enable Fireflies search filtering."""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.database import get_engine
from sqlalchemy import text

def add_subs_keywords():
    """Add keywords for SUBS (Snuggle Bugz) project."""

    keywords = [
        'snuggle',
        'bugz',
        'snugglebugz',
        'snugglebug',
        'baby',
        'store'
    ]

    engine = get_engine()

    with engine.connect() as conn:
        # Check if keywords already exist
        result = conn.execute(
            text("SELECT keyword FROM project_keywords WHERE project_key = 'SUBS'")
        )
        existing = [row[0] for row in result]

        if existing:
            print(f"✅ SUBS already has keywords: {existing}")
            return

        # Add keywords
        for keyword in keywords:
            conn.execute(
                text("INSERT INTO project_keywords (project_key, keyword) VALUES (:key, :keyword)"),
                {"key": "SUBS", "keyword": keyword.lower()}
            )
            print(f"   Added keyword: {keyword}")

        conn.commit()
        print(f"\n✅ Successfully added {len(keywords)} keywords for SUBS project")
        print(f"📋 Keywords: {', '.join(keywords)}")

if __name__ == "__main__":
    add_subs_keywords()
