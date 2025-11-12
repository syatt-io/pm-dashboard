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

    # Valid epic categories
    VALID_CATEGORIES = [
        "FE Dev",
        "BE Dev",
        "Project Oversight",
        "Design",
        "UX",
        "Data",
        "Infrastructure",
        "QA",
        "Uncategorized"
    ]

    def __init__(self, db_session: Session):
        """Initialize the categorizer with a database session.

        Args:
            db_session: SQLAlchemy session for database operations
        """
        self.db_session = db_session
        self.llm = self._create_llm()
        self._cache: Dict[str, str] = {}

    def _create_llm(self):
        """Create LLM instance based on centralized settings."""
        ai_config = Settings.get_fresh_ai_config()

        if not ai_config:
            logger.warning("AI configuration not available - EpicCategorizer will not be functional")
            return None

        logger.info(f"Creating LLM for categorization with provider={ai_config.provider}, model={ai_config.model}")

        if ai_config.provider == "openai":
            return ChatOpenAI(
                model=ai_config.model,
                temperature=0.1,  # Low temperature for consistent categorization
                max_tokens=50,  # Only need category name
                api_key=ai_config.api_key
            )
        elif ai_config.provider == "anthropic":
            return ChatAnthropic(
                model=ai_config.model,
                anthropic_api_key=ai_config.api_key,
                temperature=0.1,
                max_tokens=50
            )
        elif ai_config.provider == "google":
            return ChatGoogleGenerativeAI(
                model=ai_config.model,
                google_api_key=ai_config.api_key,
                temperature=0.1,
                max_tokens=50
            )
        else:
            logger.error(f"Unsupported AI provider: {ai_config.provider}")
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
        existing_mapping = self.db_session.query(EpicCategoryMapping).filter_by(
            epic_key=epic_key
        ).first()

        if existing_mapping:
            logger.debug(f"Found existing category mapping for {epic_key}: {existing_mapping.category}")
            self._cache[epic_key] = existing_mapping.category
            return existing_mapping.category

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

        system_prompt = f"""You are an expert at categorizing software development epics.

Categorize the following epic into ONE of these categories:
- FE Dev: Frontend development (React, Vue, Angular, UI components, client-side features)
- BE Dev: Backend development (APIs, databases, server-side logic, integrations)
- Project Oversight: Project management (planning, coordination, stakeholder management)
- Design: Visual design (UI design, graphics, branding, design systems)
- UX: User experience (user research, usability testing, UX design, customer interviews)
- Data: Data science, analytics, reporting, data pipelines
- Infrastructure: DevOps, hosting, CI/CD, deployment, monitoring
- QA: Testing, quality assurance, test automation
- Uncategorized: If none of the above fit

Rules:
1. Return ONLY the category name exactly as shown above (case-sensitive)
2. Choose the most specific category that fits
3. If multiple categories could apply, choose the primary focus
4. Do NOT explain your reasoning, just return the category name

Example responses:
"FE Dev"
"BE Dev"
"Project Oversight"
"""

        user_prompt = f"Epic: {epic_summary}"

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]

            response = self.llm.invoke(messages)
            category = response.content.strip()

            # Validate category
            if category in self.VALID_CATEGORIES:
                logger.info(f"AI categorized epic as: {category}")
                return category
            else:
                logger.warning(f"AI returned invalid category '{category}', defaulting to 'Uncategorized'")
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
            existing = self.db_session.query(EpicCategoryMapping).filter_by(
                epic_key=epic_key
            ).first()

            if existing:
                # Update existing mapping
                existing.category = category
                logger.debug(f"Updated category mapping for {epic_key} to {category}")
            else:
                # Create new mapping
                mapping = EpicCategoryMapping(
                    epic_key=epic_key,
                    category=category
                )
                self.db_session.add(mapping)
                logger.debug(f"Created category mapping for {epic_key}: {category}")

            self.db_session.commit()

        except Exception as e:
            logger.error(f"Error saving category mapping for {epic_key}: {e}", exc_info=True)
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
