"""Jira integration API endpoints."""

from flask import Blueprint, jsonify, request
from datetime import datetime
import logging
import asyncio

from config.settings import settings
from src.integrations.jira_mcp import JiraMCPClient
from src.utils.database import get_engine

logger = logging.getLogger(__name__)

# Create blueprint
jira_bp = Blueprint('jira', __name__, url_prefix='/api/jira')


# Import response helpers
def success_response(data=None, message=None, status_code=200):
    """Standard success response format."""
    response = {'success': True}
    if data is not None:
        response['data'] = data
    if message is not None:
        response['message'] = message
    return jsonify(response), status_code


def error_response(error, status_code=500, details=None):
    """Standard error response format."""
    response = {'success': False, 'error': str(error)}
    if details is not None:
        response['details'] = details
    return jsonify(response), status_code


# =============================================================================
# API Routes
# =============================================================================

@jira_bp.route("/projects", methods=["GET"])
def get_jira_projects():
    """Get all Jira projects with local database enhancements."""
    try:
        # Check if Jira credentials are configured
        if not settings.jira.url or not settings.jira.username or not settings.jira.api_token:
            logger.error("Jira credentials not configured")
            return error_response("Jira credentials not configured", status_code=500)

        logger.info(f"Fetching projects from Jira URL: {settings.jira.url}")

        # Fetch projects from Jira
        async def fetch_projects():
            async with JiraMCPClient(
                jira_url=settings.jira.url,
                username=settings.jira.username,
                api_token=settings.jira.api_token
            ) as jira_client:
                return await jira_client.get_projects()

        jira_projects = asyncio.run(fetch_projects())
        logger.info(f"Fetched {len(jira_projects)} projects from Jira")

        # Merge with local database data
        from sqlalchemy import text
        engine = get_engine()

        enhanced_projects = []
        try:
            with engine.connect() as conn:
                # Get current month for joining with monthly forecast
                from datetime import datetime
                now = datetime.now()
                current_month = datetime(now.year, now.month, 1).date()

                for project in jira_projects:
                    enhanced_project = project.copy()
                    try:
                        # Get local project data joined with current month forecast
                        result = conn.execute(text("""
                            SELECT
                                p.is_active,
                                p.project_work_type,
                                p.total_hours,
                                p.cumulative_hours,
                                p.slack_channel,
                                p.weekly_meeting_day,
                                p.retainer_hours,
                                pmf.forecasted_hours,
                                pmf.actual_monthly_hours
                            FROM projects p
                            LEFT JOIN project_monthly_forecast pmf
                                ON p.key = pmf.project_key
                                AND pmf.month_year = :current_month
                            WHERE p.key = :key
                        """), {"key": project["key"], "current_month": current_month}).fetchone()

                        if result:
                            enhanced_project["is_active"] = bool(result[0]) if result[0] is not None else True
                            enhanced_project["project_work_type"] = result[1] if result[1] else 'project-based'
                            enhanced_project["total_hours"] = float(result[2]) if result[2] else 0
                            enhanced_project["cumulative_hours"] = float(result[3]) if result[3] else 0
                            enhanced_project["slack_channel"] = result[4] if result[4] else None
                            enhanced_project["weekly_meeting_day"] = result[5] if result[5] else None
                            enhanced_project["retainer_hours"] = float(result[6]) if result[6] else 0
                            enhanced_project["forecasted_hours_month"] = float(result[7]) if result[7] else 0
                            enhanced_project["current_month_hours"] = float(result[8]) if result[8] else 0
                        else:
                            # No database record - use defaults
                            enhanced_project["is_active"] = True
                            enhanced_project["project_work_type"] = 'project-based'
                            enhanced_project["total_hours"] = 0
                            enhanced_project["cumulative_hours"] = 0
                            enhanced_project["slack_channel"] = None
                            enhanced_project["weekly_meeting_day"] = None
                            enhanced_project["retainer_hours"] = 0
                            enhanced_project["forecasted_hours_month"] = 0
                            enhanced_project["current_month_hours"] = 0
                    except Exception:
                        # Projects table doesn't exist or query failed - use defaults
                        enhanced_project["forecasted_hours_month"] = 0
                        enhanced_project["is_active"] = True
                        enhanced_project["project_work_type"] = 'project-based'
                        enhanced_project["total_hours"] = 0
                        enhanced_project["current_month_hours"] = 0
                        enhanced_project["cumulative_hours"] = 0
                        enhanced_project["slack_channel"] = None
                        enhanced_project["weekly_meeting_day"] = None

                    enhanced_projects.append(enhanced_project)
        except Exception as e:
            # If database operations fail entirely, return projects without enhancements
            logger.warning(f"Could not enhance projects with database data: {e}")
            enhanced_projects = jira_projects

        return success_response(data={'projects': enhanced_projects})
    except Exception as e:
        logger.error(f"Error fetching Jira projects: {e}")
        return error_response(str(e), status_code=500)


