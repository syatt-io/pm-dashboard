"""
Intelligent forecasting service using AI to analyze historical projects.

This service uses LLMs to deeply analyze similar historical projects and make
intelligent predictions about team allocation, epic breakdown, and monthly distribution.
"""

import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

logger = logging.getLogger(__name__)


class IntelligentForecastingService:
    """AI-powered forecasting service that analyzes similar historical projects."""

    def __init__(self, session: Session):
        """Initialize intelligent forecasting service.

        Args:
            session: SQLAlchemy database session
        """
        self.session = session

    def generate_intelligent_forecast(
        self,
        project_characteristics: Dict[str, int],
        total_hours: float,
        estimated_months: int,
        teams_selected: List[str],
        start_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate intelligent forecast using AI analysis of similar historical projects.

        Args:
            project_characteristics: Dictionary with characteristics (1-5 scale):
                - be_integrations
                - custom_theme
                - custom_designs
                - ux_research
                - extensive_customizations
                - project_oversight
            total_hours: Total hours budget for the project
            estimated_months: Duration in months
            teams_selected: List of team names
            start_date: Optional start date (YYYY-MM-DD)

        Returns:
            Dictionary with:
                - teams: List of team allocations with monthly breakdowns
                - reasoning: AI's explanation of the predictions
                - similar_projects: List of historical projects used for analysis
                - confidence_score: AI's confidence in predictions (0-1)
        """
        logger.info("=" * 80)
        logger.info("INTELLIGENT FORECASTING REQUEST")
        logger.info("=" * 80)
        logger.info(f"Target characteristics: {project_characteristics}")
        logger.info(f"Total hours: {total_hours}, Duration: {estimated_months} months")
        logger.info(f"Teams selected: {teams_selected}")

        # Step 1: Find similar historical projects
        similar_projects = self._find_similar_projects(project_characteristics, limit=5)

        if not similar_projects:
            logger.warning(
                "No similar historical projects found. "
                "Cannot generate intelligent forecast without historical data."
            )
            return {
                "error": "No historical data available for intelligent analysis",
                "teams": [],
                "reasoning": "No similar historical projects found in database.",
                "similar_projects": [],
                "confidence_score": 0.0,
            }

        logger.info(f"\nFound {len(similar_projects)} similar projects:")
        for p in similar_projects:
            logger.info(
                f"  - {p['project_key']}: similarity={p['similarity_score']:.3f}, "
                f"chars={p['characteristics']}, total_hours={p['total_hours']}h"
            )

        # Step 2: Build rich historical context
        historical_context = self._build_historical_context(similar_projects)
        logger.info(
            f"\nBuilt historical context ({len(historical_context)} characters)"
        )

        # Step 3: Generate AI-powered forecast
        ai_forecast = self._generate_ai_forecast(
            project_characteristics=project_characteristics,
            total_hours=total_hours,
            estimated_months=estimated_months,
            teams_selected=teams_selected,
            historical_context=historical_context,
            start_date=start_date,
        )

        logger.info("=" * 80)
        return {
            **ai_forecast,
            "similar_projects": [
                {
                    "project_key": p["project_key"],
                    "characteristics": p["characteristics"],
                    "similarity_score": p["similarity_score"],
                }
                for p in similar_projects
            ],
        }

    def _find_similar_projects(
        self, target_characteristics: Dict[str, int], limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find historical projects with similar characteristics.

        Uses Euclidean distance in characteristic space to find most similar projects.

        Args:
            target_characteristics: Characteristics of new project (1-5 scale)
            limit: Maximum number of similar projects to return

        Returns:
            List of similar projects with their data, sorted by similarity
        """
        from src.models import (
            ProjectCharacteristics,
            ProjectForecastingConfig,
            EpicHours,
        )

        # Query all projects with forecasting configs
        query = (
            self.session.query(ProjectCharacteristics, ProjectForecastingConfig)
            .join(
                ProjectForecastingConfig,
                ProjectCharacteristics.project_key
                == ProjectForecastingConfig.project_key,
            )
            .filter(ProjectForecastingConfig.include_in_forecasting == True)
        )

        results = query.all()

        if not results:
            return []

        # Calculate similarity scores using Euclidean distance
        similar_projects = []
        for char, config in results:
            # Calculate distance in 6-dimensional characteristic space
            distance_squared = sum(
                [
                    (getattr(char, key, 3) - target_characteristics.get(key, 3)) ** 2
                    for key in [
                        "be_integrations",
                        "custom_theme",
                        "custom_designs",
                        "ux_research",
                        "extensive_customizations",
                        "project_oversight",
                    ]
                ]
            )

            # Convert distance to similarity score (0-1, where 1 = identical)
            # Max possible distance = sqrt(6 * 4^2) = sqrt(96) ≈ 9.8
            # Normalize to 0-1 range
            similarity_score = max(0, 1 - (distance_squared**0.5) / 9.8)

            # Get team hours for this project
            team_hours = (
                self.session.query(
                    EpicHours.team, func.sum(EpicHours.hours).label("total_hours")
                )
                .filter(
                    EpicHours.project_key == char.project_key,
                    EpicHours.month >= config.forecasting_start_date,
                    EpicHours.month <= config.forecasting_end_date,
                )
                .group_by(EpicHours.team)
                .all()
            )

            # Get monthly distribution for this project
            monthly_hours = (
                self.session.query(
                    EpicHours.month,
                    EpicHours.team,
                    func.sum(EpicHours.hours).label("hours"),
                )
                .filter(
                    EpicHours.project_key == char.project_key,
                    EpicHours.month >= config.forecasting_start_date,
                    EpicHours.month <= config.forecasting_end_date,
                )
                .group_by(EpicHours.month, EpicHours.team)
                .order_by(EpicHours.month)
                .all()
            )

            # Get epic breakdown for this project
            epic_breakdown = (
                self.session.query(
                    EpicHours.epic_category, func.sum(EpicHours.hours).label("hours")
                )
                .filter(
                    EpicHours.project_key == char.project_key,
                    EpicHours.month >= config.forecasting_start_date,
                    EpicHours.month <= config.forecasting_end_date,
                    EpicHours.epic_category.isnot(None),
                )
                .group_by(EpicHours.epic_category)
                .all()
            )

            total_project_hours = sum(hours for _, hours in team_hours)

            similar_projects.append(
                {
                    "project_key": char.project_key,
                    "similarity_score": round(similarity_score, 3),
                    "characteristics": {
                        "be_integrations": char.be_integrations,
                        "custom_theme": char.custom_theme,
                        "custom_designs": char.custom_designs,
                        "ux_research": char.ux_research,
                        "extensive_customizations": char.extensive_customizations,
                        "project_oversight": char.project_oversight,
                    },
                    "total_hours": round(total_project_hours, 2),
                    "team_hours": {team: round(hours, 2) for team, hours in team_hours},
                    "monthly_distribution": [
                        {"month": str(month), "team": team, "hours": round(hours, 2)}
                        for month, team, hours in monthly_hours
                    ],
                    "epic_breakdown": {
                        category: round(hours, 2) for category, hours in epic_breakdown
                    },
                    "date_range": {
                        "start": str(config.forecasting_start_date),
                        "end": str(config.forecasting_end_date),
                    },
                }
            )

        # Sort by similarity (most similar first) and return top N
        similar_projects.sort(key=lambda x: x["similarity_score"], reverse=True)
        return similar_projects[:limit]

    def _build_historical_context(self, similar_projects: List[Dict[str, Any]]) -> str:
        """
        Build rich historical context from similar projects for AI prompt.

        Args:
            similar_projects: List of similar historical projects with their data

        Returns:
            Formatted string with detailed historical context
        """
        context_lines = ["# Historical Projects for Analysis\n"]

        for i, project in enumerate(similar_projects, 1):
            context_lines.append(f"\n## Project {i}: {project['project_key']}")
            context_lines.append(
                f"**Similarity Score**: {project['similarity_score']} (1.0 = identical characteristics)"
            )
            context_lines.append(f"**Total Hours**: {project['total_hours']}h")
            context_lines.append(
                f"**Timeline**: {project['date_range']['start']} to {project['date_range']['end']}"
            )

            # Characteristics
            context_lines.append("\n**Characteristics** (1-5 scale):")
            for key, value in project["characteristics"].items():
                context_lines.append(f"  - {key}: {value}")

            # Team distribution
            context_lines.append("\n**Team Hours Distribution**:")
            team_total = sum(project["team_hours"].values())
            for team, hours in sorted(
                project["team_hours"].items(), key=lambda x: -x[1]
            ):
                percentage = (hours / team_total * 100) if team_total > 0 else 0
                context_lines.append(f"  - {team}: {hours}h ({percentage:.1f}%)")

            # Epic breakdown
            if project["epic_breakdown"]:
                context_lines.append("\n**Epic Categories**:")
                for category, hours in sorted(
                    project["epic_breakdown"].items(), key=lambda x: -x[1]
                )[:5]:
                    context_lines.append(f"  - {category}: {hours}h")

            # Monthly pattern (show first 3 months as example)
            if project["monthly_distribution"]:
                context_lines.append("\n**Monthly Pattern (first 3 months)**:")
                months_seen = set()
                for entry in project["monthly_distribution"]:
                    if len(months_seen) >= 3:
                        break
                    if entry["month"] not in months_seen:
                        months_seen.add(entry["month"])
                        month_entries = [
                            e
                            for e in project["monthly_distribution"]
                            if e["month"] == entry["month"]
                        ]
                        month_total = sum(e["hours"] for e in month_entries)
                        context_lines.append(
                            f"  Month {entry['month']}: {month_total}h"
                        )
                        for e in sorted(month_entries, key=lambda x: -x["hours"])[:3]:
                            context_lines.append(f"    - {e['team']}: {e['hours']}h")

        return "\n".join(context_lines)

    def _generate_ai_forecast(
        self,
        project_characteristics: Dict[str, int],
        total_hours: float,
        estimated_months: int,
        teams_selected: List[str],
        historical_context: str,
        start_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Use AI (LLM) to analyze historical context and generate intelligent forecast.

        Args:
            project_characteristics: New project characteristics
            total_hours: Total hours budget
            estimated_months: Duration
            teams_selected: Teams to allocate
            historical_context: Rich historical project data
            start_date: Optional start date

        Returns:
            Dictionary with AI-generated forecast and reasoning
        """
        from config.settings import settings

        # Build comprehensive AI prompt
        prompt = f"""You are an expert software project forecaster analyzing historical project data to predict team allocation and timeline for a new project.

# CHARACTERISTIC SCALE DEFINITIONS (CRITICAL - READ CAREFULLY!)

The 1-5 scale represents the INTENSITY of each requirement:

**1 = MINIMAL/ALMOST NONE**
- Expect 0-10% allocation compared to typical projects
- Example: BE Integrations 1/5 → Minimal backend work → 3-10% BE Devs (NOT 25-30%!)

**2 = BELOW AVERAGE**
- Expect 40-60% of typical allocation
- Example: Custom Designs 2/5 → Less design than usual → 4-8% Design

**3 = TYPICAL/STANDARD**
- Use historical baseline averages
- Example: Custom Theme 3/5 → Standard theme work → Use similar project patterns

**4 = ABOVE AVERAGE**
- Expect 140-180% of typical allocation
- Example: UX Research 4/5 → Heavy UX work → 8-12% UX

**5 = EXTENSIVE/MAXIMUM**
- Expect 200-300%+ of typical allocation
- Example: BE Integrations 5/5 → Complex backend → 35-50% BE Devs

# New Project Details

**Total Budget**: {total_hours} hours
**Duration**: {estimated_months} months
**Start Date**: {start_date or 'Not specified'}
**Teams Available**: {', '.join(teams_selected)}

**NEW PROJECT CHARACTERISTICS:**
- Backend Integrations: {project_characteristics.get('be_integrations', 3)}/5 → {"MINIMAL backend (expect 3-10% BE Devs)" if project_characteristics.get('be_integrations', 3) == 1 else "BELOW AVG backend (expect 10-20% BE Devs)" if project_characteristics.get('be_integrations', 3) == 2 else "TYPICAL backend (use baseline ~20-30% BE Devs)" if project_characteristics.get('be_integrations', 3) == 3 else "HEAVY backend (expect 30-40% BE Devs)" if project_characteristics.get('be_integrations', 3) == 4 else "EXTENSIVE backend (expect 40-50%+ BE Devs)"}
- Custom Theme: {project_characteristics.get('custom_theme', 3)}/5 → {"MINIMAL theme work" if project_characteristics.get('custom_theme', 3) <= 2 else "TYPICAL theme work" if project_characteristics.get('custom_theme', 3) == 3 else "HEAVY theme work"}
- Custom Designs: {project_characteristics.get('custom_designs', 3)}/5 → {"MINIMAL design needs" if project_characteristics.get('custom_designs', 3) <= 2 else "TYPICAL design needs" if project_characteristics.get('custom_designs', 3) == 3 else "EXTENSIVE design work"}
- UX Research: {project_characteristics.get('ux_research', 3)}/5 → {"MINIMAL UX" if project_characteristics.get('ux_research', 3) <= 2 else "TYPICAL UX" if project_characteristics.get('ux_research', 3) == 3 else "HEAVY UX work"}
- Extensive Customizations: {project_characteristics.get('extensive_customizations', 3)}/5
- Project Oversight: {project_characteristics.get('project_oversight', 3)}/5

{historical_context}

# CRITICAL ANALYSIS RULES (MUST FOLLOW!)

⚠️ **PRIMARY DIRECTIVE**: The new project's characteristics are MORE IMPORTANT than historical patterns!

1. **ADJUST FOR CHARACTERISTIC DIFFERENCES**:
   - If new project has be_integrations=1 but similar projects have 4-5:
     → REDUCE BE Dev allocation by 70-90% from their pattern (NOT just 20-30%!)
   - If new project has custom_designs=5 but similar projects have 2-3:
     → INCREASE Design allocation by 100-150% from their pattern

2. **MAGNITUDE OF ADJUSTMENTS**:
   - 1-point difference: Adjust by 20-40%
   - 2-point difference: Adjust by 50-80%
   - 3-point difference: Adjust by 80-120%
   - 4-point difference: Adjust by 150-200%

3. **DO NOT SIMPLY AVERAGE** historical projects:
   - Historical patterns are STARTING POINTS, not final answers
   - The specific characteristics of THIS project must drive your predictions
   - Example: If all historical projects allocated 30% to BE Devs but THIS project has be_integrations=1,
     you MUST predict ~5-10% BE Devs, NOT 25-30%!

4. **CONFIDENCE SCORING**:
   - High confidence (0.8-1.0): Similar projects with matching characteristics exist
   - Medium confidence (0.5-0.7): Some adjustment needed from historical patterns
   - Low confidence (0.2-0.4): Significant differences, major adjustments required

# EPIC CATEGORY ALLOCATION

In addition to team allocation, predict EPIC CATEGORY distribution based on project characteristics.

Common epic categories for web application projects:
- **Project Oversight** (10-20%): Planning, meetings, stakeholder management, project coordination
- **FE Dev** (30-45%): Frontend implementation, React/Vue components, UI development
- **BE Dev** (15-30%): Backend APIs, database design, business logic, server-side code
- **Design** (8-15%): Visual design, mockups, style guides, UI/UX design work
- **UX** (3-8%): User research, usability testing, user flows, personas
- **Infrastructure** (3-8%): DevOps, deployment pipelines, hosting setup, CI/CD
- **Authentication** (5-10%): Login systems, user management, permissions, security
- **Search** (3-8%): Search functionality, filters, indexing (if applicable)
- **Cart/Checkout** (5-12%): E-commerce features, payment integration (if applicable)

Scale epic categories based on characteristics:
- **High be_integrations (4-5)** → increase "BE Dev" epic to 25-35%
- **Low be_integrations (1-2)** → reduce "BE Dev" epic to 8-15%
- **High custom_designs (4-5)** → increase "Design" epic to 12-18%
- **Low custom_designs (1-2)** → reduce "Design" epic to 4-8%
- **High ux_research (4-5)** → increase "UX" epic to 8-12%
- **Low ux_research (1-2)** → reduce "UX" epic to 2-4%
- **High project_oversight (4-5)** → increase "Project Oversight" epic to 15-25%
- **Low project_oversight (1-2)** → reduce "Project Oversight" epic to 8-12%

# Your Task

Analyze the historical projects above, then predict the optimal team allocation AND epic category allocation for the NEW project.
REMEMBER: Adjust heavily based on the characteristic differences explained above!

Return your analysis as a JSON object with this exact structure:

{{
  "team_allocations": {{
    "BE Devs": {{
      "total_hours": <number>,
      "percentage": <number 0-100>,
      "reasoning": "<why this allocation>"
    }},
    "FE Devs": {{ ... }},
    "Design": {{ ... }},
    "UX": {{ ... }},
    "PMs": {{ ... }},
    "Data": {{ ... }}
  }},
  "epic_allocations": {{
    "Project Oversight": {{
      "total_hours": <number>,
      "percentage": <number 0-100>,
      "reasoning": "<why this allocation>"
    }},
    "FE Dev": {{ ... }},
    "BE Dev": {{ ... }},
    "Design": {{ ... }},
    "UX": {{ ... }},
    "Infrastructure": {{ ... }},
    "Authentication": {{ ... }}
    // Include other relevant epics based on project type
  }},
  "monthly_distribution_pattern": {{
    "ramp_up_percentage": <number 0-100>,
    "peak_percentage": <number 0-100>,
    "ramp_down_percentage": <number 0-100>,
    "reasoning": "<why this pattern>"
  }},
  "key_insights": [
    "<insight 1>",
    "<insight 2>",
    "<insight 3>"
  ],
  "confidence_score": <number 0-1>,
  "overall_reasoning": "<comprehensive explanation of your predictions>"
}}

IMPORTANT: Return ONLY the JSON object, no additional text before or after.
"""

        try:
            # Call LLM based on configured provider
            logger.info(
                f"\nCalling AI ({settings.ai.provider}) for forecast analysis..."
            )
            if settings.ai.provider == "openai":
                response_text = self._call_openai(prompt)
            elif settings.ai.provider == "anthropic":
                response_text = self._call_anthropic(prompt)
            else:
                # Fallback to OpenAI
                response_text = self._call_openai(prompt)

            logger.info(f"AI response received ({len(response_text)} characters)")
            logger.info(f"Raw AI response (first 500 chars): {response_text[:500]}...")

            # Parse AI response
            # Remove markdown code blocks if present
            response_text = response_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()

            ai_forecast = json.loads(response_text)

            logger.info(f"\nAI forecast parsed successfully:")
            logger.info(
                f"  Confidence score: {ai_forecast.get('confidence_score', 'N/A')}"
            )
            logger.info(
                f"  Overall reasoning: {ai_forecast.get('overall_reasoning', '')[:200]}..."
            )
            if "team_allocations" in ai_forecast:
                logger.info(f"  Team allocations:")
                for team, alloc in ai_forecast["team_allocations"].items():
                    logger.info(f"    - {team}: {alloc.get('percentage', 0):.1f}%")
            if "epic_allocations" in ai_forecast:
                logger.info(f"  Epic allocations:")
                for epic, alloc in ai_forecast["epic_allocations"].items():
                    logger.info(f"    - {epic}: {alloc.get('percentage', 0):.1f}%")

            # Validate and structure the forecast
            structured_forecast = self._structure_ai_forecast(
                ai_forecast, total_hours, estimated_months, teams_selected, start_date
            )

            return structured_forecast

        except Exception as e:
            logger.error(f"Error generating AI forecast: {e}", exc_info=True)
            return {
                "error": f"Failed to generate AI forecast: {str(e)}",
                "teams": [],
                "reasoning": "AI analysis failed. Please try again.",
                "confidence_score": 0.0,
            }

    def _call_openai(self, prompt: str) -> str:
        """Call OpenAI API."""
        from openai import OpenAI
        from config.settings import settings

        client = OpenAI(api_key=settings.ai.api_key)

        response = client.chat.completions.create(
            model=settings.ai.model or "gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert software project forecaster with deep knowledge of team dynamics and project planning.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.5,  # Balanced temperature for creative adjustments while maintaining structure
            max_tokens=2000,
        )

        return response.choices[0].message.content

    def _call_anthropic(self, prompt: str) -> str:
        """Call Anthropic (Claude) API."""
        from anthropic import Anthropic
        from config.settings import settings

        client = Anthropic(api_key=settings.ai.api_key)

        response = client.messages.create(
            model=settings.ai.model or "claude-3-5-sonnet-20241022",
            max_tokens=2000,
            temperature=0.5,  # Balanced temperature for creative adjustments while maintaining structure
            messages=[{"role": "user", "content": prompt}],
        )

        return response.content[0].text

    def _structure_ai_forecast(
        self,
        ai_forecast: Dict[str, Any],
        total_hours: float,
        estimated_months: int,
        teams_selected: List[str],
        start_date: Optional[str],
    ) -> Dict[str, Any]:
        """
        Structure AI forecast into format compatible with existing forecasting system.

        Args:
            ai_forecast: Raw AI forecast output
            total_hours: Total hours budget
            estimated_months: Duration
            teams_selected: Teams to allocate
            start_date: Optional start date

        Returns:
            Structured forecast with teams and monthly breakdowns
        """
        from src.services.forecasting_service import ForecastingService

        teams_data = []
        forecasting_service = ForecastingService(session=self.session)

        # Extract team allocations from AI forecast
        team_allocations = ai_forecast.get("team_allocations", {})
        monthly_pattern = ai_forecast.get("monthly_distribution_pattern", {})

        # Convert monthly pattern to lifecycle percentages
        lifecycle = {
            "ramp_up": monthly_pattern.get("ramp_up_percentage", 30.0),
            "busy": monthly_pattern.get("peak_percentage", 50.0),
            "ramp_down": monthly_pattern.get("ramp_down_percentage", 20.0),
        }

        for team in teams_selected:
            if team not in team_allocations:
                continue

            allocation = team_allocations[team]
            team_hours = allocation.get("total_hours", 0)

            # Distribute hours across months using forecasting service
            monthly_breakdown = forecasting_service._distribute_hours_by_month(
                team_hours, estimated_months, lifecycle, team, start_date
            )

            teams_data.append(
                {
                    "team": team,
                    "total_hours": round(team_hours, 2),
                    "percentage": round(allocation.get("percentage", 0), 2),
                    "monthly_breakdown": monthly_breakdown,
                    "reasoning": allocation.get("reasoning", ""),
                }
            )

        # Extract epic allocations from AI forecast
        epics_data = []
        epic_allocations = ai_forecast.get("epic_allocations", {})

        for epic_name, allocation in epic_allocations.items():
            epics_data.append(
                {
                    "epic": epic_name,
                    "total_hours": round(allocation.get("total_hours", 0), 2),
                    "percentage": round(allocation.get("percentage", 0), 2),
                    "reasoning": allocation.get("reasoning", ""),
                }
            )

        logger.info(f"\nFinal structured forecast:")
        for team_data in teams_data:
            logger.info(
                f"  - {team_data['team']}: {team_data['total_hours']}h ({team_data['percentage']:.1f}%)"
            )
        if epics_data:
            logger.info(f"\nEpic allocations:")
            for epic_data in epics_data:
                logger.info(
                    f"  - {epic_data['epic']}: {epic_data['total_hours']}h ({epic_data['percentage']:.1f}%)"
                )

        return {
            "teams": teams_data,
            "epics": epics_data,
            "reasoning": ai_forecast.get("overall_reasoning", ""),
            "key_insights": ai_forecast.get("key_insights", []),
            "confidence_score": ai_forecast.get("confidence_score", 0.5),
            "monthly_pattern": monthly_pattern,
            "total_hours": total_hours,
            "estimated_months": estimated_months,
        }
