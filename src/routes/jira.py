"""Jira integration API endpoints."""

from flask import Blueprint, jsonify, request
from datetime import datetime
import logging
import asyncio

from config.settings import settings
from src.integrations.jira_mcp import JiraMCPClient
from src.utils.database import get_engine
from src.utils.cache_manager import cached_endpoint, invalidate_cache

logger = logging.getLogger(__name__)

# Create blueprint
jira_bp = Blueprint("jira", __name__, url_prefix="/api/jira")


# Import response helpers
def success_response(data=None, message=None, status_code=200):
    """Standard success response format."""
    response = {"success": True}
    if data is not None:
        response["data"] = data
    if message is not None:
        response["message"] = message
    return jsonify(response), status_code


def error_response(error, status_code=500, details=None):
    """Standard error response format."""
    response = {"success": False, "error": str(error)}
    if details is not None:
        response["details"] = details
    return jsonify(response), status_code


# =============================================================================
# API Routes
# =============================================================================


@jira_bp.route("/projects", methods=["GET"])
@cached_endpoint("projects", ttl=3600, user_specific=False)
def get_jira_projects():
    """Get all Jira projects with local database enhancements.

    Cached for 1 hour (3600 seconds) with global caching (not user-specific).
    Cache is invalidated when projects are updated.
    """
    try:
        # Check if Jira credentials are configured
        if (
            not settings.jira.url
            or not settings.jira.username
            or not settings.jira.api_token
        ):
            logger.error("Jira credentials not configured")
            return error_response("Jira credentials not configured", status_code=500)

        logger.info(f"Fetching projects from Jira URL: {settings.jira.url}")

        # Fetch projects from Jira
        async def fetch_projects():
            async with JiraMCPClient(
                jira_url=settings.jira.url,
                username=settings.jira.username,
                api_token=settings.jira.api_token,
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

                # ✅ PERFORMANCE FIX: Use single batch query instead of N+1 queries
                # Extract all project keys for batch query
                project_keys = [project["key"] for project in jira_projects]

                # Fetch all project data in a single query
                if project_keys:
                    results = conn.execute(
                        text(
                            """
                        SELECT
                            p.key,
                            p.is_active,
                            p.project_work_type,
                            p.description,
                            p.weekly_meeting_day,
                            p.retainer_hours,
                            p.total_hours,
                            p.send_meeting_emails,
                            p.start_date,
                            p.launch_date,
                            pmf.forecasted_hours,
                            pmf.actual_monthly_hours
                        FROM projects p
                        LEFT JOIN project_monthly_forecast pmf
                            ON p.key = pmf.project_key
                            AND pmf.month_year = :current_month
                        WHERE p.key = ANY(:project_keys)
                    """
                        ),
                        {"project_keys": project_keys, "current_month": current_month},
                    ).fetchall()

                    # Fetch keywords for all projects
                    keywords_results = conn.execute(
                        text(
                            """
                        SELECT project_key, array_agg(keyword) as keywords
                        FROM project_keywords
                        WHERE project_key = ANY(:project_keys)
                        GROUP BY project_key
                    """
                        ),
                        {"project_keys": project_keys},
                    ).fetchall()

                    # Build keywords lookup dictionary
                    keywords_map = {}
                    for row in keywords_results:
                        keywords_map[row[0]] = row[1] if row[1] else []

                    # Build lookup dictionary for O(1) access: project_key -> database_data
                    project_data_map = {}
                    for row in results:
                        project_key = row[0]
                        project_data_map[project_key] = {
                            "is_active": bool(row[1]) if row[1] is not None else True,
                            "project_work_type": row[2],
                            "description": row[3],
                            "weekly_meeting_day": row[4],
                            "retainer_hours": float(row[5]) if row[5] else 0,
                            "total_hours": float(row[6]) if row[6] else 0,
                            "send_meeting_emails": (
                                bool(row[7]) if row[7] is not None else False
                            ),
                            "start_date": row[8].isoformat() if row[8] else None,
                            "launch_date": row[9].isoformat() if row[9] else None,
                            "forecasted_hours_month": float(row[10]) if row[10] else 0,
                            "current_month_hours": float(row[11]) if row[11] else 0,
                            "keywords": keywords_map.get(project_key, []),
                        }

                    # Merge Jira data with database data
                    for project in jira_projects:
                        enhanced_project = project.copy()
                        project_key = project["key"]

                        if project_key in project_data_map:
                            # Merge database data
                            enhanced_project.update(project_data_map[project_key])
                        else:
                            # No database record - use defaults
                            enhanced_project["is_active"] = True
                            enhanced_project["forecasted_hours_month"] = 0
                            enhanced_project["current_month_hours"] = 0
                            enhanced_project["keywords"] = keywords_map.get(
                                project_key, []
                            )

                        enhanced_projects.append(enhanced_project)
                else:
                    # No projects to enhance
                    enhanced_projects = jira_projects
        except Exception as e:
            # If database operations fail entirely, return projects without enhancements
            logger.warning(f"Could not enhance projects with database data: {e}")
            enhanced_projects = jira_projects

        # Filter by is_active if requested
        is_active_param = request.args.get("is_active")
        if is_active_param is not None:
            is_active_bool = is_active_param.lower() in ["true", "1", "yes"]
            enhanced_projects = [
                p for p in enhanced_projects if p.get("is_active") == is_active_bool
            ]

        return success_response(data={"projects": enhanced_projects})
    except Exception as e:
        logger.error(f"Error fetching Jira projects: {e}")
        return error_response(str(e), status_code=500)


@jira_bp.route("/projects/<project_key>", methods=["GET"])
def get_jira_project(project_key):
    """Get a single Jira project by key with local database enhancements."""
    try:
        # Check if Jira credentials are configured
        if (
            not settings.jira.url
            or not settings.jira.username
            or not settings.jira.api_token
        ):
            logger.error("Jira credentials not configured")
            return error_response("Jira credentials not configured", status_code=500)

        logger.info(f"Fetching project {project_key} from Jira")

        # Fetch project from Jira
        async def fetch_project():
            async with JiraMCPClient(
                jira_url=settings.jira.url,
                username=settings.jira.username,
                api_token=settings.jira.api_token,
            ) as jira_client:
                projects = await jira_client.get_projects()
                # Find the specific project by key
                for project in projects:
                    if project.get("key") == project_key:
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
                result = conn.execute(
                    text(
                        """
                    SELECT
                        p.is_active,
                        p.project_work_type,
                        p.description,
                        p.weekly_meeting_day,
                        p.retainer_hours,
                        p.total_hours,
                        p.cumulative_hours,
                        p.send_meeting_emails,
                        p.start_date,
                        p.launch_date,
                        pmf.forecasted_hours,
                        pmf.actual_monthly_hours
                    FROM projects p
                    LEFT JOIN project_monthly_forecast pmf
                        ON p.key = pmf.project_key
                        AND pmf.month_year = :current_month
                    WHERE p.key = :key
                """
                    ),
                    {"key": project_key, "current_month": current_month},
                ).fetchone()

                if result:
                    enhanced_project["is_active"] = (
                        bool(result[0]) if result[0] is not None else True
                    )
                    enhanced_project["project_work_type"] = result[1]
                    enhanced_project["description"] = result[2]
                    enhanced_project["weekly_meeting_day"] = result[3]
                    enhanced_project["retainer_hours"] = (
                        float(result[4]) if result[4] else 0
                    )
                    enhanced_project["total_hours"] = (
                        float(result[5]) if result[5] else 0
                    )
                    enhanced_project["cumulative_hours"] = (
                        float(result[6]) if result[6] else 0
                    )
                    enhanced_project["send_meeting_emails"] = (
                        bool(result[7]) if result[7] is not None else False
                    )
                    enhanced_project["start_date"] = (
                        result[8].isoformat() if result[8] else None
                    )
                    enhanced_project["launch_date"] = (
                        result[9].isoformat() if result[9] else None
                    )
                    enhanced_project["forecasted_hours_month"] = (
                        float(result[10]) if result[10] else 0
                    )
                    enhanced_project["current_month_hours"] = (
                        float(result[11]) if result[11] else 0
                    )
                else:
                    # No database record - use defaults
                    enhanced_project["is_active"] = True
                    enhanced_project["cumulative_hours"] = 0
                    enhanced_project["forecasted_hours_month"] = 0
                    enhanced_project["current_month_hours"] = 0
        except Exception as e:
            # If database operations fail, use defaults
            logger.warning(f"Could not enhance project with database data: {e}")
            enhanced_project["is_active"] = True
            enhanced_project["project_work_type"] = "project-based"
            enhanced_project["total_hours"] = 0
            enhanced_project["cumulative_hours"] = 0
            enhanced_project["weekly_meeting_day"] = None
            enhanced_project["retainer_hours"] = 0
            enhanced_project["description"] = None
            enhanced_project["send_meeting_emails"] = False
            enhanced_project["start_date"] = None
            enhanced_project["launch_date"] = None
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
        project_key = request.args.get("project")

        async def fetch_issue_types():
            async with JiraMCPClient(
                jira_url=settings.jira.url,
                username=settings.jira.username,
                api_token=settings.jira.api_token,
            ) as jira_client:
                return await jira_client.get_issue_types(project_key)

        issue_types = asyncio.run(fetch_issue_types())
        return success_response(data={"issue_types": issue_types})
    except Exception as e:
        logger.error(f"Error fetching Jira issue types: {e}")
        return error_response(str(e), status_code=500)


@jira_bp.route("/users", methods=["GET"])
def get_jira_users():
    """Get assignable users for a project."""
    try:
        project_key = request.args.get("project")
        max_results = int(request.args.get("max_results", 200))

        async def fetch_users():
            async with JiraMCPClient(
                jira_url=settings.jira.url,
                username=settings.jira.username,
                api_token=settings.jira.api_token,
            ) as jira_client:
                return await jira_client.get_users(project_key, max_results)

        users = asyncio.run(fetch_users())
        return success_response(data={"users": users})
    except Exception as e:
        logger.error(f"Error fetching Jira users: {e}")
        return error_response(str(e), status_code=500)


@jira_bp.route("/users/search", methods=["GET"])
def search_jira_users():
    """Search users with autocomplete - requires minimum 3 characters."""
    try:
        query = request.args.get("q", "").strip()

        # Require minimum 3 characters
        if len(query) < 3:
            return success_response(data={"users": []})

        project_key = request.args.get("project")
        max_results = int(
            request.args.get("max_results", 20)
        )  # Smaller limit for autocomplete

        async def fetch_users():
            async with JiraMCPClient(
                jira_url=settings.jira.url,
                username=settings.jira.username,
                api_token=settings.jira.api_token,
            ) as jira_client:
                return await jira_client.search_users(query, project_key, max_results)

        users = asyncio.run(fetch_users())
        return success_response(data={"users": users})
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
                api_token=settings.jira.api_token,
            ) as jira_client:
                return await jira_client.get_priorities()

        priorities = asyncio.run(fetch_priorities())
        return success_response(data={"priorities": priorities})
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
                api_token=settings.jira.api_token,
            ) as jira_client:
                return await jira_client.get_project_metadata(project_key)

        metadata = asyncio.run(fetch_metadata())
        return success_response(data={"metadata": metadata})
    except Exception as e:
        logger.error(f"Error fetching Jira metadata: {e}")
        return error_response(str(e), status_code=500)


