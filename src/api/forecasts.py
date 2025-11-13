"""
API endpoints for epic forecasting.
"""

from flask import Blueprint, request, jsonify, make_response
from src.services.forecasting_service import ForecastingService
from src.services.intelligent_forecasting_service import IntelligentForecastingService
from src.models import EpicForecast
from src.utils.database import get_session
import logging
import csv
import io

logger = logging.getLogger(__name__)

forecasts_bp = Blueprint("forecasts", __name__, url_prefix="/api/forecasts")
forecasting_service = ForecastingService()


@forecasts_bp.route("/calculate", methods=["POST"])
def calculate_forecast():
    """
    Calculate a forecast based on project characteristics.

    Request body:
    {
        "be_integrations": bool,
        "custom_theme": bool,
        "custom_designs": bool,
        "ux_research": bool,
        "teams_selected": ["BE Devs", "FE Devs", ...],
        "estimated_months": int
    }
    """
    try:
        data = request.json

        # Validate required fields
        required_fields = [
            "be_integrations",
            "custom_theme",
            "custom_designs",
            "ux_research",
            "teams_selected",
            "estimated_months",
        ]
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400

        # Calculate forecast
        forecast_result = forecasting_service.calculate_forecast(
            be_integrations=data["be_integrations"],
            custom_theme=data["custom_theme"],
            custom_designs=data["custom_designs"],
            ux_research=data["ux_research"],
            teams_selected=data["teams_selected"],
            estimated_months=data["estimated_months"],
        )

        return jsonify(forecast_result), 200

    except Exception as e:
        logger.error(f"Error calculating forecast: {e}")
        return jsonify({"error": str(e)}), 500


