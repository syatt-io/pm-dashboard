#!/usr/bin/env python3
"""
AI-powered epic grouping analysis script.

This script fetches all unique epic names from the database,
uses AI to propose natural groupings (canonical categories),
and saves the mappings to the epic_baseline_mappings table.

The AI analyzes the data organically rather than forcing predefined categories,
allowing the number of groups to be driven by the actual data (could be 15, 20, 40, etc.).

Usage:
    python scripts/analyze_epic_groups.py
    python scripts/analyze_epic_groups.py --dry-run  # Preview without saving
"""

import sys
import json
import logging
import argparse
from pathlib import Path
from typing import Dict, List
from datetime import datetime, timezone
from collections import Counter

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from config.settings import Settings
from src.models import EpicHours, EpicBaselineMapping
from src.utils.database import get_session

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_llm():
    """Create LLM instance based on centralized settings."""
    ai_config = Settings.get_fresh_ai_config()

    if not ai_config:
        logger.error("AI configuration not available")
        return None

    logger.info(f"Creating LLM with provider={ai_config.provider}, model={ai_config.model}")

    if ai_config.provider == "openai":
        return ChatOpenAI(
            model=ai_config.model,
            temperature=0.1,  # Low temperature for consistent grouping
            max_tokens=4000,  # Need space for JSON response
            api_key=ai_config.api_key,
        )
    elif ai_config.provider == "anthropic":
        return ChatAnthropic(
            model=ai_config.model,
            anthropic_api_key=ai_config.api_key,
            temperature=0.1,
            max_tokens=4000,
        )
    elif ai_config.provider == "google":
        return ChatGoogleGenerativeAI(
            model=ai_config.model,
            google_api_key=ai_config.api_key,
            temperature=0.1,
            max_tokens=4000,
        )
    else:
        logger.error(f"Unsupported AI provider: {ai_config.provider}")
        return None


def fetch_unique_epic_names(session) -> List[str]:
    """Fetch all unique epic_summary values from epic_hours table."""
    logger.info("Fetching unique epic names from database...")

    results = (
        session.query(EpicHours.epic_summary)
        .filter(EpicHours.epic_summary.isnot(None))
        .filter(EpicHours.epic_summary != "")
        .distinct()
        .all()
    )

    epic_names = [r.epic_summary for r in results]
    logger.info(f"Found {len(epic_names)} unique epic names")

    return epic_names


def analyze_with_ai(llm, epic_names: List[str]) -> Dict[str, str]:
    """Use AI to analyze epic names and propose canonical groupings.

    Args:
        llm: LangChain LLM instance
        epic_names: List of unique epic names to analyze

    Returns:
        Dictionary mapping epic_name -> canonical_category
    """
    logger.info(f"Sending {len(epic_names)} epic names to AI for grouping analysis...")

    # Format epic names for the prompt
    epic_list = "\n".join([f"- {name}" for name in sorted(epic_names)])

    system_prompt = """You are an expert at analyzing e-commerce project epic names and grouping similar epics together.

Your task is to analyze a list of epic names from multiple Shopify/e-commerce projects and create canonical categories that group similar epics.

Instructions:
1. Analyze all the epic names and identify natural groupings
2. Create canonical category names (lowercase, concise, descriptive)
3. Similar epics should map to the same category, even if worded differently
   Examples:
   - "Product Details", "PDP Details", "Product detail page" → "product details"
   - "Cart", "Shopping Cart", "Cart Drawer" → "cart"
   - "Product Listings", "PLP", "Collection Pages" → "product listings"

4. Create as many or as few categories as makes logical sense (could be 15-40+)
5. Use common e-commerce patterns (product details, cart, checkout, search, header, footer, etc.)
6. Keep category names simple and consistent

Return a JSON object mapping each epic name to its canonical category:
{
  "Product Details": "product details",
  "PDP Details": "product details",
  "Cart": "cart",
  "Shopping Cart": "cart",
  ...
}

IMPORTANT: Return ONLY valid JSON, no other text or explanation."""

    user_prompt = f"""Analyze these epic names from e-commerce projects and create canonical groupings:

{epic_list}

Return JSON mapping each epic name to its canonical category."""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ]

    try:
        response = llm.invoke(messages)
        response_text = response.content.strip()

        # Try to extract JSON if wrapped in markdown code blocks
        if response_text.startswith("```"):
            # Remove markdown code blocks
            lines = response_text.split("\n")
            json_lines = []
            in_code_block = False
            for line in lines:
                if line.startswith("```"):
                    in_code_block = not in_code_block
                    continue
                if in_code_block or (not line.startswith("```") and json_lines):
                    json_lines.append(line)
            response_text = "\n".join(json_lines)

        mappings = json.loads(response_text)
        logger.info(f"AI proposed {len(set(mappings.values()))} canonical categories")

        return mappings

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse AI response as JSON: {e}")
        logger.error(f"Response text: {response_text}")
        raise
    except Exception as e:
        logger.error(f"Error during AI analysis: {e}")
        raise


