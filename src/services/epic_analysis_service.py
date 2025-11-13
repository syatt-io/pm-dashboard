"""Epic analysis service for AI-powered epic grouping.

This service analyzes epic names and creates canonical category groupings
using AI, storing the mappings in the epic_baseline_mappings table.
"""

import logging
import json
from typing import Dict, List
from datetime import datetime, timezone
from collections import Counter

from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from config.settings import Settings
from src.models import EpicHours, EpicBaselineMapping
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class EpicAnalysisService:
    """Service for analyzing and grouping epics with AI."""

    def __init__(self, session: Session):
        """Initialize analysis service.

        Args:
            session: SQLAlchemy database session
        """
        self.session = session
        self.llm = self._create_llm()

    def _create_llm(self):
        """Create LLM instance based on centralized settings."""
        ai_config = Settings.get_fresh_ai_config()

        if not ai_config:
            logger.error("AI configuration not available")
            return None

        logger.info(
            f"Creating LLM with provider={ai_config.provider}, model={ai_config.model}"
        )

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

    def fetch_unique_epic_names(self) -> List[str]:
        """Fetch all unique epic_summary values from epic_hours table."""
        logger.info("Fetching unique epic names from database...")

        results = (
            self.session.query(EpicHours.epic_summary)
            .filter(EpicHours.epic_summary.isnot(None))
            .filter(EpicHours.epic_summary != "")
            .distinct()
            .all()
        )

        epic_names = [r.epic_summary for r in results]
        logger.info(f"Found {len(epic_names)} unique epic names")

        return epic_names

    def analyze_with_ai(self, epic_names: List[str]) -> Dict[str, str]:
        """Use AI to analyze epic names and propose canonical groupings.

        Args:
            epic_names: List of unique epic names to analyze

        Returns:
            Dictionary mapping epic_name -> canonical_category
        """
        if not self.llm:
            logger.error("LLM not available, cannot analyze")
            return {}

        logger.info(
            f"Sending {len(epic_names)} epic names to AI for grouping analysis..."
        )

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
            HumanMessage(content=user_prompt),
        ]

        try:
            response = self.llm.invoke(messages)
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
            logger.info(
                f"AI proposed {len(set(mappings.values()))} canonical categories"
            )

            return mappings

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            logger.error(f"Response text: {response_text}")
            raise
        except Exception as e:
            logger.error(f"Error during AI analysis: {e}")
            raise

    def save_mappings(self, mappings: Dict[str, str]) -> int:
        """Save epic-to-category mappings to database.

        Args:
            mappings: Dictionary of epic_summary -> baseline_category

        Returns:
            Number of mappings saved
        """
        logger.info("Clearing existing mappings...")
        self.session.query(EpicBaselineMapping).delete()

        logger.info(f"Saving {len(mappings)} mappings to database...")

        for epic_summary, baseline_category in mappings.items():
            mapping = EpicBaselineMapping(
                epic_summary=epic_summary,
                baseline_category=baseline_category.lower().strip(),
                created_by="ai",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            self.session.add(mapping)

        self.session.commit()
        logger.info("Mappings saved successfully")

        return len(mappings)

    def generate_analysis_stats(self, mappings: Dict[str, str]) -> Dict[str, any]:
        """Generate statistics about the groupings.

        Args:
            mappings: Dictionary of epic_summary -> baseline_category

        Returns:
            Dict with analysis statistics
        """
        # Count epics per category
        category_counts = Counter(mappings.values())

        return {
            "total_epics": len(mappings),
            "total_categories": len(category_counts),
            "top_categories": dict(category_counts.most_common(10)),
            "categories_by_size": dict(category_counts),
        }

    def analyze_and_group_epics(self) -> Dict[str, any]:
        """Run full AI analysis and grouping workflow.

        Returns:
            Dict with analysis results and statistics
        """
        if not self.llm:
            logger.error("LLM not available - cannot run analysis")
            return {"success": False, "error": "AI configuration not available"}

        # Step 1: Fetch unique epic names
        epic_names = self.fetch_unique_epic_names()

        if not epic_names:
            logger.warning("No epic names found in database")
            return {"success": False, "error": "No epic names found"}

        # Step 2: Analyze with AI
        mappings = self.analyze_with_ai(epic_names)

        # Step 3: Save to database
        mappings_saved = self.save_mappings(mappings)

        # Step 4: Generate statistics
        stats = self.generate_analysis_stats(mappings)

        return {"success": True, "mappings_saved": mappings_saved, **stats}
