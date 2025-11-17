"""AI-powered service to map forecasted epics to existing project epics."""

import json
import logging
from typing import Dict, List, Any, Union
from config.settings import settings

logger = logging.getLogger(__name__)


class EpicMappingService:
    """
    AI-powered service to intelligently map forecasted epic allocations
    to existing project epics based on descriptions, context, and project characteristics.
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
                f"Unsupported AI provider for epic mapping: {self.provider}. "
                f"Supported providers: anthropic, openai"
            )

    def suggest_mappings(
        self,
        project_key: str,
        project_name: str,
        forecast_epics: List[Dict[str, Any]],
        existing_epics: List[Dict[str, Any]],
        project_characteristics: Dict[str, int] = None,
    ) -> Dict[str, Any]:
        """
        Use Claude AI to intelligently map forecasted epics to existing project epics.

        Args:
            project_key: Project key (e.g., "SUBS")
            project_name: Human-readable project name
            forecast_epics: List of forecasted epics from AI forecast
                [{"epic": "UI Development", "total_hours": 245, "reasoning": "..."}]
            existing_epics: List of existing epics in the project
                [{"epic_key": "SUBS-123", "epic_summary": "Frontend Product Pages", "estimated_hours": 0}]
            project_characteristics: Optional characteristics (be_integrations, custom_designs, etc.)

        Returns:
            {
                "mappings": [
                    {
                        "forecast_epic": "UI Development",
                        "forecast_hours": 245,
                        "matched_epics": [
                            {
                                "epic_key": "SUBS-123",
                                "epic_summary": "Frontend Product Pages",
                                "allocated_hours": 150,
                                "reasoning": "Primary UI work for product pages",
                                "confidence": 0.85
                            }
                        ]
                    }
                ],
                "unmapped_forecasts": ["Search Functionality"],
                "unmatched_existing": ["SUBS-125"],
                "overall_confidence": 0.82
            }
        """
        logger.info(
            f"Generating AI mappings for {len(forecast_epics)} forecasted epics "
            f"to {len(existing_epics)} existing epics in project {project_key}"
        )

        # Build AI prompt
        prompt = self._build_mapping_prompt(
            project_key,
            project_name,
            forecast_epics,
            existing_epics,
            project_characteristics,
        )

        try:
            # Call AI provider
            if self.provider == "anthropic":
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=4000,
                    temperature=0.3,  # Lower temperature for more consistent mapping
                    messages=[{"role": "user", "content": prompt}],
                )
                response_text = response.content[0].text.strip()
            elif self.provider == "openai":
                response = self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=4000,
                    temperature=0.3,  # Lower temperature for more consistent mapping
                    messages=[{"role": "user", "content": prompt}],
                )
                response_text = response.choices[0].message.content.strip()
            else:
                raise ValueError(f"Unsupported provider: {self.provider}")

            # Extract JSON from response

            # Remove markdown code fences if present
            if response_text.startswith("```json"):
                response_text = response_text[7:].strip()
                if response_text.endswith("```"):
                    response_text = response_text[:-3].strip()
            elif response_text.startswith("```"):
                response_text = response_text[3:].strip()
                if response_text.endswith("```"):
                    response_text = response_text[:-3].strip()

            # Parse JSON
            mappings = json.loads(response_text)

            logger.info(
                f"AI generated {len(mappings.get('mappings', []))} mappings with "
                f"overall confidence {mappings.get('overall_confidence', 0):.2f}"
            )

            return mappings

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI mapping response: {e}")
            logger.error(f"Response text: {response_text[:500]}...")
            # Return fallback empty mappings
            return {
                "mappings": [],
                "unmapped_forecasts": [e["epic"] for e in forecast_epics],
                "unmatched_existing": [e["epic_key"] for e in existing_epics],
                "overall_confidence": 0.0,
                "error": "Failed to parse AI response",
            }

        except Exception as e:
            logger.error(f"Error generating AI mappings: {e}", exc_info=True)
            return {
                "mappings": [],
                "unmapped_forecasts": [e["epic"] for e in forecast_epics],
                "unmatched_existing": [e["epic_key"] for e in existing_epics],
                "overall_confidence": 0.0,
                "error": str(e),
            }

    def _build_mapping_prompt(
        self,
        project_key: str,
        project_name: str,
        forecast_epics: List[Dict],
        existing_epics: List[Dict],
        project_characteristics: Dict = None,
    ) -> str:
        """Build the AI prompt for epic mapping."""

        characteristics_text = ""
        if project_characteristics:
            characteristics_text = "\nPROJECT CHARACTERISTICS:\n"
            for key, value in project_characteristics.items():
                # Convert snake_case to Title Case
                readable_key = key.replace("_", " ").title()
                characteristics_text += f"- {readable_key}: {value}/5\n"

        forecast_text = "\nFORECASTED EPICS (from AI analysis):\n"
        for i, epic in enumerate(forecast_epics, 1):
            forecast_text += (
                f'{i}. "{epic["epic"]}" ({epic["total_hours"]}h): '
                f'"{epic.get("reasoning", "No reasoning provided")}"\n'
            )

        existing_text = "\nEXISTING PROJECT EPICS (from Jira):\n"
        for i, epic in enumerate(existing_epics, 1):
            estimated = epic.get("estimated_hours", 0)
            status = " - SKIP THIS (already has estimate)" if estimated > 0 else ""
            existing_text += (
                f'{i}. {epic["epic_key"]}: "{epic.get("epic_summary", "No summary")}" '
                f"({estimated}h estimated{status})\n"
            )

        prompt = f"""You are mapping AI-forecasted epic allocations to existing Jira epics for project "{project_name}" ({project_key}).
{characteristics_text}
{forecast_text}
{existing_text}