@jira_bp.route("/projects/<project_key>", methods=["GET"])
def get_jira_project(project_key):
    """Get a single Jira project by key with local database enhancements."""
    try:
        # Check if Jira credentials are configured
        if not settings.jira.url or not settings.jira.username or not settings.jira.api_token:
            logger.error("Jira credentials not configured")
            return error_response("Jira credentials not configured", status_code=500)

        logger.info(f"Fetching project {project_key} from Jira")

        # Fetch project from Jira
        async def fetch_project():
            async with JiraMCPClient(
                jira_url=settings.jira.url,
                username=settings.jira.username,
                api_token=settings.jira.api_token
            ) as jira_client:
                projects = await jira_client.get_projects()
                # Find the specific project by key
                for project in projects:
                    if project.get('key') == project_key:
                        return project
                return None

        jira_project = asyncio.run(fetch_project())

        if not jira_project:
            return error_response(f"Project {project_key} not found", status_code=404)

        logger.info(f"Found project {project_key} in Jira")

        # Enhance with local database data
        from sqlalchemy import text
        engine = get_engine()

        enhanced_project = jira_project.copy()
        try:
            with engine.connect() as conn:
                # Get current month for joining with monthly forecast
                from datetime import datetime
                now = datetime.now()
                current_month = datetime(now.year, now.month, 1).date()

                # Get local project data joined with current month forecast
                result = conn.execute(text("""
                    SELECT
                        p.is_active,
                        p.project_work_type,
                        p.total_hours,
                        p.cumulative_hours,
                        p.slack_channel,
                        p.weekly_meeting_day,
                        p.retainer_hours,
                        p.description,
                        pmf.forecasted_hours,
                        pmf.actual_monthly_hours
                    FROM projects p
                    LEFT JOIN project_monthly_forecast pmf
                        ON p.key = pmf.project_key
                        AND pmf.month_year = :current_month
                    WHERE p.key = :key
                """), {"key": project_key, "current_month": current_month}).fetchone()

                if result:
                    enhanced_project["is_active"] = bool(result[0]) if result[0] is not None else True
                    enhanced_project["project_work_type"] = result[1] if result[1] else 'project-based'
                    enhanced_project["total_hours"] = float(result[2]) if result[2] else 0
                    enhanced_project["cumulative_hours"] = float(result[3]) if result[3] else 0
                    enhanced_project["slack_channel"] = result[4] if result[4] else None
                    enhanced_project["weekly_meeting_day"] = result[5] if result[5] else None
                    enhanced_project["retainer_hours"] = float(result[6]) if result[6] else 0
                    enhanced_project["description"] = result[7] if result[7] else None
                    enhanced_project["forecasted_hours_month"] = float(result[8]) if result[8] else 0
                    enhanced_project["current_month_hours"] = float(result[9]) if result[9] else 0
                else:
                    # No database record - use defaults
                    enhanced_project["is_active"] = True
                    enhanced_project["project_work_type"] = 'project-based'
                    enhanced_project["total_hours"] = 0
                    enhanced_project["cumulative_hours"] = 0
                    enhanced_project["slack_channel"] = None
                    enhanced_project["weekly_meeting_day"] = None
                    enhanced_project["retainer_hours"] = 0
                    enhanced_project["description"] = None
                    enhanced_project["forecasted_hours_month"] = 0
                    enhanced_project["current_month_hours"] = 0
        except Exception as e:
            # If database operations fail, use defaults
            logger.warning(f"Could not enhance project with database data: {e}")
            enhanced_project["is_active"] = True
            enhanced_project["project_work_type"] = 'project-based'
            enhanced_project["total_hours"] = 0
            enhanced_project["cumulative_hours"] = 0
            enhanced_project["slack_channel"] = None
            enhanced_project["weekly_meeting_day"] = None
            enhanced_project["retainer_hours"] = 0
            enhanced_project["description"] = None
            enhanced_project["forecasted_hours_month"] = 0
            enhanced_project["current_month_hours"] = 0

        return success_response(data=enhanced_project)
    except Exception as e:
        logger.error(f"Error fetching Jira project {project_key}: {e}")
        return error_response(str(e), status_code=500)