@jira_bp.route("/projects/<project_key>", methods=["PUT"])
def update_project(project_key):
    """Update project data in local database."""
    try:
        data = request.json
        print(
            f"[DEBUG] update_project called for {project_key} with data: {data}",
            flush=True,
        )

        # Connect to database
        from sqlalchemy import text
        from datetime import datetime

        engine = get_engine()

        # Get current month for forecast table
        now = datetime.now()
        current_month = datetime(now.year, now.month, 1).date()

        with engine.begin() as conn:
            # Check if project exists in local DB
            result = conn.execute(
                text(
                    """
                SELECT * FROM projects WHERE key = :key
            """
                ),
                {"key": project_key},
            )

            existing = result.fetchone()

            if existing:
                # Update existing project - DYNAMIC UPDATE (only update provided fields)
                update_fields = []
                update_params = {"key": project_key}

                # Only include fields that were actually sent from the frontend
                if "is_active" in data:
                    update_fields.append("is_active = :is_active")
                    update_params["is_active"] = data["is_active"]

                if "project_work_type" in data:
                    update_fields.append("project_work_type = :project_work_type")
                    update_params["project_work_type"] = data["project_work_type"]

                if "total_hours" in data:
                    update_fields.append("total_hours = :total_hours")
                    update_params["total_hours"] = data["total_hours"]

                if "retainer_hours" in data:
                    update_fields.append("retainer_hours = :retainer_hours")
                    update_params["retainer_hours"] = data["retainer_hours"]

                if "name" in data:
                    update_fields.append("name = :name")
                    update_params["name"] = data["name"]

                if "weekly_meeting_day" in data:
                    update_fields.append("weekly_meeting_day = :weekly_meeting_day")
                    update_params["weekly_meeting_day"] = data["weekly_meeting_day"]

                if "description" in data:
                    update_fields.append("description = :description")
                    update_params["description"] = data["description"]

                if "send_meeting_emails" in data:
                    update_fields.append("send_meeting_emails = :send_meeting_emails")
                    update_params["send_meeting_emails"] = data["send_meeting_emails"]

                if "start_date" in data:
                    update_fields.append("start_date = :start_date")
                    update_params["start_date"] = data["start_date"]

                if "launch_date" in data:
                    update_fields.append("launch_date = :launch_date")
                    update_params["launch_date"] = data["launch_date"]

                # Always update the timestamp
                if update_fields:
                    update_fields.append("updated_at = CURRENT_TIMESTAMP")
                    query = f"UPDATE projects SET {', '.join(update_fields)} WHERE key = :key"
                    conn.execute(text(query), update_params)
            else:
                # Insert new project
                conn.execute(
                    text(
                        """
                    INSERT INTO projects (key, name, is_active, project_work_type, total_hours, retainer_hours, weekly_meeting_day, send_meeting_emails, created_at, updated_at)
                    VALUES (:key, :name, :is_active, :project_work_type, :total_hours, :retainer_hours, :weekly_meeting_day, :send_meeting_emails, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """
                    ),
                    {
                        "key": project_key,
                        "name": data.get("name", "Unknown"),
                        "is_active": data.get("is_active", True),
                        "project_work_type": data.get(
                            "project_work_type", "project-based"
                        ),
                        "total_hours": data.get("total_hours", 0),
                        "retainer_hours": data.get("retainer_hours", 0),
                        "weekly_meeting_day": data.get("weekly_meeting_day"),
                        "send_meeting_emails": data.get("send_meeting_emails", False),
                    },
                )

            # Upsert forecasted hours for current month if provided
            if "forecasted_hours_month" in data:
                conn.execute(
                    text(
                        """
                    INSERT INTO project_monthly_forecast
                        (project_key, month_year, forecasted_hours, updated_at)
                    VALUES
                        (:project_key, :month_year, :forecasted_hours, NOW())
                    ON CONFLICT (project_key, month_year)
                    DO UPDATE SET
                        forecasted_hours = :forecasted_hours,
                        updated_at = NOW()
                """
                    ),
                    {
                        "project_key": project_key,
                        "month_year": current_month,
                        "forecasted_hours": data.get("forecasted_hours_month", 0),
                    },
                )

            # Fetch and return updated project data with explicit column selection
            try:
                result = conn.execute(
                    text(
                        """
                    SELECT key, name, is_active, project_work_type, total_hours, retainer_hours,
                           weekly_meeting_day, send_meeting_emails, start_date, launch_date, updated_at
                    FROM projects
                    WHERE key = :key
                """
                    ),
                    {"key": project_key},
                )
                updated_project = result.fetchone()

                if updated_project:
                    project_dict = {
                        "key": updated_project[0],
                        "name": updated_project[1],
                        "is_active": updated_project[2],
                        "project_work_type": updated_project[3],
                        "total_hours": updated_project[4],
                        "retainer_hours": updated_project[5],
                        "weekly_meeting_day": updated_project[6],
                        "send_meeting_emails": updated_project[7],
                        "start_date": (
                            updated_project[8].isoformat()
                            if updated_project[8]
                            else None
                        ),
                        "launch_date": (
                            updated_project[9].isoformat()
                            if updated_project[9]
                            else None
                        ),
                        "updated_at": (
                            updated_project[10].isoformat()
                            if updated_project[10]
                            else None
                        ),
                    }
                    return success_response(
                        data=project_dict, message="Project updated successfully"
                    )
            except (IndexError, TypeError, AttributeError) as e:
                # If we can't build the full project dict (e.g., in tests or schema mismatch), return simple success
                logger.warning(
                    f"Could not return full project data for {project_key}: {e}"
                )
                pass

            return success_response(message="Project updated successfully")

    except Exception as e:
        logger.error(f"Error updating project {project_key}: {e}")
        return error_response(str(e), status_code=500)


