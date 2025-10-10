"""Project management and monitoring routes."""
from flask import Blueprint, jsonify, request, session
import asyncio
import logging
from datetime import datetime, timedelta

from src.services.auth import auth_required
from src.utils.database import session_scope
from src.models.user import UserWatchedProject
from src.managers.notifications import NotificationContent

logger = logging.getLogger(__name__)

projects_bp = Blueprint('projects', __name__, url_prefix='/api')

# Dependencies injected from main app
_notifier = None


def init_projects_routes(notifier):
    """Initialize projects routes with dependencies."""
    global _notifier
    _notifier = notifier


# ============================================================================
# Watched Projects Routes
# ============================================================================

@projects_bp.route('/watched-projects', methods=['GET'])
@auth_required
def get_watched_projects(user):
    """Get user's watched projects."""
    try:
        with session_scope() as db_session:
            watched_projects = db_session.query(UserWatchedProject)\
                .filter_by(user_id=user.id)\
                .order_by(UserWatchedProject.created_at.desc())\
                .all()

            result = [wp.project_key for wp in watched_projects]

        return jsonify({
            'success': True,
            'watched_projects': result
        })

    except Exception as e:
        logger.error(f"Failed to get watched projects: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@projects_bp.route('/watched-projects/<project_key>', methods=['POST'])
@auth_required
def watch_project(user, project_key):
    """Add a project to user's watched list."""
    try:
        with session_scope() as db_session:
            # Check if already watching
            existing = db_session.query(UserWatchedProject)\
                .filter_by(user_id=user.id, project_key=project_key)\
                .first()

            if existing:
                return jsonify({'success': True, 'message': 'Already watching this project'})

            # Add new watched project
            watched_project = UserWatchedProject(
                user_id=user.id,
                project_key=project_key
            )
            db_session.add(watched_project)

        return jsonify({'success': True, 'message': f'Now watching {project_key}'})

    except Exception as e:
        logger.error(f"Failed to watch project {project_key}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@projects_bp.route('/watched-projects/<project_key>', methods=['DELETE'])
@auth_required
def unwatch_project(user, project_key):
    """Remove a project from user's watched list."""
    try:
        with session_scope() as db_session:
            watched_project = db_session.query(UserWatchedProject)\
                .filter_by(user_id=user.id, project_key=project_key)\
                .first()

            if watched_project:
                db_session.delete(watched_project)
                return jsonify({'success': True, 'message': f'Stopped watching {project_key}'})
            else:
                return jsonify({'success': False, 'message': 'Project not in watched list'})

    except Exception as e:
        logger.error(f"Failed to unwatch project {project_key}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# My Projects Routes
# ============================================================================

@projects_bp.route('/my-projects/user/<email>', methods=['GET'])
def get_user_my_projects_settings(email):
    """Get user settings by email."""
    try:
        from main import UserPreference

        with session_scope() as db_session:
            user_pref = db_session.query(UserPreference).filter_by(email=email).first()

            if user_pref:
                # Store email in session for future redirects
                session['user_email'] = email

                settings_data = {
                    'email': user_pref.email,
                    'slack_username': user_pref.slack_username,
                    'notification_cadence': user_pref.notification_cadence,
                    'selected_projects': user_pref.selected_projects or [],
                    'last_notification_sent': user_pref.last_notification_sent.isoformat() if user_pref.last_notification_sent else None
                }
                return jsonify({'success': True, 'user_settings': settings_data})
            else:
                return jsonify({'success': False, 'error': 'User not found'}), 404

    except Exception as e:
        logger.error(f"Error getting user settings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@projects_bp.route('/my-projects/user', methods=['POST'])
def save_user_settings():
    """Save or update user settings."""
    try:
        data = request.json
        email = data.get('email')

        if not email:
            return jsonify({'success': False, 'error': 'Email is required'}), 400

        from main import UserPreference
        import uuid
        from sqlalchemy import text

        with session_scope() as db_session:
            # Check if user exists
            user_pref = db_session.query(UserPreference).filter_by(email=email).first()

            if user_pref:
                # Update existing user
                user_pref.slack_username = data.get('slack_username')
                user_pref.notification_cadence = data.get('notification_cadence', 'daily')
                user_pref.selected_projects = data.get('selected_projects', [])
                user_pref.updated_at = datetime.now()
            else:
                # Create new user
                user_pref = UserPreference(
                    id=str(uuid.uuid4()),
                    email=email,
                    slack_username=data.get('slack_username'),
                    notification_cadence=data.get('notification_cadence', 'daily'),
                    selected_projects=data.get('selected_projects', []),
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                db_session.add(user_pref)

            # Handle project updates if provided
            project_updates = data.get('project_updates', [])
            if project_updates:
                for update in project_updates:
                    project_key = update.get('key')
                    project_name = update.get('name')
                    forecasted_hours = update.get('forecasted_hours_month', 0)
                    is_active = update.get('is_active', True)

                    if project_key:
                        # Insert or update project in projects table
                        db_session.execute(text("""
                            INSERT INTO projects (key, name, forecasted_hours_month, is_active, created_at, updated_at)
                            VALUES (:key, :name, :forecasted_hours, :is_active, :created_at, :updated_at)
                            ON CONFLICT(key) DO UPDATE SET
                                name = EXCLUDED.name,
                                forecasted_hours_month = EXCLUDED.forecasted_hours_month,
                                is_active = EXCLUDED.is_active,
                                updated_at = EXCLUDED.updated_at
                        """), {
                            'key': project_key,
                            'name': project_name or project_key,
                            'forecasted_hours': forecasted_hours,
                            'is_active': is_active,
                            'created_at': datetime.now(),
                            'updated_at': datetime.now()
                        })

        # Store user email in session for future redirects
        session['user_email'] = email

        return jsonify({'success': True, 'message': 'User settings saved successfully'})

    except Exception as e:
        logger.error(f"Error saving user settings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@projects_bp.route('/my-projects/test-notification', methods=['POST'])
def send_test_notification():
    """Send a test notification to user."""
    try:
        data = request.json
        email = data.get('email')

        if not email:
            return jsonify({'success': False, 'error': 'Email is required'}), 400

        if not _notifier:
            return jsonify({'success': False, 'error': 'Notifier not configured'}), 503

        # Create a test notification
        notification = NotificationContent(
            title="Test Notification - My Projects",
            body=f"This is a test notification for {email}. Your project monitoring is working correctly!",
            priority="normal"
        )

        # Send notification
        asyncio.run(_notifier.send_notification(notification, channels=["slack"]))

        return jsonify({'success': True, 'message': 'Test notification sent'})

    except Exception as e:
        logger.error(f"Error sending test notification: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@projects_bp.route('/my-projects/poll-changes', methods=['POST'])
def trigger_project_poll():
    """Manually trigger project changes polling."""
    try:
        from src.services.project_monitor import ProjectMonitor

        monitor = ProjectMonitor()
        changes = asyncio.run(monitor.run_daily_poll())

        return jsonify({'success': True, 'message': 'Project polling completed'})

    except Exception as e:
        logger.error(f"Error triggering project poll: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@projects_bp.route('/my-projects/changes/<email>', methods=['GET'])
def get_user_changes(email):
    """Get recent changes for a user's selected projects."""
    try:
        from src.services.project_monitor import ProjectMonitor

        # Get number of days to look back (default: 7 days)
        days_back = int(request.args.get('days', 7))
        since = datetime.now() - timedelta(days=days_back)

        monitor = ProjectMonitor()
        changes = asyncio.run(monitor.get_user_project_changes(email, since))

        return jsonify({'success': True, 'changes': changes, 'count': len(changes)})

    except Exception as e:
        logger.error(f"Error getting user changes: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@projects_bp.route('/my-projects/send-notification/<email>', methods=['POST'])
def send_project_notification(email):
    """Manually send project notification to a user."""
    try:
        from src.services.project_notifications import ProjectNotificationService

        notification_service = ProjectNotificationService()
        sent = asyncio.run(notification_service.send_user_notifications(email, force=True))

        if sent:
            return jsonify({'success': True, 'message': 'Notification sent successfully'})
        else:
            return jsonify({'success': False, 'message': 'No changes found or notification not due'})

    except Exception as e:
        logger.error(f"Error sending project notification: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@projects_bp.route('/my-projects/send-daily-notifications', methods=['POST'])
def send_daily_project_notifications():
    """Send daily notifications to all eligible users."""
    try:
        from src.services.project_notifications import ProjectNotificationService

        notification_service = ProjectNotificationService()
        asyncio.run(notification_service.send_daily_notifications())

        return jsonify({'success': True, 'message': 'Daily notifications sent'})

    except Exception as e:
        logger.error(f"Error sending daily notifications: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# Project Resource Mappings Routes
# ============================================================================

@projects_bp.route('/project-resource-mappings', methods=['GET'])
def get_all_project_resource_mappings():
    """Get all project resource mappings."""
    try:
        from sqlalchemy import text
        from src.utils.database import get_engine
        import json

        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT project_key, project_name, slack_channel_ids, notion_page_ids, github_repos, jira_project_keys
                FROM project_resource_mappings
                ORDER BY project_key
            """))

            mappings = []
            for row in result:
                project_key, project_name, slack_channel_ids, notion_page_ids, github_repos, jira_project_keys = row
                mappings.append({
                    'project_key': project_key,
                    'project_name': project_name,
                    'slack_channel_ids': json.loads(slack_channel_ids) if slack_channel_ids else [],
                    'notion_page_ids': json.loads(notion_page_ids) if notion_page_ids else [],
                    'github_repos': json.loads(github_repos) if github_repos else [],
                    'jira_project_keys': json.loads(jira_project_keys) if jira_project_keys else []
                })

        return jsonify({'success': True, 'mappings': mappings})

    except Exception as e:
        logger.error(f"Error getting project resource mappings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@projects_bp.route('/project-resource-mappings/<project_key>', methods=['PUT'])
def update_project_resource_mapping(project_key):
    """Update project resource mapping."""
    try:
        data = request.json
        from sqlalchemy import text
        from src.utils.database import get_engine
        import json

        engine = get_engine()
        with engine.connect() as conn:
            # Check if mapping exists
            result = conn.execute(
                text("SELECT project_key FROM project_resource_mappings WHERE project_key = :key"),
                {"key": project_key}
            )
            exists = result.fetchone() is not None

            if exists:
                # Update existing mapping
                conn.execute(text("""
                    UPDATE project_resource_mappings
                    SET slack_channel_ids = :slack_channels,
                        notion_page_ids = :notion_pages,
                        github_repos = :github_repos,
                        jira_project_keys = :jira_projects,
                        updated_at = :updated_at
                    WHERE project_key = :key
                """), {
                    'key': project_key,
                    'slack_channels': json.dumps(data.get('slack_channel_ids', [])),
                    'notion_pages': json.dumps(data.get('notion_page_ids', [])),
                    'github_repos': json.dumps(data.get('github_repos', [])),
                    'jira_projects': json.dumps(data.get('jira_project_keys', [])),
                    'updated_at': datetime.now()
                })
            else:
                # Insert new mapping
                conn.execute(text("""
                    INSERT INTO project_resource_mappings
                    (project_key, project_name, slack_channel_ids, notion_page_ids, github_repos, jira_project_keys, created_at, updated_at)
                    VALUES (:key, :name, :slack_channels, :notion_pages, :github_repos, :jira_projects, :created_at, :updated_at)
                """), {
                    'key': project_key,
                    'name': data.get('project_name', project_key),
                    'slack_channels': json.dumps(data.get('slack_channel_ids', [])),
                    'notion_pages': json.dumps(data.get('notion_page_ids', [])),
                    'github_repos': json.dumps(data.get('github_repos', [])),
                    'jira_projects': json.dumps(data.get('jira_project_keys', [])),
                    'created_at': datetime.now(),
                    'updated_at': datetime.now()
                })

            conn.commit()

        return jsonify({'success': True, 'message': 'Resource mapping updated successfully'})

    except Exception as e:
        logger.error(f"Error updating project resource mapping: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@projects_bp.route('/search/slack-channels', methods=['GET'])
def search_slack_channels():
    """Search for Slack channels by name."""
    try:
        query = request.args.get('q', '').lower()

        import os
        from slack_sdk import WebClient

        slack_token = os.getenv('SLACK_BOT_TOKEN')
        if not slack_token:
            return jsonify({'success': False, 'error': 'Slack not configured'}), 500

        slack_client = WebClient(token=slack_token)

        # Get only public channels (bot doesn't have groups:read scope for private channels)
        response = slack_client.conversations_list(
            types="public_channel",
            limit=1000
        )

        channels = []
        for channel in response['channels']:
            if query in channel['name'].lower():
                channels.append({
                    'id': channel['id'],
                    'name': channel['name'],
                    'is_private': channel.get('is_private', False),
                    'num_members': channel.get('num_members', 0)
                })

        # Sort by name
        channels.sort(key=lambda x: x['name'])

        return jsonify({'success': True, 'channels': channels})

    except Exception as e:
        logger.error(f"Error searching Slack channels: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@projects_bp.route('/search/notion-pages', methods=['GET'])
def search_notion_pages():
    """Search for Notion pages by title."""
    try:
        query = request.args.get('q', '').lower()

        import os
        from src.integrations.notion_api import NotionAPIClient

        notion_api_key = os.getenv('NOTION_API_KEY')
        if not notion_api_key:
            return jsonify({'success': False, 'error': 'Notion not configured'}), 500

        notion_client = NotionAPIClient(api_key=notion_api_key)

        # Use Notion search API with query parameter for faster results
        search_result = notion_client.search(query=query, filter_type='page', page_size=50)

        # Extract pages with proper title extraction
        pages = []
        for page in search_result.get('results', []):
            # Use the get_page_title method to properly extract title
            title = notion_client.get_page_title(page)

            if query in title.lower():
                pages.append({
                    'id': page.get('id'),
                    'title': title,
                    'url': page.get('url', '')
                })

        # Sort by title
        pages.sort(key=lambda x: x['title'])

        return jsonify({'success': True, 'pages': pages})

    except Exception as e:
        logger.error(f"Error searching Notion pages: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@projects_bp.route('/search/github-repos', methods=['GET'])
def search_github_repos():
    """Search for GitHub repositories from GitHub API."""
    try:
        query = request.args.get('q', '').lower()

        import asyncio
        from src.integrations.github_client import GitHubClient
        from config.settings import settings

        # Check if GitHub is configured
        has_app_auth = all([settings.github.app_id, settings.github.private_key, settings.github.installation_id])
        has_token_auth = bool(settings.github.api_token)

        if not (has_app_auth or has_token_auth):
            return jsonify({'success': False, 'error': 'GitHub not configured'}), 500

        # Initialize GitHub client (same pattern as context_search.py)
        github_client = GitHubClient(
            api_token=settings.github.api_token,
            organization=settings.github.organization,
            app_id=settings.github.app_id,
            private_key=settings.github.private_key,
            installation_id=settings.github.installation_id
        )

        # Get all accessible repos from GitHub
        async def get_repos():
            return await github_client.list_accessible_repos()

        all_repos = asyncio.run(get_repos())

        # Filter by query
        filtered_repos = []
        for repo in all_repos:
            if query in repo.lower():
                filtered_repos.append({'name': repo})

        # Sort by name
        filtered_repos.sort(key=lambda x: x['name'])

        return jsonify({'success': True, 'repos': filtered_repos})

    except Exception as e:
        logger.error(f"Error searching GitHub repos: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@projects_bp.route('/search/jira-projects', methods=['GET'])
def search_jira_projects():
    """Search for Jira projects by key or name."""
    try:
        query = request.args.get('q', '').lower()

        from config.settings import settings
        import requests
        from requests.auth import HTTPBasicAuth

        # Check if Jira is configured
        if not all([settings.jira.url, settings.jira.username, settings.jira.api_token]):
            return jsonify({'success': False, 'error': 'Jira not configured'}), 500

        # Call Jira REST API to get all projects
        url = f"{settings.jira.url}/rest/api/3/project"
        auth = HTTPBasicAuth(settings.jira.username, settings.jira.api_token)
        headers = {"Accept": "application/json"}

        response = requests.get(url, auth=auth, headers=headers, timeout=10)
        response.raise_for_status()

        all_projects = response.json()

        # Filter by query (search in both key and name)
        filtered_projects = []
        for project in all_projects:
            project_key = project.get('key', '').lower()
            project_name = project.get('name', '').lower()
            if query in project_key or query in project_name:
                filtered_projects.append({
                    'key': project.get('key'),
                    'name': project.get('name')
                })

        # Sort by key
        filtered_projects.sort(key=lambda x: x['key'])

        return jsonify({'success': True, 'projects': filtered_projects})

    except Exception as e:
        logger.error(f"Error searching Jira projects: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@projects_bp.route('/projects/todo-counts', methods=['GET'])
def get_project_todo_counts():
    """Get todo counts for all projects."""
    try:
        from src.utils.database import get_engine
        from sqlalchemy import text

        engine = get_engine()
        with engine.connect() as conn:
            # Get counts of todos grouped by project_key
            result = conn.execute(text("""
                SELECT project_key, COUNT(*) as count
                FROM todo_items
                WHERE project_key IS NOT NULL
                GROUP BY project_key
            """))

            # Convert to dict: {project_key: count}
            counts = {row[0]: row[1] for row in result}

        return jsonify({'success': True, 'counts': counts})

    except Exception as e:
        logger.error(f"Error getting project todo counts: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@projects_bp.route('/projects/monthly-hours', methods=['GET'])
def get_project_monthly_hours():
    """Get current month's hours for all projects."""
    try:
        from src.utils.database import get_engine
        from sqlalchemy import text
        from datetime import datetime

        # Get current month/year
        now = datetime.now()
        current_month = now.replace(day=1)

        engine = get_engine()
        with engine.connect() as conn:
            # Get current month's hours from project_monthly_forecast
            result = conn.execute(text("""
                SELECT project_key, actual_monthly_hours
                FROM project_monthly_forecast
                WHERE month_year = :month
            """), {"month": current_month})

            # Convert to dict: {project_key: hours}
            monthly_hours = {row[0]: float(row[1] or 0) for row in result}

        return jsonify({'success': True, 'monthly_hours': monthly_hours})

    except Exception as e:
        logger.error(f"Error getting project monthly hours: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