@jira_bp.route("/issue-types", methods=["GET"])
def get_jira_issue_types():
    """Get Jira issue types for a project."""
    try:
        project_key = request.args.get('project')

        async def fetch_issue_types():
            async with JiraMCPClient(
                jira_url=settings.jira.url,
                username=settings.jira.username,
                api_token=settings.jira.api_token
            ) as jira_client:
                return await jira_client.get_issue_types(project_key)

        issue_types = asyncio.run(fetch_issue_types())
        return success_response(data={'issue_types': issue_types})
    except Exception as e:
        logger.error(f"Error fetching Jira issue types: {e}")
        return error_response(str(e), status_code=500)


@jira_bp.route("/users", methods=["GET"])
def get_jira_users():
    """Get assignable users for a project."""
    try:
        project_key = request.args.get('project')
        max_results = int(request.args.get('max_results', 200))

        async def fetch_users():
            async with JiraMCPClient(
                jira_url=settings.jira.url,
                username=settings.jira.username,
                api_token=settings.jira.api_token
            ) as jira_client:
                return await jira_client.get_users(project_key, max_results)

        users = asyncio.run(fetch_users())
        return success_response(data={'users': users})
    except Exception as e:
        logger.error(f"Error fetching Jira users: {e}")
        return error_response(str(e), status_code=500)


@jira_bp.route("/users/search", methods=["GET"])
def search_jira_users():
    """Search users with autocomplete - requires minimum 3 characters."""
    try:
        query = request.args.get('q', '').strip()

        # Require minimum 3 characters
        if len(query) < 3:
            return success_response(data={'users': []})

        project_key = request.args.get('project')
        max_results = int(request.args.get('max_results', 20))  # Smaller limit for autocomplete

        async def fetch_users():
            async with JiraMCPClient(
                jira_url=settings.jira.url,
                username=settings.jira.username,
                api_token=settings.jira.api_token
            ) as jira_client:
                return await jira_client.search_users(query, project_key, max_results)

        users = asyncio.run(fetch_users())
        return success_response(data={'users': users})
    except Exception as e:
        logger.error(f"Error searching Jira users: {e}")
        return error_response(str(e), status_code=500)


@jira_bp.route("/priorities", methods=["GET"])
def get_jira_priorities():
    """Get Jira priorities."""
    try:
        async def fetch_priorities():
            async with JiraMCPClient(
                jira_url=settings.jira.url,
                username=settings.jira.username,
                api_token=settings.jira.api_token
            ) as jira_client:
                return await jira_client.get_priorities()

        priorities = asyncio.run(fetch_priorities())
        return success_response(data={'priorities': priorities})
    except Exception as e:
        logger.error(f"Error fetching Jira priorities: {e}")
        return error_response(str(e), status_code=500)


@jira_bp.route("/metadata/<project_key>", methods=["GET"])
def get_jira_metadata(project_key):
    """Get comprehensive Jira metadata for a project."""
    try:
        async def fetch_metadata():
            async with JiraMCPClient(
                jira_url=settings.jira.url,
                username=settings.jira.username,
                api_token=settings.jira.api_token
            ) as jira_client:
                return await jira_client.get_project_metadata(project_key)

        metadata = asyncio.run(fetch_metadata())
        return success_response(data={'metadata': metadata})
    except Exception as e:
        logger.error(f"Error fetching Jira metadata: {e}")
        return error_response(str(e), status_code=500)