@jira_bp.route("/projects/<project_key>/epics", methods=["GET"])
def get_project_epics(project_key):
    """Get all epics for a specific project from Jira.

    Returns list of epics with their key, summary, status, and other metadata.
    """
    try:
        # Check if Jira credentials are configured
        if (
            not settings.jira.url
            or not settings.jira.username
            or not settings.jira.api_token
        ):
            logger.error("Jira credentials not configured")
            return error_response("Jira credentials not configured", status_code=500)

        logger.info(f"Fetching epics for project {project_key}")

        # Fetch epics from Jira using JQL
        async def fetch_epics():
            async with JiraMCPClient(
                jira_url=settings.jira.url,
                username=settings.jira.username,
                api_token=settings.jira.api_token,
            ) as jira_client:
                # JQL to get all epics for the project
                jql = f"project = {project_key} AND issuetype = Epic ORDER BY created DESC"
                issues = await jira_client.search_tickets(jql, max_results=1000)
                return issues

        epics = asyncio.run(fetch_epics())

        # Format epic data for frontend
        formatted_epics = []
        for epic in epics:
            fields = epic.get("fields", {})
            formatted_epics.append(
                {
                    "key": epic.get("key"),
                    "summary": fields.get("summary", ""),
                    "status": fields.get("status", {}).get("name", "Unknown"),
                    "created": fields.get("created"),
                    "updated": fields.get("updated"),
                    "assignee": (
                        fields.get("assignee", {}).get("displayName")
                        if fields.get("assignee")
                        else None
                    ),
                    "description": fields.get("description", ""),
                }
            )

        logger.info(f"Retrieved {len(formatted_epics)} epics for project {project_key}")
        return success_response(
            data={"epics": formatted_epics, "count": len(formatted_epics)}
        )

    except Exception as e:
        logger.error(f"Error fetching epics for project {project_key}: {e}")
        return error_response(str(e), status_code=500)


