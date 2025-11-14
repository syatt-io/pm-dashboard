"""Test script to verify learned epic ranges are loaded correctly."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.database import get_session
from src.services.intelligent_forecasting_service import IntelligentForecastingService


def main():
    """Test learned epic ranges loading and prompt generation."""
    print("=" * 80)
    print("TESTING LEARNED EPIC RANGES")
    print("=" * 80)

    session = get_session()

    try:
        # Create service instance
        print("\n1. Creating IntelligentForecastingService instance...")
        service = IntelligentForecastingService(session)

        # Test loading learned epic ranges
        print("\n2. Loading learned epic ranges from database...")
        learned_ranges = service._get_learned_epic_ranges()

        if learned_ranges:
            print(f"✅ Successfully loaded {len(learned_ranges)} learned epic ranges:")
            print()
            for category, range_str in sorted(learned_ranges.items()):
                print(f"   - {category:30s}: {range_str}")
        else:
            print("❌ No learned epic ranges found in database")
            return

        # Test prompt generation
        print("\n3. Testing epic category prompt section generation...")
        prompt_section = service._generate_epic_category_prompt_section()

        print("\n" + "=" * 80)
        print("GENERATED PROMPT SECTION:")
        print("=" * 80)
        print(prompt_section)
        print("=" * 80)

        # Verify learned data is being used
        if "LEARNED from historical data" in prompt_section:
            print("\n✅ SUCCESS: Prompt is using LEARNED epic ranges from database!")
        elif (
            "HARDCODED" in prompt_section
            or "Common epic categories for web application projects:" in prompt_section
        ):
            print("\n⚠️  WARNING: Prompt is using HARDCODED epic ranges (fallback mode)")
        else:
            print(
                "\n❓ UNKNOWN: Could not determine if learned or hardcoded ranges are being used"
            )

        print("\n" + "=" * 80)
        print("TEST COMPLETED SUCCESSFULLY!")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
    finally:
        session.close()


if __name__ == "__main__":
    main()
