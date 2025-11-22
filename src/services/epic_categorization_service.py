"""AI-powered service to automatically categorize epics."""

import json
import logging
from typing import Dict, List, Any, Optional
from config.settings import settings
from src.utils.database import get_session
from src.models.epic_category import EpicCategory
from src.models.epic_category_mapping import EpicCategoryMapping
from src.models.epic_hours import EpicHours
from sqlalchemy import func

logger = logging.getLogger(__name__)


class EpicCategorizationService:
    """
    AI-powered service to automatically categorize epics based on their
    summaries and descriptions using existing categorization examples as training data.
    """

    def __init__(self):
        """Initialize the service with configured AI provider."""
        if not settings.ai:
            raise ValueError(
                "AI configuration not found. Please configure AI_PROVIDER and API key in environment."
            )

        self.provider = settings.ai.provider
        self.model = settings.ai.model
        self.api_key = settings.ai.api_key

        # Initialize provider-specific client
        if self.provider == "anthropic":
            from anthropic import Anthropic

            self.client = Anthropic(api_key=self.api_key)
        elif self.provider == "openai":
            from openai import OpenAI

            self.client = OpenAI(api_key=self.api_key)
        else:
            raise ValueError(
                f"Unsupported AI provider for categorization: {self.provider}. "
                f"Supported providers: anthropic, openai"
            )

    def categorize_epics(
        self,
        epics: List[Dict[str, Any]],
        project_key: str = None,
    ) -> Dict[str, Optional[str]]:
        """
        Use AI to automatically categorize epics based on their summaries and descriptions.

        Args:
            epics: List of epics to categorize, each with:
                - epic_key: Jira epic key (e.g., "SUBS-123")
                - epic_summary: Short summary of the epic
                - description: (optional) Full description text
            project_key: Optional project key for additional context

        Returns:
            Dictionary mapping epic_key to category name:
            {
                "SUBS-123": "FE Dev",
                "SUBS-124": "Backend",
                "SUBS-125": None  # No good match found
            }
        """
        if not epics:
            logger.warning("No epics provided for categorization")
            return {}

        logger.info(f"Categorizing {len(epics)} epics")

        try:
            # Get available categories and training examples
            session = get_session()
            available_categories = self._get_available_categories(session)
            training_examples = self._get_training_examples(session, limit=50)

            if not available_categories:
                logger.warning("No epic categories defined - skipping categorization")
                return {epic["epic_key"]: None for epic in epics}

            # Build AI prompt
            prompt = self._build_categorization_prompt(
                epics, available_categories, training_examples, project_key
            )

            # Call AI provider
            if self.provider == "anthropic":
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=2000,
                    temperature=0.2,  # Low temperature for consistent categorization
                    messages=[{"role": "user", "content": prompt}],
                )
                response_text = response.content[0].text.strip()
            elif self.provider == "openai":
                # Build request parameters
                params = {
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                }

                # Only add temperature for non-reasoning models (gpt-4, gpt-3.5, etc.)
                # Reasoning models (o1, o3, gpt-5) don't support temperature
                if not self.model.startswith(("o1", "o3", "gpt-5")):
                    params["temperature"] = 0.2

                # Use max_completion_tokens (newer models) or fallback to max_tokens
                try:
                    params["max_completion_tokens"] = 2000
                    response = self.client.chat.completions.create(**params)
                except Exception as e:
                    if "max_completion_tokens" in str(e):
                        # Older models use max_tokens
                        del params["max_completion_tokens"]
                        params["max_tokens"] = 2000
                        response = self.client.chat.completions.create(**params)
                    else:
                        raise
                response_text = response.choices[0].message.content.strip()
            else:
                raise ValueError(f"Unsupported provider: {self.provider}")

            # Extract JSON from response
            if response_text.startswith("```json"):
                response_text = response_text[7:].strip()
                if response_text.endswith("```"):
                    response_text = response_text[:-3].strip()
            elif response_text.startswith("```"):
                response_text = response_text[3:].strip()
                if response_text.endswith("```"):
                    response_text = response_text[:-3].strip()

            # Parse JSON
            categorizations = json.loads(response_text)

            # Validate categories exist
            valid_categories = {cat["name"] for cat in available_categories}
            result = {}
            for epic_key, category in categorizations.items():
                if category is None or category in valid_categories:
                    result[epic_key] = category
                else:
                    logger.warning(
                        f"AI suggested invalid category '{category}' for {epic_key}, "
                        f"leaving uncategorized"
                    )
                    result[epic_key] = None

            logger.info(
                f"Categorized {len([c for c in result.values() if c])} of {len(epics)} epics"
            )
            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI categorization response: {e}")
            logger.error(f"Response text: {response_text[:500]}...")
            # Return all uncategorized on error
            return {epic["epic_key"]: None for epic in epics}

        except Exception as e:
            logger.error(f"Error during AI categorization: {e}", exc_info=True)
            # Return all uncategorized on error
            return {epic["epic_key"]: None for epic in epics}

    def _get_available_categories(self, session) -> List[Dict[str, str]]:
        """Fetch available epic categories from database."""
        categories = (
            session.query(EpicCategory).order_by(EpicCategory.display_order).all()
        )
        return [{"name": cat.name} for cat in categories]

    def _get_training_examples(self, session, limit: int = 50) -> List[Dict[str, str]]:
        """
        Fetch existing epic categorizations to use as training examples.

        Joins with epic_budgets (preferred) or epic_hours to get epic summaries.
        epic_budgets is preferred because it's populated immediately on import,
        while epic_hours only exists when Tempo hours are tracked.
        Returns most recent mappings to reflect current categorization patterns.
        """
        from src.models.epic_budget import EpicBudget
        from sqlalchemy import func

        # Try to get summaries from epic_budgets first (populated on import),
        # fall back to epic_hours if needed (only exists with Tempo tracking)
        examples = (
            session.query(
                EpicCategoryMapping.epic_key,
                EpicCategoryMapping.category,
                func.coalesce(EpicBudget.epic_summary, EpicHours.epic_summary).label(
                    "epic_summary"
                ),
            )
            .outerjoin(
                EpicBudget,
                EpicCategoryMapping.epic_key == EpicBudget.epic_key,
            )
            .outerjoin(
                EpicHours,
                EpicCategoryMapping.epic_key == EpicHours.epic_key,
            )
            .distinct(EpicCategoryMapping.epic_key)
            .order_by(
                EpicCategoryMapping.epic_key,
                EpicCategoryMapping.updated_at.desc(),
            )
            .limit(limit)
            .all()
        )

        return [
            {
                "epic_key": epic_key,
                "epic_summary": epic_summary or "No summary",
                "category": category,
            }
            for epic_key, category, epic_summary in examples
            if epic_summary  # Only include examples with summaries
        ]

    def _build_categorization_prompt(
        self,
        epics: List[Dict],
        available_categories: List[Dict],
        training_examples: List[Dict],
        project_key: Optional[str] = None,
    ) -> str:
        """Build the AI prompt for epic categorization."""

        project_context = f' in project "{project_key}"' if project_key else ""

        # Build categories list
        categories_text = "AVAILABLE CATEGORIES:\n"
        for i, cat in enumerate(available_categories, 1):
            categories_text += f'{i}. "{cat["name"]}"\n'

        # Build training examples
        training_text = ""
        if training_examples:
            training_text = "\n\nEXAMPLES OF PREVIOUSLY CATEGORIZED EPICS:\n"
            for ex in training_examples[:20]:  # Limit to 20 examples in prompt
                training_text += f'- "{ex["epic_summary"]}" → "{ex["category"]}"\n'
            training_text += (
                "\nLearn from these examples to understand the categorization pattern."
            )

        # Build epics to categorize
        epics_text = "\n\nEPICS TO CATEGORIZE:\n"
        for i, epic in enumerate(epics, 1):
            summary = epic.get("epic_summary", "No summary")
            description = epic.get("description", "")
            desc_preview = (
                f" - Description: {description[:150]}..." if description else ""
            )
            epics_text += f'{i}. {epic["epic_key"]}: "{summary}"{desc_preview}\n'

        prompt = f"""You are categorizing Jira epics{project_context}.

{categories_text}
{training_text}
{epics_text}

TASK:
For each epic, assign the most appropriate category from the available categories list.
Consider the epic summary and description (if provided) to determine the best match.

RULES:
1. You MUST choose from the available categories only
2. If no category is a good fit, return null for that epic
3. Use the training examples to understand categorization patterns
4. Be conservative - it's better to leave uncategorized (null) than to miscategorize

Return ONLY valid JSON (no additional text) in this exact format:
{{
  "SUBS-123": "FE Dev",
  "SUBS-124": "Backend",
  "SUBS-125": null,
  "SUBS-126": "Project Oversight"
}}

IMPORTANT:
- Epic keys must exactly match the keys provided above
- Category names must exactly match available categories (case-sensitive)
- Use null (not "null", "None", or empty string) for uncategorized epics
- Focus on the epic's primary purpose to determine category"""

        return prompt