@jira_bp.route("/projects/<project_key>/epics/import", methods=["POST"])
def import_project_epics(project_key):
    """Import Jira epics as budget entries.

    This endpoint fetches all epics from Jira for the given project and creates
    or updates budget entries with estimated_hours = 0 (to be filled in by user).
    Skips epics that already have budget entries.

    Returns:
        - created: number of new budget entries created
        - skipped: number of epics that already had budgets
        - epics: list of all imported epics with their budget status
    """
    try:
        from src.utils.database import get_session
        from src.models import EpicBudget
        from decimal import Decimal

        # Check if Jira credentials are configured
        if (
            not settings.jira.url
            or not settings.jira.username
            or not settings.jira.api_token
        ):
            logger.error("Jira credentials not configured")
            return error_response("Jira credentials not configured", status_code=500)

        logger.info(f"Importing epics as budgets for project {project_key}")

        # Fetch epics from Jira using JQL
        async def fetch_epics():
            async with JiraMCPClient(
                jira_url=settings.jira.url,
                username=settings.jira.username,
                api_token=settings.jira.api_token,
            ) as jira_client:
                # JQL to get all epics for the project
                jql = f"project = {project_key} AND issuetype = Epic ORDER BY created DESC"
                issues = await jira_client.search_tickets(jql, max_results=1000)
                return issues

        epics = asyncio.run(fetch_epics())

        if not epics:
            logger.info(f"No epics found for project {project_key}")
            return success_response(
                data={
                    "created": 0,
                    "skipped": 0,
                    "epics": [],
                    "message": "No epics found in Jira for this project",
                }
            )

        session = get_session()
        created_count = 0
        skipped_count = 0
        imported_epics = []

        try:
            for epic in epics:
                fields = epic.get("fields", {})
                epic_key = epic.get("key")
                epic_summary = fields.get("summary", "")

                if not epic_key:
                    continue

                # Check if budget already exists
                existing = (
                    session.query(EpicBudget)
                    .filter_by(project_key=project_key, epic_key=epic_key)
                    .first()
                )

                if existing:
                    skipped_count += 1
                    imported_epics.append(
                        {
                            "epic_key": epic_key,
                            "epic_summary": epic_summary,
                            "status": "skipped",
                            "reason": "Budget already exists",
                        }
                    )
                else:
                    # Create new budget with 0 hours (user will fill in estimate)
                    new_budget = EpicBudget(
                        project_key=project_key,
                        epic_key=epic_key,
                        epic_summary=epic_summary,
                        estimated_hours=Decimal("0"),
                    )
                    session.add(new_budget)
                    created_count += 1
                    imported_epics.append(
                        {
                            "epic_key": epic_key,
                            "epic_summary": epic_summary,
                            "status": "created",
                            "reason": "New budget entry created",
                        }
                    )

            session.commit()

            logger.info(
                f"Import complete: {created_count} created, {skipped_count} skipped"
            )
            return success_response(
                data={
                    "created": created_count,
                    "skipped": skipped_count,
                    "epics": imported_epics,
                    "message": f"Successfully imported {created_count} epics as budgets ({skipped_count} already existed)",
                }
            )

        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    except Exception as e:
        logger.error(f"Error importing epics for project {project_key}: {e}")
        return error_response(str(e), status_code=500)