@jira_bp.route('/projects/<project_key>', methods=['PUT'])
def update_project(project_key):
    """Update project data in local database."""
    try:
        data = request.json

        # Connect to database
        from sqlalchemy import text
        from datetime import datetime
        engine = get_engine()

        # Get current month for forecast table
        now = datetime.now()
        current_month = datetime(now.year, now.month, 1).date()

        with engine.connect() as conn:
            # Check if project exists in local DB
            result = conn.execute(text("""
                SELECT * FROM projects WHERE key = :key
            """), {"key": project_key})

            existing = result.fetchone()

            if existing:
                # Update existing project
                conn.execute(text("""
                    UPDATE projects
                    SET is_active = :is_active,
                        project_work_type = :project_work_type,
                        total_hours = :total_hours,
                        retainer_hours = :retainer_hours,
                        name = :name,
                        slack_channel = :slack_channel,
                        weekly_meeting_day = :weekly_meeting_day,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE key = :key
                """), {
                    "key": project_key,
                    "is_active": data.get('is_active', True),
                    "project_work_type": data.get('project_work_type', 'ongoing'),
                    "total_hours": data.get('total_hours', 0),
                    "retainer_hours": data.get('retainer_hours', 0),
                    "name": data.get('name', existing[1] if existing else 'Unknown'),
                    "slack_channel": data.get('slack_channel'),
                    "weekly_meeting_day": data.get('weekly_meeting_day')
                })
            else:
                # Insert new project
                conn.execute(text("""
                    INSERT INTO projects (key, name, is_active, project_work_type, total_hours, retainer_hours, slack_channel, weekly_meeting_day)
                    VALUES (:key, :name, :is_active, :project_work_type, :total_hours, :retainer_hours, :slack_channel, :weekly_meeting_day)
                """), {
                    "key": project_key,
                    "name": data.get('name', 'Unknown'),
                    "is_active": data.get('is_active', True),
                    "project_work_type": data.get('project_work_type', 'ongoing'),
                    "total_hours": data.get('total_hours', 0),
                    "retainer_hours": data.get('retainer_hours', 0),
                    "slack_channel": data.get('slack_channel'),
                    "weekly_meeting_day": data.get('weekly_meeting_day')
                })

            # Upsert forecasted hours for current month if provided
            if 'forecasted_hours_month' in data:
                conn.execute(text("""
                    INSERT INTO project_monthly_forecast
                        (project_key, month_year, forecasted_hours, updated_at)
                    VALUES
                        (:project_key, :month_year, :forecasted_hours, NOW())
                    ON CONFLICT (project_key, month_year)
                    DO UPDATE SET
                        forecasted_hours = :forecasted_hours,
                        updated_at = NOW()
                """), {
                    "project_key": project_key,
                    "month_year": current_month,
                    "forecasted_hours": data.get('forecasted_hours_month', 0)
                })

            conn.commit()

        return success_response(message='Project updated successfully')

    except Exception as e:
        logger.error(f"Error updating project {project_key}: {e}")
        return error_response(str(e), status_code=500)


