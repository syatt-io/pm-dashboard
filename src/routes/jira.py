"""Jira integration API endpoints."""

from flask import Blueprint, jsonify, request
from datetime import datetime
import logging
import asyncio

from config.settings import settings
from src.integrations.jira_mcp import JiraMCPClient

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
                for project in jira_projects:
                    enhanced_project = project.copy()
                    try:
                        # Get local project data (may fail if table doesn't exist)
                        result = conn.execute(text(
                            "SELECT forecasted_hours_month, is_active, project_work_type, total_hours, current_month_hours, cumulative_hours, slack_channel, weekly_meeting_day FROM projects WHERE key = :key"
                        ), {"key": project["key"]}).fetchone()

                        if result:
                            enhanced_project["forecasted_hours_month"] = float(result[0]) if result[0] else 0
                            enhanced_project["is_active"] = bool(result[1]) if result[1] is not None else True
                            enhanced_project["project_work_type"] = result[2] if result[2] else 'project-based'
                            enhanced_project["total_hours"] = float(result[3]) if result[3] else 0
                            enhanced_project["current_month_hours"] = float(result[4]) if result[4] else 0
                            enhanced_project["cumulative_hours"] = float(result[5]) if result[5] else 0
                            enhanced_project["slack_channel"] = result[6] if result[6] else None
                            enhanced_project["weekly_meeting_day"] = result[7] if result[7] else None
                        else:
                            # No database record - use defaults
                            enhanced_project["forecasted_hours_month"] = 0
                            enhanced_project["is_active"] = True
                            enhanced_project["project_work_type"] = 'project-based'
                            enhanced_project["total_hours"] = 0
                            enhanced_project["current_month_hours"] = 0
                            enhanced_project["cumulative_hours"] = 0
                            enhanced_project["slack_channel"] = None
                            enhanced_project["weekly_meeting_day"] = None
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
        engine = get_engine()

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
                        forecasted_hours_month = :forecasted_hours_month,
                        project_work_type = :project_work_type,
                        total_hours = :total_hours,
                        name = :name,
                        slack_channel = :slack_channel,
                        weekly_meeting_day = :weekly_meeting_day,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE key = :key
                """), {
                    "key": project_key,
                    "is_active": data.get('is_active', True),
                    "forecasted_hours_month": data.get('forecasted_hours_month', 0),
                    "project_work_type": data.get('project_work_type', 'ongoing'),
                    "total_hours": data.get('total_hours', 0),
                    "name": data.get('name', existing[1] if existing else 'Unknown'),
                    "slack_channel": data.get('slack_channel'),
                    "weekly_meeting_day": data.get('weekly_meeting_day')
                })
            else:
                # Insert new project
                conn.execute(text("""
                    INSERT INTO projects (key, name, is_active, forecasted_hours_month, project_work_type, total_hours, slack_channel, weekly_meeting_day)
                    VALUES (:key, :name, :is_active, :forecasted_hours_month, :project_work_type, :total_hours, :slack_channel, :weekly_meeting_day)
                """), {
                    "key": project_key,
                    "name": data.get('name', 'Unknown'),
                    "is_active": data.get('is_active', True),
                    "forecasted_hours_month": data.get('forecasted_hours_month', 0),
                    "project_work_type": data.get('project_work_type', 'ongoing'),
                    "total_hours": data.get('total_hours', 0),
                    "slack_channel": data.get('slack_channel'),
                    "weekly_meeting_day": data.get('weekly_meeting_day')
                })

            conn.commit()

        return success_response(message='Project updated successfully')

    except Exception as e:
        logger.error(f"Error updating project {project_key}: {e}")
        return error_response(str(e), status_code=500)