TASK:
Map each forecasted epic to the most appropriate existing epic(s). Consider:
1. Epic descriptions and summaries
2. Forecast reasoning and project context
3. You can split forecasted hours across multiple epics if logical
4. CRITICAL: Skip epics that already have estimates > 0 (marked "SKIP THIS")
5. If no good match exists, include in "unmapped_forecasts" array

For each mapping, provide:
- Allocated hours per epic (must sum to forecast total)
- Reasoning for the match (1-2 sentences)
- Confidence score (0.0-1.0, where 1.0 = perfect match)

Return ONLY valid JSON (no additional text) in this exact format:
{{
  "mappings": [
    {{
      "forecast_epic": "UI Development",
      "forecast_hours": 245,
      "matched_epics": [
        {{
          "epic_key": "SUBS-123",
          "epic_summary": "Frontend Product Pages",
          "allocated_hours": 150,
          "reasoning": "Primary UI work matches product page requirements",
          "confidence": 0.85
        }},
        {{
          "epic_key": "SUBS-124",
          "epic_summary": "Shopping Cart UI",
          "allocated_hours": 95,
          "reasoning": "Cart interface is secondary UI component",
          "confidence": 0.75
        }}
      ]
    }}
  ],
  "unmapped_forecasts": ["Search Functionality"],
  "unmatched_existing": ["SUBS-130"],
  "overall_confidence": 0.78
}}

IMPORTANT:
- Ensure allocated_hours sum to forecast_hours for each mapping
- Be conservative with confidence scores (0.6-0.8 is normal, 0.9+ is exceptional match)
- Focus on semantic meaning, not just keyword matching
- Consider project characteristics when evaluating matches"""

        return prompt

    def generate_placeholder_epic_key(
        self, project_key: str, existing_placeholders: List[str]
    ) -> str:
        """
        Generate unique synthetic epic key for placeholder epics.

        Args:
            project_key: Project key (e.g., "SUBS")
            existing_placeholders: List of existing placeholder keys to avoid collisions

        Returns:
            Unique synthetic key like "SUBS-FORECAST-1"
        """
        counter = 1
        while True:
            candidate = f"{project_key}-FORECAST-{counter}"
            if candidate not in existing_placeholders:
                return candidate
            counter += 1

    def validate_mappings(
        self, mappings: List[Dict], forecast_epics: List[Dict]
    ) -> Dict[str, Any]:
        """
        Validate that AI-generated mappings are consistent and complete.

        Args:
            mappings: AI-generated mappings
            forecast_epics: Original forecast epics

        Returns:
            {
                "valid": True/False,
                "errors": ["Hour mismatch for 'UI Development'", ...],
                "warnings": ["Low confidence for 'Testing'", ...]
            }
        """
        errors = []
        warnings = []

        # Build forecast lookup
        forecast_lookup = {e["epic"]: e["total_hours"] for e in forecast_epics}

        for mapping in mappings:
            forecast_epic = mapping["forecast_epic"]
            forecast_hours = mapping["forecast_hours"]
            matched_epics = mapping.get("matched_epics", [])

            # Check forecast exists
            if forecast_epic not in forecast_lookup:
                errors.append(
                    f"Mapping references unknown forecast epic: {forecast_epic}"
                )
                continue

            # Check hour allocation sums correctly
            allocated_total = sum(e["allocated_hours"] for e in matched_epics)
            if abs(allocated_total - forecast_hours) > 0.01:
                errors.append(
                    f"Hour mismatch for '{forecast_epic}': "
                    f"forecast {forecast_hours}h but allocated {allocated_total}h"
                )

            # Check confidence scores
            for epic in matched_epics:
                confidence = epic.get("confidence", 0)
                if confidence < 0.5:
                    warnings.append(
                        f"Low confidence ({confidence:.2f}) for mapping "
                        f"'{forecast_epic}' → '{epic['epic_key']}'"
                    )

        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