@jira_bp.route("/celery/health", methods=["GET"])
def celery_health_check():
    """Check if Celery and Redis are responsive."""
    try:
        from src.tasks.celery_app import celery_app

        # Try to ping Celery via Redis
        inspector = celery_app.control.inspect()
        active_workers = inspector.active()

        if not active_workers:
            return error_response(
                "No Celery workers are currently active. Background tasks cannot be processed.",
                status_code=503,
            )

        worker_count = len(active_workers)
        logger.info(f"✅ Celery health check passed: {worker_count} worker(s) active")

        return success_response(
            data={
                "status": "healthy",
                "workers": worker_count,
                "worker_names": list(active_workers.keys()),
            }
        )

    except Exception as e:
        logger.error(f"❌ Celery health check failed: {e}", exc_info=True)
        return error_response(
            f"Celery health check failed: {str(e)}. Background worker may be offline.",
            status_code=503,
        )


@jira_bp.route("/celery/task-status/<task_id>", methods=["GET"])
def get_task_status(task_id):
    """Get the status of a Celery task by ID."""
    try:
        from celery.result import AsyncResult
        from src.tasks.celery_app import celery_app

        task_result = AsyncResult(task_id, app=celery_app)

        response = {
            "task_id": task_id,
            "state": task_result.state,
            "ready": task_result.ready(),
            "successful": task_result.successful() if task_result.ready() else None,
            "failed": task_result.failed() if task_result.ready() else None,
        }

        # Add progress info if task is running
        if task_result.state == "PROGRESS" and task_result.info:
            response["progress"] = {
                "current": task_result.info.get("current", 0),
                "total": task_result.info.get("total", 0),
                "percent": (
                    round(
                        (
                            task_result.info.get("current", 0)
                            / task_result.info.get("total", 1)
                        )
                        * 100,
                        1,
                    )
                    if task_result.info.get("total", 0) > 0
                    else 0
                ),
                "message": task_result.info.get("message", ""),
            }

        # Add result if task completed
        if task_result.ready():
            if task_result.successful():
                response["result"] = task_result.result
            elif task_result.failed():
                response["error"] = (
                    str(task_result.info) if task_result.info else "Task failed"
                )

        return success_response(data=response)

    except Exception as e:
        logger.error(f"Error getting task status for {task_id}: {e}", exc_info=True)
        return error_response(str(e), status_code=500)