@forecasts_bp.route("", methods=["GET"])
def list_forecasts():
    """List all saved forecasts."""
    try:
        session = get_session()
        forecasts = (
            session.query(EpicForecast).order_by(EpicForecast.created_at.desc()).all()
        )

        return (
            jsonify(
                {
                    "forecasts": [
                        {
                            "id": f.id,
                            "project_key": f.project_key,
                            "epic_name": f.epic_name,
                            "total_hours": f.total_hours,
                            "estimated_months": f.estimated_months,
                            "teams_selected": f.teams_selected,
                            "characteristics": {
                                "be_integrations": f.be_integrations,
                                "custom_theme": f.custom_theme,
                                "custom_designs": f.custom_designs,
                                "ux_research": f.ux_research,
                            },
                            "created_at": (
                                f.created_at.isoformat() if f.created_at else None
                            ),
                        }
                        for f in forecasts
                    ]
                }
            ),
            200,
        )

    except Exception as e:
        logger.error(f"Error listing forecasts: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@forecasts_bp.route("", methods=["POST"])
def save_forecast():
    """
    Save a new forecast.

    Request body:
    {
        "project_key": str,
        "epic_name": str,
        "epic_description": str (optional),
        "be_integrations": bool,
        "custom_theme": bool,
        "custom_designs": bool,
        "ux_research": bool,
        "teams_selected": [...],
        "estimated_months": int,
        "forecast_data": {...},
        "total_hours": float
    }
    """
    try:
        data = request.json
        session = get_session()

        forecast = EpicForecast(
            project_key=data["project_key"],
            epic_name=data["epic_name"],
            epic_description=data.get("epic_description"),
            be_integrations=data["be_integrations"],
            custom_theme=data["custom_theme"],
            custom_designs=data["custom_designs"],
            ux_research=data["ux_research"],
            teams_selected=data["teams_selected"],
            estimated_months=data["estimated_months"],
            forecast_data=data["forecast_data"],
            total_hours=data["total_hours"],
            created_by=data.get("created_by"),
        )

        session.add(forecast)
        session.commit()

        return (
            jsonify({"id": forecast.id, "message": "Forecast saved successfully"}),
            201,
        )

    except Exception as e:
        logger.error(f"Error saving forecast: {e}")
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@forecasts_bp.route("/<int:forecast_id>", methods=["GET"])
def get_forecast(forecast_id):
    """Get a specific forecast by ID."""
    try:
        session = get_session()
        forecast = session.query(EpicForecast).filter_by(id=forecast_id).first()

        if not forecast:
            return jsonify({"error": "Forecast not found"}), 404

        return (
            jsonify(
                {
                    "id": forecast.id,
                    "project_key": forecast.project_key,
                    "epic_name": forecast.epic_name,
                    "epic_description": forecast.epic_description,
                    "characteristics": {
                        "be_integrations": forecast.be_integrations,
                        "custom_theme": forecast.custom_theme,
                        "custom_designs": forecast.custom_designs,
                        "ux_research": forecast.ux_research,
                    },
                    "teams_selected": forecast.teams_selected,
                    "estimated_months": forecast.estimated_months,
                    "forecast_data": forecast.forecast_data,
                    "total_hours": forecast.total_hours,
                    "created_at": (
                        forecast.created_at.isoformat() if forecast.created_at else None
                    ),
                    "updated_at": (
                        forecast.updated_at.isoformat() if forecast.updated_at else None
                    ),
                }
            ),
            200,
        )

    except Exception as e:
        logger.error(f"Error getting forecast: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@forecasts_bp.route("/<int:forecast_id>", methods=["PUT"])
def update_forecast(forecast_id):
    """Update an existing forecast."""
    try:
        data = request.json
        session = get_session()

        forecast = session.query(EpicForecast).filter_by(id=forecast_id).first()

        if not forecast:
            return jsonify({"error": "Forecast not found"}), 404

        # Update fields
        if "epic_name" in data:
            forecast.epic_name = data["epic_name"]
        if "epic_description" in data:
            forecast.epic_description = data["epic_description"]
        if "project_key" in data:
            forecast.project_key = data["project_key"]

        session.commit()

        return jsonify({"message": "Forecast updated successfully"}), 200

    except Exception as e:
        logger.error(f"Error updating forecast: {e}")
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@forecasts_bp.route("/<int:forecast_id>", methods=["DELETE"])
def delete_forecast(forecast_id):
    """Delete a forecast."""
    try:
        session = get_session()
        forecast = session.query(EpicForecast).filter_by(id=forecast_id).first()

        if not forecast:
            return jsonify({"error": "Forecast not found"}), 404

        session.delete(forecast)
        session.commit()

        return jsonify({"message": "Forecast deleted successfully"}), 200

    except Exception as e:
        logger.error(f"Error deleting forecast: {e}")
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@forecasts_bp.route("/baselines", methods=["GET"])
def get_baselines():
    """Get baseline hours for all teams based on integration requirement."""
    try:
        be_integrations = request.args.get("be_integrations", "false").lower() == "true"

        baselines = forecasting_service.get_baseline_info(be_integrations)
        baseline_set = "with_integration" if be_integrations else "no_integration"

        return jsonify({"baseline_set": baseline_set, "baselines": baselines}), 200

    except Exception as e:
        logger.error(f"Error getting baselines: {e}")
        return jsonify({"error": str(e)}), 500


@forecasts_bp.route("/lifecycle/<team>", methods=["GET"])
def get_lifecycle(team):
    """Get lifecycle percentages for a specific team."""
    try:
        lifecycle = forecasting_service.get_lifecycle_info(team)

        return jsonify({"team": team, "lifecycle": lifecycle}), 200

    except Exception as e:
        logger.error(f"Error getting lifecycle info: {e}")
        return jsonify({"error": str(e)}), 500


@forecasts_bp.route("/calculate-from-total", methods=["POST"])
def calculate_from_total_hours():
    """
    Calculate team distribution from total hours budget.

    Supports two modes:
    1. Statistical baseline mode (default): Uses averaged historical data
    2. AI-powered mode (use_ai=true): Uses LLM to analyze similar projects and make intelligent predictions

    Request body:
    {
        "total_hours": float,
        "be_integrations": int (1-5 slider value),
        "custom_theme": int (1-5 slider value),
        "custom_designs": int (1-5 slider value),
        "ux_research": int (1-5 slider value),
        "extensive_customizations": int (1-5 slider value, optional, default: 1),
        "project_oversight": int (1-5 slider value, optional, default: 3),
        "teams_selected": [...],
        "estimated_months": int,
        "start_date": str (YYYY-MM-DD, optional),
        "use_ai": bool (optional, default: true) - Use AI-powered intelligent forecasting
    }
    """
    try:
        data = request.json

        # Validate required fields
        required_fields = [
            "total_hours",
            "be_integrations",
            "custom_theme",
            "custom_designs",
            "ux_research",
            "teams_selected",
            "estimated_months",
        ]
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400

        # Check if AI-powered forecasting is requested (default: true for intelligent analysis)
        use_ai = data.get("use_ai", True)

        if use_ai:
            # Use AI-powered intelligent forecasting
            logger.info("Using AI-powered intelligent forecasting")
            session = get_session()
            try:
                intelligent_service = IntelligentForecastingService(session)

                project_characteristics = {
                    "be_integrations": data["be_integrations"],
                    "custom_theme": data["custom_theme"],
                    "custom_designs": data["custom_designs"],
                    "ux_research": data["ux_research"],
                    "extensive_customizations": data.get("extensive_customizations", 1),
                    "project_oversight": data.get("project_oversight", 3),
                }

                result = intelligent_service.generate_intelligent_forecast(
                    project_characteristics=project_characteristics,
                    total_hours=data["total_hours"],
                    estimated_months=data["estimated_months"],
                    teams_selected=data["teams_selected"],
                    start_date=data.get("start_date"),
                )

                # Add metadata indicating AI was used
                result["forecast_method"] = "ai_powered"
                result["forecast_description"] = "Intelligent AI analysis of similar historical projects"

            finally:
                session.close()
        else:
            # Use traditional statistical baseline forecasting
            logger.info("Using statistical baseline forecasting")
            result = forecasting_service.calculate_from_total_hours(
                total_hours=data["total_hours"],
                be_integrations=data["be_integrations"],
                custom_theme=data["custom_theme"],
                custom_designs=data["custom_designs"],
                ux_research=data["ux_research"],
                teams_selected=data["teams_selected"],
                estimated_months=data["estimated_months"],
                extensive_customizations=data.get("extensive_customizations", 1),
                project_oversight=data.get("project_oversight", 3),
                start_date=data.get("start_date"),
            )

            # Add metadata indicating statistical method was used
            result["forecast_method"] = "statistical_baseline"
            result["forecast_description"] = "Statistical averaging of historical baselines"

        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Error calculating team distribution: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@forecasts_bp.route("/export-combined-forecast", methods=["POST"])
def export_combined_forecast():
    """
    Export combined project forecast (team distribution + epic schedule) as CSV.

    Request body:
    {
        "total_hours": float,
        "be_integrations": int (1-5),
        "custom_theme": int (1-5),
        "custom_designs": int (1-5),
        "ux_research": int (1-5),
        "extensive_customizations": int (1-5, optional),
        "project_oversight": int (1-5, optional),
        "teams_selected": [...],
        "estimated_months": int,
        "start_date": str (YYYY-MM-DD)
    }
    """
    try:
        from datetime import datetime
        from dateutil.relativedelta import relativedelta
        from src.api.analytics_schedule import generate_project_schedule

        data = request.json

        # Validate required fields
        required_fields = [
            "total_hours",
            "be_integrations",
            "custom_theme",
            "custom_designs",
            "ux_research",
            "teams_selected",
            "estimated_months",
            "start_date",
        ]
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400

        # Get team distribution data
        team_result = forecasting_service.calculate_from_total_hours(
            total_hours=data["total_hours"],
            be_integrations=data["be_integrations"],
            custom_theme=data["custom_theme"],
            custom_designs=data["custom_designs"],
            ux_research=data["ux_research"],
            teams_selected=data["teams_selected"],
            estimated_months=data["estimated_months"],
            extensive_customizations=data.get("extensive_customizations", 1),
            project_oversight=data.get("project_oversight", 3),
        )

        # Get epic schedule data
        epic_schedule = generate_project_schedule(
            total_hours=data["total_hours"],
            duration_months=data["estimated_months"],
            start_date=data["start_date"],
        )

        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)

        # Section 1: Project Summary
        writer.writerow(["PROJECT FORECAST SUMMARY"])
        writer.writerow([""])
        writer.writerow(["Total Hours", data["total_hours"]])
        writer.writerow(["Duration (Months)", data["estimated_months"]])
        writer.writerow(["Start Date", data["start_date"]])
        writer.writerow([""])
        writer.writerow(["Project Characteristics"])
        writer.writerow(["Backend Integrations", data["be_integrations"]])
        writer.writerow(["Custom Theme", data["custom_theme"]])
        writer.writerow(["Custom Designs", data["custom_designs"]])
        writer.writerow(["UX Research", data["ux_research"]])
        writer.writerow(
            ["Extensive Customizations", data.get("extensive_customizations", 1)]
        )
        writer.writerow([""])
        writer.writerow([""])

        # Section 2: Team Distribution
        writer.writerow(["TEAM DISTRIBUTION"])
        writer.writerow([""])
        writer.writerow(["Team", "Total Hours", "Percentage"])
        for team_data in team_result["teams"]:
            writer.writerow(
                [
                    team_data["team"],
                    team_data["total_hours"],
                    f"{team_data['percentage']}%",
                ]
            )
        writer.writerow([""])
        writer.writerow([""])

        # Section 3: Team Monthly Breakdown
        writer.writerow(["TEAM MONTHLY BREAKDOWN"])
        writer.writerow([""])
        for team_data in team_result["teams"]:
            writer.writerow(
                [f"{team_data['team']} ({team_data['total_hours']}h total)"]
            )
            writer.writerow(["Month", "Phase", "Hours"])
            for month_data in team_data["monthly_breakdown"]:
                writer.writerow(
                    [
                        f"Month {month_data['month']}",
                        month_data["phase"],
                        month_data["hours"],
                    ]
                )
            writer.writerow([""])
        writer.writerow([""])

        # Section 4: Epic Schedule Breakdown
        writer.writerow(["EPIC SCHEDULE BREAKDOWN"])
        writer.writerow([""])

        # Epic schedule header
        header_row = ["Epic", "Temporal Pattern", "Total Hours"]
        start_date_obj = datetime.strptime(data["start_date"], "%Y-%m-%d")
        for i in range(data["estimated_months"]):
            month_date = start_date_obj + relativedelta(months=i)
            header_row.append(month_date.strftime("%b %Y"))
        writer.writerow(header_row)

        # Epic schedule data
        for epic in epic_schedule.get("epics", []):
            row = [
                epic["name"],
                epic.get("temporal_pattern", "Even"),
                epic["total_hours"],
            ]
            for month_hours in epic["monthly_hours"]:
                row.append(month_hours)
            writer.writerow(row)

        writer.writerow([""])
        writer.writerow(
            ["Total Hours", epic_schedule.get("total_hours", data["total_hours"])]
        )

        # Create response
        output.seek(0)
        response = make_response(output.getvalue())
        response.headers["Content-Type"] = "text/csv"
        response.headers["Content-Disposition"] = (
            f'attachment; filename=project_forecast_{data["start_date"]}.csv'
        )

        return response

    except Exception as e:
        logger.error(f"Error exporting combined forecast: {e}")
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@forecasts_bp.route("/match-jira-epics", methods=["POST"])
def match_jira_epics():
    """
    Fuzzy match forecast epic names to existing Jira epics.

    Request body:
    {
        "project_key": str,
        "epic_names": [str]  # List of epic names from forecast/templates
    }

    Returns:
    {
        "matches": [
            {
                "forecast_epic": str,
                "suggestions": [
                    {
                        "key": str,
                        "name": str,
                        "score": int (0-100),
                        "status": str
                    }
                ]
            }
        ]
    }
    """
    try:
        from fuzzywuzzy import fuzz
        from src.integrations.jira_mcp import JiraMCPClient
        from src.config.settings import config
        import asyncio

        data = request.json

        # Validate required fields
        if "project_key" not in data or "epic_names" not in data:
            return (
                jsonify({"error": "Missing required fields: project_key, epic_names"}),
                400,
            )

        project_key = data["project_key"]
        epic_names = data["epic_names"]

        if not isinstance(epic_names, list) or len(epic_names) == 0:
            return jsonify({"error": "epic_names must be a non-empty list"}), 400

        # Initialize Jira client
        jira_client = JiraMCPClient(
            jira_url=config.JIRA_URL,
            username=config.JIRA_USERNAME,
            api_token=config.JIRA_API_TOKEN,
        )

        # Search for existing epics in Jira project
        async def search_epics():
            jql = f"project = {project_key} AND type = Epic ORDER BY created DESC"
            return await jira_client.search_tickets(jql=jql, max_results=200)

        # Run async search
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        jira_epics = loop.run_until_complete(search_epics())
        loop.close()

        # Extract epic names from Jira
        jira_epic_list = []
        for epic in jira_epics:
            fields = epic.get("fields", {})
            jira_epic_list.append(
                {
                    "key": epic.get("key"),
                    "name": fields.get("summary", ""),
                    "status": fields.get("status", {}).get("name", "Unknown"),
                }
            )

        # Perform fuzzy matching for each forecast epic
        matches = []
        for epic_name in epic_names:
            suggestions = []

            for jira_epic in jira_epic_list:
                # Calculate fuzzy match score
                score = fuzz.ratio(epic_name.lower(), jira_epic["name"].lower())

                # Only include matches with score >= 60 (configurable threshold)
                if score >= 60:
                    suggestions.append(
                        {
                            "key": jira_epic["key"],
                            "name": jira_epic["name"],
                            "score": score,
                            "status": jira_epic["status"],
                        }
                    )

            # Sort suggestions by score (highest first)
            suggestions.sort(key=lambda x: x["score"], reverse=True)

            # Limit to top 5 suggestions
            matches.append({"forecast_epic": epic_name, "suggestions": suggestions[:5]})

        return (
            jsonify({"success": True, "project_key": project_key, "matches": matches}),
            200,
        )

    except Exception as e:
        logger.error(f"Error matching Jira epics: {e}")
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@forecasts_bp.route("/export-to-jira", methods=["POST"])
def export_to_jira():
    """
    Export forecast epics to Jira with mapping to existing or new epics.

    Request body:
    {
        "project_key": str,
        "epics": [
            {
                "name": str,
                "description": str (optional),
                "estimated_hours": float,
                "action": "create" | "link",  # create new epic or link to existing
                "existing_epic_key": str (optional, required if action="link"),
                "story_points": int (optional)
            }
        ]
    }

    Returns:
    {
        "success": bool,
        "results": [
            {
                "epic_name": str,
                "action": "created" | "linked",
                "epic_key": str,
                "error": str (optional, if failed)
            }
        ]
    }
    """
    try:
        from src.integrations.jira_mcp import JiraMCPClient, JiraTicket
        from src.config.settings import config
        import asyncio

        data = request.json

        # Validate required fields
        if "project_key" not in data or "epics" not in data:
            return (
                jsonify({"error": "Missing required fields: project_key, epics"}),
                400,
            )

        project_key = data["project_key"]
        epics = data["epics"]

        if not isinstance(epics, list) or len(epics) == 0:
            return jsonify({"error": "epics must be a non-empty list"}), 400

        # Initialize Jira client
        jira_client = JiraMCPClient(
            jira_url=config.JIRA_URL,
            username=config.JIRA_USERNAME,
            api_token=config.JIRA_API_TOKEN,
        )

        results = []

        # Process each epic
        async def process_epics():
            for epic_data in epics:
                try:
                    epic_name = epic_data.get("name")
                    action = epic_data.get("action", "create")

                    if not epic_name:
                        results.append(
                            {
                                "epic_name": "Unknown",
                                "action": "failed",
                                "error": "Epic name is required",
                            }
                        )
                        continue

                    if action == "link":
                        # Link to existing epic
                        existing_key = epic_data.get("existing_epic_key")
                        if not existing_key:
                            results.append(
                                {
                                    "epic_name": epic_name,
                                    "action": "failed",
                                    "error": "existing_epic_key is required for link action",
                                }
                            )
                            continue

                        # Verify epic exists and optionally update estimate
                        epic = await jira_client.get_ticket(existing_key)
                        if epic.get("success") is False:
                            results.append(
                                {
                                    "epic_name": epic_name,
                                    "action": "failed",
                                    "error": f"Epic {existing_key} not found",
                                }
                            )
                            continue

                        # Optionally update story points if provided
                        if "story_points" in epic_data:
                            await jira_client.update_ticket(
                                existing_key,
                                {
                                    "customfield_10016": epic_data["story_points"]
                                },  # Story points field
                            )

                        results.append(
                            {
                                "epic_name": epic_name,
                                "action": "linked",
                                "epic_key": existing_key,
                            }
                        )

                    elif action == "create":
                        # Create new epic
                        description = epic_data.get("description", "")
                        estimated_hours = epic_data.get("estimated_hours", 0)
                        story_points = epic_data.get("story_points")

                        # Build description with hours estimate
                        full_description = (
                            f"{description}\n\nEstimated Hours: {estimated_hours}h"
                        )

                        ticket = JiraTicket(
                            project_key=project_key,
                            summary=epic_name,
                            description=full_description,
                            issue_type="Epic",
                            story_points=story_points,
                        )

                        result = await jira_client.create_ticket(ticket)

                        if result.get("success"):
                            results.append(
                                {
                                    "epic_name": epic_name,
                                    "action": "created",
                                    "epic_key": result.get("key"),
                                }
                            )
                        else:
                            results.append(
                                {
                                    "epic_name": epic_name,
                                    "action": "failed",
                                    "error": result.get("error", "Unknown error"),
                                }
                            )

                    else:
                        results.append(
                            {
                                "epic_name": epic_name,
                                "action": "failed",
                                "error": f'Invalid action: {action}. Must be "create" or "link"',
                            }
                        )

                except Exception as e:
                    logger.error(
                        f"Error processing epic {epic_data.get('name', 'Unknown')}: {e}"
                    )
                    results.append(
                        {
                            "epic_name": epic_data.get("name", "Unknown"),
                            "action": "failed",
                            "error": str(e),
                        }
                    )

        # Run async processing
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(process_epics())
        loop.close()

        # Check if all succeeded
        all_success = all(r["action"] in ["created", "linked"] for r in results)

        return (
            jsonify(
                {"success": all_success, "project_key": project_key, "results": results}
            ),
            200,
        )

    except Exception as e:
        logger.error(f"Error exporting to Jira: {e}")
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@forecasts_bp.route("/epic-monthly-breakdown", methods=["POST"])
def epic_monthly_breakdown():
    """
    Calculate epic-by-epic monthly hour breakdown for project forecasting.

    Request body:
    {
        "epics": [
            {
                "name": str,
                "estimated_hours": float,
                "estimated_months": int,
                "teams_selected": [str],
                "be_integrations": int (1-5),
                "custom_theme": int (1-5),
                "custom_designs": int (1-5),
                "ux_research": int (1-5),
                "extensive_customizations": int (1-5, optional),
                "project_oversight": int (1-5, optional),
                "start_date": str (YYYY-MM-DD, optional)
            }
        ],
        "project_start_date": str (YYYY-MM-DD, optional)
    }

    Returns:
    {
        "success": true,
        "breakdown": {
            "epics": [...],
            "months": [...],
            "totals_by_month": [...]
        }
    }
    """
    try:
        data = request.json

        if "epics" not in data or not data["epics"]:
            return jsonify({"error": "Missing or empty epics list"}), 400

        # Validate epic data
        required_fields = [
            "name",
            "estimated_hours",
            "estimated_months",
            "teams_selected",
        ]
        for epic in data["epics"]:
            for field in required_fields:
                if field not in epic:
                    return (
                        jsonify({"error": f"Epic missing required field: {field}"}),
                        400,
                    )

        # Get project start date if provided
        project_start_date = data.get("project_start_date")

        # Calculate breakdown
        breakdown = forecasting_service.get_epic_monthly_breakdown(
            epics=data["epics"], project_start_date=project_start_date
        )

        return jsonify({"success": True, "breakdown": breakdown}), 200

    except Exception as e:
        logger.error(f"Error calculating epic monthly breakdown: {e}")
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