@jira_bp.route('/project-forecasts/batch', methods=['POST'])
def get_project_forecasts_batch():
    """Get monthly forecasts for multiple projects in a single request (rolling 6 months from current month)."""
    try:
        from sqlalchemy import text
        from datetime import datetime
        from dateutil.relativedelta import relativedelta

        data = request.json
        project_keys = data.get('project_keys', [])

        if not project_keys:
            return error_response('project_keys is required', status_code=400)

        engine = get_engine()
        now = datetime.now()
        current_month = datetime(now.year, now.month, 1).date()

        # Calculate 6 months forward
        months = []
        for i in range(6):
            month = (datetime(now.year, now.month, 1) + relativedelta(months=i)).date()
            months.append(month)

        # Fetch all forecasts in a single query
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT project_key, month_year, forecasted_hours, actual_monthly_hours
                FROM project_monthly_forecast
                WHERE project_key = ANY(:project_keys)
                AND month_year >= :start_month
                ORDER BY project_key, month_year ASC
            """), {
                "project_keys": project_keys,
                "start_month": current_month
            })

            # Group by project_key
            forecasts_by_project = {}
            for row in result:
                project_key = row[0]
                month_year = row[1]
                if project_key not in forecasts_by_project:
                    forecasts_by_project[project_key] = {}
                forecasts_by_project[project_key][month_year] = {
                    "forecasted_hours": float(row[2]) if row[2] else 0,
                    "actual_monthly_hours": float(row[3]) if row[3] else 0
                }

        # Build response with all 6 months for each project
        response_data = {}
        for project_key in project_keys:
            forecasts = []
            existing_forecasts = forecasts_by_project.get(project_key, {})
            for month in months:
                forecast_data = existing_forecasts.get(month, {"forecasted_hours": 0, "actual_monthly_hours": 0})
                forecasts.append({
                    "month_year": month.isoformat(),
                    "forecasted_hours": forecast_data["forecasted_hours"],
                    "actual_monthly_hours": forecast_data["actual_monthly_hours"]
                })
            response_data[project_key] = forecasts

        return success_response(data={'forecasts': response_data})

    except Exception as e:
        logger.error(f"Error fetching batch forecasts: {e}")
        return error_response(str(e), status_code=500)


@jira_bp.route('/project-forecasts/<project_key>', methods=['GET'])
def get_project_forecasts(project_key):
    """Get monthly forecasts for a project (rolling 6 months from current month)."""
    try:
        from sqlalchemy import text
        from datetime import datetime
        from dateutil.relativedelta import relativedelta

        engine = get_engine()
        now = datetime.now()
        current_month = datetime(now.year, now.month, 1).date()

        # Calculate 6 months forward
        months = []
        for i in range(6):
            month = (datetime(now.year, now.month, 1) + relativedelta(months=i)).date()
            months.append(month)

        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT month_year, forecasted_hours, actual_monthly_hours
                FROM project_monthly_forecast
                WHERE project_key = :project_key
                AND month_year >= :start_month
                ORDER BY month_year ASC
            """), {
                "project_key": project_key,
                "start_month": current_month
            })

            existing_forecasts = {row[0]: {"forecasted_hours": float(row[1]) if row[1] else 0, "actual_monthly_hours": float(row[2]) if row[2] else 0} for row in result}

        # Build response with all 6 months
        forecasts = []
        for month in months:
            forecast_data = existing_forecasts.get(month, {"forecasted_hours": 0, "actual_monthly_hours": 0})
            forecasts.append({
                "month_year": month.isoformat(),
                "forecasted_hours": forecast_data["forecasted_hours"],
                "actual_monthly_hours": forecast_data["actual_monthly_hours"]
            })

        return success_response(data={'forecasts': forecasts})

    except Exception as e:
        logger.error(f"Error fetching forecasts for project {project_key}: {e}")
        return error_response(str(e), status_code=500)


@jira_bp.route('/project-forecasts/<project_key>', methods=['PUT'])
def update_project_forecasts(project_key):
    """Update monthly forecasts for a project."""
    try:
        data = request.json
        forecasts = data.get('forecasts', [])

        from sqlalchemy import text
        engine = get_engine()

        with engine.connect() as conn:
            for forecast in forecasts:
                month_year = forecast.get('month_year')
                forecasted_hours = forecast.get('forecasted_hours', 0)

                conn.execute(text("""
                    INSERT INTO project_monthly_forecast
                        (project_key, month_year, forecasted_hours, updated_at)
                    VALUES
                        (:project_key, :month_year, :forecasted_hours, NOW())
                    ON CONFLICT (project_key, month_year)
                    DO UPDATE SET
                        forecasted_hours = :forecasted_hours,
                        updated_at = NOW()
                """), {
                    "project_key": project_key,
                    "month_year": month_year,
                    "forecasted_hours": forecasted_hours
                })

            conn.commit()

        return success_response(message='Forecasts updated successfully')

    except Exception as e:
        logger.error(f"Error updating forecasts for project {project_key}: {e}")
        return error_response(str(e), status_code=500)