@jira_bp.route("/projects/<project_key>/sync-hours", methods=["POST"])
def sync_project_hours(project_key):
    """Sync epic hours from Tempo for a specific project.

    This triggers a Celery task to perform Tempo worklog analysis for the project
    and populates the epic_hours table with monthly breakdowns of actual hours per epic.

    The task runs asynchronously via Celery to ensure completion even if the web
    request times out or the process is recycled.
    """
    try:
        from src.tasks.notification_tasks import sync_project_epic_hours
        from src.tasks.celery_app import celery_app

        # Note: Health check via inspector.active() doesn't work reliably with GCP Pub/Sub
        # We'll queue the task and let Celery handle failures gracefully
        logger.info(f"Queueing epic hours sync task for project {project_key}")

        # Queue the Celery task
        task = sync_project_epic_hours.delay(project_key)

        logger.info(f"Epic hours sync task queued with ID: {task.id}")

        return success_response(
            data={
                "message": f"Started syncing epic hours for {project_key}. This will take a few minutes.",
                "project_key": project_key,
                "task_id": task.id,
            }
        )

    except Exception as e:
        logger.error(
            f"Error queueing sync task for project {project_key}: {e}", exc_info=True
        )
        return error_response(str(e), status_code=500)


@jira_bp.route("/project-forecasts/batch", methods=["POST"])
def get_project_forecasts_batch():
    """Get monthly forecasts for multiple projects in a single request (rolling 6 months from current month)."""
    try:
        from sqlalchemy import text
        from datetime import datetime
        from dateutil.relativedelta import relativedelta

        data = request.json
        project_keys = data.get("project_keys", [])

        if not project_keys:
            return error_response("project_keys is required", status_code=400)

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
            result = conn.execute(
                text(
                    """
                SELECT project_key, month_year, forecasted_hours, actual_monthly_hours
                FROM project_monthly_forecast
                WHERE project_key = ANY(:project_keys)
                AND month_year >= :start_month
                ORDER BY project_key, month_year ASC
            """
                ),
                {"project_keys": project_keys, "start_month": current_month},
            )

            # Group by project_key
            forecasts_by_project = {}
            for row in result:
                project_key = row[0]
                month_year = row[1]
                if project_key not in forecasts_by_project:
                    forecasts_by_project[project_key] = {}
                forecasts_by_project[project_key][month_year] = {
                    "forecasted_hours": float(row[2]) if row[2] else 0,
                    "actual_monthly_hours": float(row[3]) if row[3] else 0,
                }

        # Build response with all 6 months for each project
        response_data = {}
        for project_key in project_keys:
            forecasts = []
            existing_forecasts = forecasts_by_project.get(project_key, {})
            for month in months:
                forecast_data = existing_forecasts.get(
                    month, {"forecasted_hours": 0, "actual_monthly_hours": 0}
                )
                forecasts.append(
                    {
                        "month_year": month.isoformat(),
                        "forecasted_hours": forecast_data["forecasted_hours"],
                        "actual_monthly_hours": forecast_data["actual_monthly_hours"],
                    }
                )
            response_data[project_key] = forecasts

        return success_response(data={"forecasts": response_data})

    except Exception as e:
        logger.error(f"Error fetching batch forecasts: {e}")
        return error_response(str(e), status_code=500)