def save_mappings(session, mappings: Dict[str, str], dry_run: bool = False):
    """Save epic-to-category mappings to database.

    Args:
        session: SQLAlchemy session
        mappings: Dictionary of epic_summary -> baseline_category
        dry_run: If True, don't actually save to database
    """
    if dry_run:
        logger.info("DRY RUN: Would save mappings to database (skipping)")
        return

    logger.info("Clearing existing mappings...")
    session.query(EpicBaselineMapping).delete()

    logger.info(f"Saving {len(mappings)} mappings to database...")

    for epic_summary, baseline_category in mappings.items():
        mapping = EpicBaselineMapping(
            epic_summary=epic_summary,
            baseline_category=baseline_category.lower().strip(),
            created_by='ai',
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        session.add(mapping)

    session.commit()
    logger.info("✅ Mappings saved successfully!")


def generate_report(mappings: Dict[str, str]):
    """Generate summary report of the groupings.

    Args:
        mappings: Dictionary of epic_summary -> baseline_category
    """
    # Count epics per category
    category_counts = Counter(mappings.values())

    print("\n" + "=" * 80)
    print("EPIC GROUPING ANALYSIS SUMMARY")
    print("=" * 80)
    print(f"Total epic names analyzed: {len(mappings)}")
    print(f"Total canonical categories created: {len(category_counts)}")
    print()

    print("-" * 80)
    print("CATEGORIES BY SIZE")
    print("-" * 80)
    print(f"{'Category':<40} {'Epic Count':<15}")
    print("-" * 80)

    for category, count in category_counts.most_common():
        print(f"{category:<40} {count:<15}")

    print()
    print("-" * 80)
    print("SAMPLE MAPPINGS (First 20)")
    print("-" * 80)

    for i, (epic, category) in enumerate(sorted(mappings.items())[:20]):
        print(f"{epic:<50} → {category}")

    if len(mappings) > 20:
        print(f"\n... and {len(mappings) - 20} more mappings")

    print("=" * 80)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Analyze epic names and create AI-powered groupings')
    parser.add_argument('--dry-run', action='store_true', help='Preview without saving to database')
    args = parser.parse_args()

    logger.info("Starting AI-powered epic grouping analysis...")

    # Create LLM
    llm = create_llm()
    if not llm:
        logger.error("Failed to create LLM instance")
        return 1

    # Get database session
    session = get_session()

    try:
        # Fetch unique epic names
        epic_names = fetch_unique_epic_names(session)

        if not epic_names:
            logger.warning("No epic names found in database")
            return 1

        # Analyze with AI
        mappings = analyze_with_ai(llm, epic_names)

        # Generate report
        generate_report(mappings)

        # Save to database
        save_mappings(session, mappings, dry_run=args.dry_run)

        if args.dry_run:
            print("\n⚠️  DRY RUN MODE: No changes were saved to database")
        else:
            print("\n✅ Analysis complete! Mappings saved to epic_baseline_mappings table")
            print("\nNext steps:")
            print("1. Review the mappings in the database")
            print("2. Run 'python scripts/generate_epic_baselines.py' to regenerate baselines")
            print("3. The Epic Baselines tab should now show grouped categories")

        return 0

    except Exception as e:
        logger.error(f"Error during analysis: {e}", exc_info=True)
        session.rollback()
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
