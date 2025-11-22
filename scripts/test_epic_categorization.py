#!/usr/bin/env python3
"""
Test script for epic categorization functionality.
Run this locally to verify AI categorization is working.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.epic_categorization_service import EpicCategorizationService
from src.utils.database import get_session
from src.models.epic_category import EpicCategory
from src.models.epic_category_mapping import EpicCategoryMapping


def test_categorization():
    """Test epic categorization with sample data."""

    print("=" * 80)
    print("Testing Epic Categorization Service")
    print("=" * 80)

    # Initialize service
    try:
        service = EpicCategorizationService()
        print("✅ EpicCategorizationService initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize service: {e}")
        return False

    # Check database connection
    session = get_session()

    # Check if categories exist
    categories = session.query(EpicCategory).all()
    print(f"\n📊 Found {len(categories)} epic categories in database:")
    for cat in categories:
        print(f"  - {cat.name}")

    if not categories:
        print(
            "⚠️  No categories found! You need to create some in Settings > Epic Categories first"
        )
        return False

    # Check if training examples exist
    mappings = session.query(EpicCategoryMapping).limit(10).all()
    print(
        f"\n🎓 Found {session.query(EpicCategoryMapping).count()} training examples (showing 10):"
    )
    for mapping in mappings:
        print(f"  - {mapping.epic_key} → {mapping.category}")

    # Sample epics to categorize
    sample_epics = [
        {
            "epic_key": "MMS-TEST-1",
            "epic_summary": "Implement user authentication and login flow",
        },
        {
            "epic_key": "MMS-TEST-2",
            "epic_summary": "Design and build product catalog pages",
        },
        {
            "epic_key": "MMS-TEST-3",
            "epic_summary": "Set up CI/CD pipeline and deployment automation",
        },
    ]

    print(f"\n🧪 Testing categorization on {len(sample_epics)} sample epics:")
    for epic in sample_epics:
        print(f"  - {epic['epic_key']}: {epic['epic_summary']}")

    # Run categorization
    try:
        print("\n🤖 Running AI categorization...")
        categories_dict = service.categorize_epics(
            epics=sample_epics, project_key="MMS"
        )

        print("\n✅ Categorization results:")
        for epic_key, category in categories_dict.items():
            if category:
                print(f"  - {epic_key} → {category}")
            else:
                print(f"  - {epic_key} → (no category)")

        return True

    except Exception as e:
        print(f"\n❌ Categorization failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    finally:
        session.close()


if __name__ == "__main__":
    success = test_categorization()
    sys.exit(0 if success else 1)