@jira_bp.route("/project-forecasts/<project_key>", methods=["GET"])
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
            result = conn.execute(
                text(
                    """
                SELECT month_year, forecasted_hours, actual_monthly_hours
                FROM project_monthly_forecast
                WHERE project_key = :project_key
                AND month_year >= :start_month
                ORDER BY month_year ASC
            """
                ),
                {"project_key": project_key, "start_month": current_month},
            )

            existing_forecasts = {
                row[0]: {
                    "forecasted_hours": float(row[1]) if row[1] else 0,
                    "actual_monthly_hours": float(row[2]) if row[2] else 0,
                }
                for row in result
            }

        # Build response with all 6 months
        forecasts = []
        for month in months:
            forecast_data = existing_forecasts.get(
                month, {"forecasted_hours": 0, "actual_monthly_hours": 0}
            )
            forecasts.append(
                {
                    "month_year": month.isoformat(),
                    "forecasted_hours": forecast_data["forecasted_hours"],
                    "actual_monthly_hours": forecast_data["actual_monthly_hours"],
                }
            )

        return success_response(data={"forecasts": forecasts})

    except Exception as e:
        logger.error(f"Error fetching forecasts for project {project_key}: {e}")
        return error_response(str(e), status_code=500)


@jira_bp.route("/project-forecasts/<project_key>", methods=["PUT"])
def update_project_forecasts(project_key):
    """Update monthly forecasts for a project."""
    try:
        data = request.json
        forecasts = data.get("forecasts", [])

        from sqlalchemy import text

        engine = get_engine()

        # Use engine.begin() instead of connect() for auto-commit
        with engine.begin() as conn:
            # Ensure project exists in projects table to avoid foreign key violation
            # This handles cases where projects are renamed or newly created in Jira
            result = conn.execute(
                text("SELECT key FROM projects WHERE key = :key"), {"key": project_key}
            )

            if not result.fetchone():
                logger.warning(
                    f"Project {project_key} not found in projects table - auto-creating"
                )

                # Fetch project data from Jira to get the name
                try:
                    from src.integrations.jira_mcp import JiraMCPClient
                    import asyncio

                    jira_client = JiraMCPClient()
                    jira_projects = asyncio.run(jira_client.get_projects())

                    # Find matching project
                    project_name = project_key  # Default to key if not found
                    for proj in jira_projects:
                        if proj.get("key") == project_key:
                            project_name = proj.get("name", project_key)
                            break

                    # Insert project with basic data
                    conn.execute(
                        text(
                            """
                            INSERT INTO projects (key, name, is_active, created_at, updated_at)
                            VALUES (:key, :name, true, NOW(), NOW())
                        """
                        ),
                        {"key": project_key, "name": project_name},
                    )
                    logger.info(f"Auto-created project {project_key} in projects table")

                except Exception as sync_error:
                    logger.error(
                        f"Failed to auto-create project {project_key}: {sync_error}"
                    )
                    raise

            # Now insert/update forecasts
            for forecast in forecasts:
                month_year = forecast.get("month_year")
                forecasted_hours = forecast.get("forecasted_hours", 0)

                conn.execute(
                    text(
                        """
                    INSERT INTO project_monthly_forecast
                        (project_key, month_year, forecasted_hours, updated_at)
                    VALUES
                        (:project_key, :month_year, :forecasted_hours, NOW())
                    ON CONFLICT (project_key, month_year)
                    DO UPDATE SET
                        forecasted_hours = :forecasted_hours,
                        updated_at = NOW()
                """
                    ),
                    {
                        "project_key": project_key,
                        "month_year": month_year,
                        "forecasted_hours": forecasted_hours,
                    },
                )

        return success_response(message="Forecasts updated successfully")

    except Exception as e:
        logger.error(f"Error updating forecasts for project {project_key}: {e}")
        return error_response(str(e), status_code=500)


