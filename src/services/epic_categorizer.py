"""AI-powered epic categorization service for historical data import."""

import logging
from typing import Optional, Dict
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from config.settings import Settings
from sqlalchemy.orm import Session
from src.models.epic_category_mapping import EpicCategoryMapping

logger = logging.getLogger(__name__)


class EpicCategorizer:
    """Service for categorizing epics using AI."""

    def __init__(self, db_session: Session):
        """Initialize the categorizer with a database session.

        Args:
            db_session: SQLAlchemy session for database operations
        """
        self.db_session = db_session
        self.llm = self._create_llm()
        self._cache: Dict[str, str] = {}
        self._valid_categories: Optional[list[str]] = None

    def _load_valid_categories(self) -> list[str]:
        """Load valid categories from database.

        Returns:
            List of category names plus "Uncategorized"
        """
        if self._valid_categories is not None:
            return self._valid_categories

        try:
            from src.models.epic_category import EpicCategory

            categories = (
                self.db_session.query(EpicCategory)
                .order_by(EpicCategory.display_order)
                .all()
            )

            # Get category names from database
            category_names = [cat.name for cat in categories]

            # Always add "Uncategorized" as fallback
            if "Uncategorized" not in category_names:
                category_names.append("Uncategorized")

            self._valid_categories = category_names
            logger.info(f"Loaded {len(category_names)} valid categories from database: {category_names}")

            return category_names

        except Exception as e:
            logger.error(f"Error loading categories from database: {e}", exc_info=True)
            # Fallback to basic list if database load fails
            return ["UI Dev", "Project Oversight", "Uncategorized"]

    def _create_llm(self):
        """Create LLM instance based on centralized settings."""
        ai_config = Settings.get_fresh_ai_config()

        if not ai_config:
            logger.warning(
                "AI configuration not available - EpicCategorizer will not be functional"
            )
            return None

        logger.info(
            f"Creating LLM for categorization with provider={ai_config.provider}, model={ai_config.model}"
        )

        if ai_config.provider == "openai":
            return ChatOpenAI(
                model=ai_config.model,
                temperature=0.1,  # Low temperature for consistent categorization
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

    def _fuzzy_match_category(self, epic_summary: str) -> Optional[str]:
        """Try to match epic summary to a category using fuzzy matching.

        Args:
            epic_summary: Epic title/summary

        Returns:
            Category name if match found, None otherwise
        """
        valid_categories = self._load_valid_categories()
        summary_lower = epic_summary.lower().strip()

        # Exact match (case-insensitive)
        for category in valid_categories:
            if category.lower() == summary_lower:
                logger.info(f"Fuzzy matched '{epic_summary}' to '{category}' (exact match)")
                return category

        # Check if summary contains full category name
        for category in valid_categories:
            if category.lower() in summary_lower:
                logger.info(f"Fuzzy matched '{epic_summary}' to '{category}' (contains match)")
                return category

        # No fuzzy match found
        return None

    def categorize_epic(self, epic_key: str, epic_summary: str) -> str:
        """Categorize an epic based on its summary.

        Args:
            epic_key: Jira epic key (e.g., "RNWL-123")
            epic_summary: Epic title/summary from Jira

        Returns:
            Category name (one of VALID_CATEGORIES)
        """
        # Check local cache first
        if epic_key in self._cache:
            logger.debug(f"Using cached category for {epic_key}")
            return self._cache[epic_key]

        # Check database for existing mapping
        existing_mapping = (
            self.db_session.query(EpicCategoryMapping)
            .filter_by(epic_key=epic_key)
            .first()
        )

        if existing_mapping:
            logger.debug(
                f"Found existing category mapping for {epic_key}: {existing_mapping.category}"
            )
            self._cache[epic_key] = existing_mapping.category
            return existing_mapping.category

        # Try fuzzy matching first (faster and cheaper than AI)
        fuzzy_category = self._fuzzy_match_category(epic_summary)
        if fuzzy_category:
            logger.info(f"Fuzzy matched {epic_key} to {fuzzy_category}, skipping AI")
            self._save_mapping(epic_key, fuzzy_category)
            self._cache[epic_key] = fuzzy_category
            return fuzzy_category

        # Use AI to categorize
        category = self._categorize_with_ai(epic_summary)

        # Save to database
        self._save_mapping(epic_key, category)

        # Cache result
        self._cache[epic_key] = category

        return category

    def _categorize_with_ai(self, epic_summary: str) -> str:
        """Use AI to categorize an epic.

        Args:
            epic_summary: Epic title/summary

        Returns:
            Category name
        """
        if not self.llm:
            logger.warning("LLM not available, defaulting to 'Uncategorized'")
            return "Uncategorized"

        valid_categories = self._load_valid_categories()

        # Build category descriptions dynamically with keyword hints
        category_descriptions = {
            "Project Oversight": "Project management, planning, coordination, stakeholder management, meetings, status updates, UAT, testing, QA, environment setup, infrastructure setup, DevOps",
            "UX": "User experience research, usability testing, UX design, user flows, wireframes, customer interviews",
            "Design": "Visual design, UI design, graphics, branding, design systems, mockups, style guides",
            "UI Dev": "Frontend development, user interface implementation, pages, components, navigation, headers, footers, forms, buttons, modals. DEFAULT choice if epic involves user-facing work and category is unclear.",
            "Customizations": "Client-specific features, custom functionality, tailored solutions, special requirements, custom purchasing flows, scholarships, donations, configurators, custom forms, bulk tools, custom uploaders",
            "Integrations": "External system integrations, API connections, third-party services, middleware, import/export systems, sync operations, order sync, product imports, data integrations (NOT marketplace apps)",
            "Migrations": "Data migrations, platform migrations, system transitions, legacy system updates, product migrations, moving between systems",
            "3rd Party Apps": "Shopify apps, marketplace plugins, app store integrations, pre-built third-party extensions",
            "SEO & Analytics": "Search engine optimization, analytics implementation, tracking, performance monitoring",
            "POS": "Point of sale systems, retail solutions, in-store technology (NOT scholarship systems with POS in name)",
            "Launch Support": "Go-live activities, production support, launch coordination, post-launch fixes",
        }

        # Build prompt with categories from database
        categories_list = "\n".join([
            f"- {cat}: {category_descriptions.get(cat, 'General category')}"
            for cat in valid_categories if cat != "Uncategorized"
        ])

        system_prompt = f"""You are an expert at categorizing software development epics for e-commerce and web development projects.

Categorize the following epic into ONE of these categories:
{categories_list}
- Uncategorized: ONLY if none of the above fit and you are uncertain

**CRITICAL**: Your response MUST be ONLY the category name, nothing else. No explanations, no markdown, no reasoning.

**CATEGORIZATION STRATEGY (apply in this order)**:

1. **Check for OBVIOUS KEYWORDS first**:
   - UAT, testing, QA, environment setup, infrastructure → "Project Oversight"
   - Import, export, sync, middleware, data integration → "Integrations"
   - Migration, moving between systems → "Migrations"
   - Shopify app, marketplace plugin → "3rd Party Apps"
   - SEO, analytics, tracking → "SEO & Analytics"

2. **Check if it's a STANDARD E-COMMERCE UI COMPONENT**:
   Standard UI patterns that should be "UI Dev":
   - Headers, footers, navigation, menus
   - Product listings (PLP), product details (PDP), collections
   - Cart, mini-cart, checkout flow
   - Search, filters, sorting
   - Account pages, login, registration
   - Homepage sections, landing pages
   - Forms (standard contact, newsletter)

   If it matches these → "UI Dev"

3. **Check if it's CUSTOM BUSINESS LOGIC**:
   If it's a functional deliverable that is NOT a standard e-commerce pattern:
   - Custom purchasing flows (academic purchasing, group orders)
   - Custom business features (scholarships, donations, memberships)
   - Custom configurators or builders
   - Custom bulk tools or uploaders
   - Client-specific workflows

   If it's unique business logic → "Customizations"

4. **Last resort**: If still unclear and user-facing → "UI Dev"

**EXAMPLES**:
- "UAT | PLP" → "Project Oversight" (testing keyword)
- "Environment Setup" → "Project Oversight" (infrastructure keyword)
- "Import products from eagle" → "Integrations" (import keyword)
- "Order Sync" → "Integrations" (sync keyword)
- "Product Migration" → "Migrations" (migration keyword)
- "Product Listings" → "UI Dev" (standard e-commerce UI)
- "Cart" → "UI Dev" (standard e-commerce UI)
- "Header" → "UI Dev" (standard e-commerce UI)
- "Scholarships" → "Customizations" (unique business logic)
- "Academic Purchasing Journey" → "Customizations" (unique business logic)
- "Configurator" → "Customizations" (unique business logic)
- "Bulk Image Uploader" → "Customizations" (unique business tool)

Example responses:
"UI Dev"
"Project Oversight"
"Customizations"
"""

        user_prompt = f"Epic: {epic_summary}"

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]

            response = self.llm.invoke(messages)
            raw_response = response.content.strip()

            # Try to extract category name from response
            # AI might return verbose response like "**UI Dev**\n\nReasoning..."
            # Extract just the category name
            category = raw_response

            # Remove markdown formatting
            category = category.replace("**", "").replace("*", "")

            # If response has multiple lines, take first line
            if "\n" in category:
                category = category.split("\n")[0].strip()

            # Remove common prefixes
            for prefix in ["Category: ", "Answer: ", "Result: "]:
                if category.startswith(prefix):
                    category = category[len(prefix):].strip()

            # Check if extracted category is valid
            if category in valid_categories:
                if category != raw_response:
                    logger.info(f"AI returned verbose response, extracted category: {category}")
                else:
                    logger.info(f"AI categorized epic as: {category}")
                return category

            # Try to find any valid category mentioned in the response
            for valid_cat in valid_categories:
                if valid_cat in raw_response:
                    logger.info(f"AI returned invalid format, but found valid category '{valid_cat}' in response")
                    return valid_cat

            # No valid category found
            logger.warning(
                f"AI returned invalid category '{raw_response[:100]}...', defaulting to 'Uncategorized'"
            )
            return "Uncategorized"

        except Exception as e:
            logger.error(f"Error categorizing epic with AI: {e}", exc_info=True)
            return "Uncategorized"

    def _save_mapping(self, epic_key: str, category: str):
        """Save epic category mapping to database.

        Args:
            epic_key: Jira epic key
            category: Category name
        """
        try:
            # Check if mapping already exists
            existing = (
                self.db_session.query(EpicCategoryMapping)
                .filter_by(epic_key=epic_key)
                .first()
            )

            if existing:
                # Update existing mapping
                existing.category = category
                logger.debug(f"Updated category mapping for {epic_key} to {category}")
            else:
                # Create new mapping
                mapping = EpicCategoryMapping(epic_key=epic_key, category=category)
                self.db_session.add(mapping)
                logger.debug(f"Created category mapping for {epic_key}: {category}")

            self.db_session.commit()

        except Exception as e:
            logger.error(
                f"Error saving category mapping for {epic_key}: {e}", exc_info=True
            )
            self.db_session.rollback()

    def categorize_batch(self, epics: list[tuple[str, str]]) -> Dict[str, str]:
        """Categorize multiple epics in batch.

        Args:
            epics: List of (epic_key, epic_summary) tuples

        Returns:
            Dictionary mapping epic_key to category
        """
        results = {}
        for epic_key, epic_summary in epics:
            category = self.categorize_epic(epic_key, epic_summary)
            results[epic_key] = category
        return results
