"""AI-powered epic baseline grouping service.

This service groups similar epics into canonical baseline categories for forecasting.
It uses a hybrid approach: cache-first with AI fallback for unmapped epics.
"""

import logging
from typing import Optional, Dict, Set
from datetime import datetime, timezone
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from config.settings import Settings
from sqlalchemy.orm import Session
from src.models.epic_baseline_mapping import EpicBaselineMapping

logger = logging.getLogger(__name__)


class EpicBaselineGrouper:
    """Service for grouping epics into canonical baseline categories."""

    def __init__(self, db_session: Session):
        """Initialize the grouper with a database session.

        Args:
            db_session: SQLAlchemy session for database operations
        """
        self.db_session = db_session
        self.llm = self._create_llm()
        self._cache: Dict[str, str] = {}
        self._existing_categories: Optional[Set[str]] = None

    def _create_llm(self):
        """Create LLM instance based on centralized settings."""
        ai_config = Settings.get_fresh_ai_config()

        if not ai_config:
            logger.warning(
                "AI configuration not available - EpicBaselineGrouper will use database cache only"
            )
            return None

        logger.info(
            f"Creating LLM for baseline grouping with provider={ai_config.provider}, model={ai_config.model}"
        )

        if ai_config.provider == "openai":
            return ChatOpenAI(
                model=ai_config.model,
                temperature=0.1,  # Low temperature for consistent grouping
                max_tokens=50,  # Only need category name
                api_key=ai_config.api_key,
            )
        elif ai_config.provider == "anthropic":
            return ChatAnthropic(
                model=ai_config.model,
                anthropic_api_key=ai_config.api_key,
                temperature=0.1,
                max_tokens=50,
            )
        elif ai_config.provider == "google":
            return ChatGoogleGenerativeAI(
                model=ai_config.model,
                google_api_key=ai_config.api_key,
                temperature=0.1,
                max_tokens=50,
            )
        else:
            logger.error(f"Unsupported AI provider: {ai_config.provider}")
            return None

    def _get_existing_categories(self) -> Set[str]:
        """Get set of existing baseline categories from database."""
        if self._existing_categories is None:
            results = (
                self.db_session.query(EpicBaselineMapping.baseline_category)
                .distinct()
                .all()
            )
            self._existing_categories = {r.baseline_category for r in results}
            logger.debug(f"Loaded {len(self._existing_categories)} existing categories from database")

        return self._existing_categories

    def group_epic(self, epic_summary: str) -> str:
        """Group an epic into its canonical baseline category.

        Args:
            epic_summary: Epic title/summary from Jira or Tempo

        Returns:
            Canonical baseline category name (lowercase, normalized)
        """
        if not epic_summary or epic_summary.strip() == "":
            return "uncategorized"

        # Normalize for lookup
        epic_summary_normalized = epic_summary.strip()

        # Check local cache first
        if epic_summary_normalized in self._cache:
            logger.debug(f"Using cached category for '{epic_summary_normalized}'")
            return self._cache[epic_summary_normalized]

        # Check database for existing mapping
        existing_mapping = (
            self.db_session.query(EpicBaselineMapping)
            .filter_by(epic_summary=epic_summary_normalized)
            .first()
        )

        if existing_mapping:
            logger.debug(
                f"Found existing baseline mapping for '{epic_summary_normalized}': {existing_mapping.baseline_category}"
            )
            self._cache[epic_summary_normalized] = existing_mapping.baseline_category
            return existing_mapping.baseline_category

        # Use AI to group (with context of existing categories)
        logger.info(f"No mapping found for '{epic_summary_normalized}', using AI to classify")
        category = self._group_with_ai(epic_summary_normalized)

        # Save to database
        self._save_mapping(epic_summary_normalized, category)

        # Cache result
        self._cache[epic_summary_normalized] = category

        return category

    def _group_with_ai(self, epic_summary: str) -> str:
        """Use AI to group an epic into a baseline category.

        Args:
            epic_summary: Epic title/summary

        Returns:
            Canonical baseline category name
        """
        if not self.llm:
            logger.warning("LLM not available, defaulting to 'uncategorized'")
            return "uncategorized"

        # Get existing categories for context
        existing_categories = self._get_existing_categories()

        if existing_categories:
            categories_list = "\n".join([f"- {cat}" for cat in sorted(existing_categories)])
            system_prompt = f"""You are an expert at grouping e-commerce project epics into canonical categories.

Existing baseline categories in the system:
{categories_list}

Your task is to group the following epic into ONE of the existing categories above, OR create a NEW category if none fit well.

Rules:
1. Prefer using an existing category if it's a good fit
2. Only create a new category if the epic is significantly different from existing ones
3. Return ONLY the category name (lowercase, concise, descriptive)
4. No explanation, just the category name
5. For e-commerce projects, common categories include:
   - product details, product listings, cart, checkout, search
   - header, footer, navigation, content sections
   - design system, ux research, environment setup
   - 3rd party apps, launch support, project oversight

Examples:
- "Product Detail Page" → "product details"
- "Shopping Cart Feature" → "cart"
- "Custom Header Design" → "header"
- "Payment Gateway Integration" → "3rd party apps"
"""
        else:
            system_prompt = """You are an expert at categorizing e-commerce project epics.

Your task is to create a canonical category name for the following epic.

Rules:
1. Return ONLY the category name (lowercase, concise, descriptive)
2. No explanation, just the category name
3. Use common e-commerce patterns:
   - product details, product listings, cart, checkout, search
   - header, footer, navigation, content sections
   - design system, ux research, environment setup
   - 3rd party apps, launch support, project oversight

Examples:
- "Product Detail Page" → "product details"
- "Shopping Cart Feature" → "cart"
- "Custom Header Design" → "header"
"""

        user_prompt = f"Epic: {epic_summary}"

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]

        try:
            response = self.llm.invoke(messages)
            category = response.content.strip().lower()

            # Validate category name (basic sanitization)
            category = category.replace('"', '').replace("'", '').strip()

            if not category or len(category) > 200:
                logger.warning(f"Invalid category from AI: '{category}', defaulting to 'uncategorized'")
                return "uncategorized"

            logger.info(f"AI grouped '{epic_summary}' → '{category}'")

            # Update existing categories cache
            if self._existing_categories is not None:
                self._existing_categories.add(category)

            return category

        except Exception as e:
            logger.error(f"Error during AI grouping: {e}")
            return "uncategorized"

    def _save_mapping(self, epic_summary: str, baseline_category: str):
        """Save epic-to-category mapping to database.

        Args:
            epic_summary: Epic title/summary
            baseline_category: Canonical category name
        """
        try:
            mapping = EpicBaselineMapping(
                epic_summary=epic_summary,
                baseline_category=baseline_category,
                created_by='ai',
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            self.db_session.add(mapping)
            self.db_session.commit()
            logger.debug(f"Saved mapping: '{epic_summary}' → '{baseline_category}'")
        except Exception as e:
            logger.error(f"Error saving mapping: {e}")
            self.db_session.rollback()