@jira_bp.route("/tickets", methods=["POST"])
def create_jira_ticket():
    """Create a single Jira ticket from meeting action item.

    Expected JSON payload:
    {
        "title": "Ticket summary",
        "description": "Ticket description",
        "project": "PROJECT_KEY",
        "issueType": "Task",
        "priority": "Medium",
        "assignee": "user@example.com" (optional)
    }
    """
    try:
        data = request.json

        # Validate required fields
        if not data.get("title"):
            return error_response("Title is required", status_code=400)
        if not data.get("project"):
            return error_response("Project is required", status_code=400)
        if not data.get("issueType"):
            return error_response("Issue type is required", status_code=400)

        # Create Jira ticket object
        from src.integrations.jira_mcp import JiraTicket

        ticket = JiraTicket(
            summary=data["title"],
            description=data.get("description", ""),
            project_key=data["project"],
            issue_type=data["issueType"],
            priority=data.get("priority", "Medium"),
            assignee=data.get("assignee"),
        )

        # Initialize Jira client and create the ticket
        async def create_ticket_async():
            async with JiraMCPClient(
                jira_url=settings.jira.url,
                username=settings.jira.username,
                api_token=settings.jira.api_token,
            ) as jira_client:
                return await jira_client.create_ticket(ticket)

        result = asyncio.run(create_ticket_async())

        logger.info(f"Created Jira ticket: {result.get('key')} for '{data['title']}'")

        return success_response(
            data={
                "ticket_key": result.get("key"),
                "ticket_url": f"{settings.jira.url}/browse/{result.get('key')}",
            },
            message=f"Successfully created ticket {result.get('key')}",
        )

    except Exception as e:
        logger.error(f"Error creating Jira ticket: {e}")
        import traceback

        traceback.print_exc()
        return error_response(str(e), status_code=500)
