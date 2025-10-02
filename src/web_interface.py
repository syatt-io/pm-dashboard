"""Web-based interface for interactive meeting processing."""

from flask import Flask, render_template, request, jsonify, session, redirect, send_from_directory
from flask_cors import CORS
import asyncio
import uuid
import logging
import schedule
from datetime import datetime
import json

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings
from src.integrations.fireflies import FirefliesClient
from src.processors.transcript_analyzer import TranscriptAnalyzer
from src.processors.interactive_processor import ReviewedItem
from src.integrations.jira_mcp import JiraMCPClient, JiraTicket
from src.managers.notifications import NotificationManager, NotificationContent
from src.managers.todo_manager import TodoManager
from src.managers.slack_bot import SlackTodoBot
from src.services.scheduler import get_scheduler, start_scheduler, stop_scheduler

# Authentication imports
from src.services.auth import AuthService, auth_required, admin_required
from src.routes.auth import create_auth_blueprint
from src.models.user import UserWatchedProject
from sqlalchemy import text
from main import TodoItem
from src.utils.database import get_engine, get_session_factory, get_session, close_session, init_database, session_scope


logger = logging.getLogger(__name__)

def get_project_keywords_from_db():
    """Load project keywords from database as a dictionary."""
    try:
        engine = get_engine()

        project_keywords = {}
        with engine.connect() as conn:
            result = conn.execute(text("SELECT project_key, keyword FROM project_keywords"))
            for row in result:
                project_key, keyword = row
                if project_key not in project_keywords:
                    project_keywords[project_key] = []
                project_keywords[project_key].append(keyword)

        return project_keywords
    except Exception as e:
        logger.error(f"Error loading project keywords from database: {e}")
        # Return empty dict if database query fails
        return {}

import os
template_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'templates')
# Configure React build directory for static files
react_build_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'frontend', 'build')
app = Flask(__name__,
            template_folder=template_dir,
            static_folder=react_build_dir,
            static_url_path='')

# Production-ready secret key
app.secret_key = os.getenv('JWT_SECRET_KEY')
if not app.secret_key:
    if os.getenv('FLASK_ENV') == 'production':
        raise ValueError("JWT_SECRET_KEY must be set in production environment")
    else:
        logger.warning("JWT_SECRET_KEY not set - using development fallback (NOT FOR PRODUCTION)")
        app.secret_key = 'dev-secret-key-change-in-production'

# Configure CORS for development and production
# Get frontend port from environment, default to 4001
frontend_port = int(os.getenv('FRONTEND_PORT', 4001))
cors_origins = [f"http://localhost:{frontend_port}", "http://localhost:3000", "http://localhost:3001", "http://localhost:3002"]
if os.getenv('FLASK_ENV') == 'production':
    # Add production domain when deployed
    production_domain = os.getenv('PRODUCTION_DOMAIN')
    if production_domain:
        cors_origins.append(f"https://{production_domain}")

CORS(app, origins=cors_origins, supports_credentials=True,
     allow_headers=['Content-Type', 'Authorization'],
     methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])

# Set up database and auth
# Initialize database once at startup
init_database()

# Get session factory for auth services
db_session_factory = get_session_factory()

# Initialize auth service with factory, not instance
auth_service = AuthService(db_session_factory)
app.auth_service = auth_service

# Register auth blueprint
auth_blueprint = create_auth_blueprint(db_session_factory)
app.register_blueprint(auth_blueprint)

# Register extracted route blueprints
from src.routes.health import health_bp
from src.routes.todos import todos_bp
from src.routes.meetings import meetings_bp
from src.routes.jira import jira_bp
from src.routes.learnings import learnings_bp
from src.routes.scheduler import scheduler_bp

app.register_blueprint(health_bp)
app.register_blueprint(todos_bp)
app.register_blueprint(meetings_bp)
app.register_blueprint(jira_bp)
app.register_blueprint(learnings_bp)
app.register_blueprint(scheduler_bp)

# Initialize components
fireflies = FirefliesClient(settings.fireflies.api_key)
analyzer = TranscriptAnalyzer()
notifier = NotificationManager(settings.notifications)
todo_manager = TodoManager()

# Initialize Slack bot if tokens are available
slack_bot = None
if settings.notifications.slack_bot_token:
    try:
        slack_bot = SlackTodoBot(
            bot_token=settings.notifications.slack_bot_token,
            signing_secret=getattr(settings.notifications, 'slack_signing_secret', 'dummy_secret')
        )
        logger.info("Slack bot initialized successfully")
    except Exception as e:
        logger.warning(f"Failed to initialize Slack bot: {e}")
        slack_bot = None


# ============================================================================
# Standardized API Response Helpers
# ============================================================================

def success_response(data=None, message=None, status_code=200):
    """
    Standard success response format for all API endpoints.

    Args:
        data: Response data (dict, list, or None)
        message: Optional success message
        status_code: HTTP status code (default 200)

    Returns:
        Flask jsonify response with consistent format
    """
    response = {'success': True}

    if data is not None:
        response['data'] = data

    if message is not None:
        response['message'] = message

    return jsonify(response), status_code


def error_response(error, status_code=500, details=None):
    """
    Standard error response format for all API endpoints.

    Args:
        error: Error message (string)
        status_code: HTTP status code (default 500)
        details: Optional additional error details

    Returns:
        Flask jsonify response with consistent format
    """
    response = {
        'success': False,
        'error': str(error)
    }

    if details is not None:
        response['details'] = details

    return jsonify(response), status_code


def run_database_migrations():
    """Run any necessary database migrations."""
    try:
        # Run Alembic migrations first
        import subprocess
        import os
        logger.info("Running Alembic migrations...")
        try:
            # Get the project root directory
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            result = subprocess.run(
                ['alembic', 'upgrade', 'head'],
                cwd=project_root,
                capture_output=True,
                text=True,
                check=True
            )
            logger.info(f"Alembic migrations completed: {result.stdout}")
        except subprocess.CalledProcessError as e:
            logger.warning(f"Alembic migration failed: {e.stderr}")
        except Exception as e:
            logger.warning(f"Alembic migration error: {e}")

        from sqlalchemy.orm import sessionmaker
        engine = get_engine()

        with engine.connect() as conn:
            # Check if we need to migrate slack_user_id to slack_username
            try:
                # Try to query the old column
                conn.execute(text("SELECT slack_user_id FROM user_preferences LIMIT 1"))

                # If we get here, the old column exists, so we need to migrate
                logger.info("Migrating slack_user_id to slack_username...")

                # Add new column if it doesn't exist
                try:
                    conn.execute(text("ALTER TABLE user_preferences ADD COLUMN slack_username TEXT"))
                    conn.commit()
                    logger.info("Added slack_username column")
                except Exception:
                    # Column might already exist
                    pass

                # Copy data from old column to new column
                try:
                    conn.execute(text("UPDATE user_preferences SET slack_username = slack_user_id WHERE slack_user_id IS NOT NULL AND slack_username IS NULL"))
                    conn.commit()
                    logger.info("Copied data from slack_user_id to slack_username")
                except Exception as e:
                    logger.warning(f"Data copy failed: {e}")

                logger.info("Migration completed successfully")

            except Exception:
                # Old column doesn't exist, so no migration needed
                logger.info("No migration needed - slack_username column already exists")

            # Add new columns to processed_meetings table
            columns_to_add = [
                ('key_decisions', 'TEXT'),
                ('blockers', 'TEXT'),
                ('analyzed_at', 'TIMESTAMP'),
                ('processed_at', 'TIMESTAMP'),
                ('tickets_created', 'TEXT'),
                ('todos_created', 'TEXT'),
                ('success', 'BOOLEAN DEFAULT true')
            ]

            for column_name, column_type in columns_to_add:
                try:
                    conn.execute(text(f"ALTER TABLE processed_meetings ADD COLUMN {column_name} {column_type}"))
                    conn.commit()
                    logger.info(f"Added {column_name} column to processed_meetings")
                except Exception as e:
                    # Column might already exist
                    if 'already exists' not in str(e).lower() and 'duplicate' not in str(e).lower():
                        logger.debug(f"Column {column_name} migration note: {e}")

    except Exception as e:
        logger.warning(f"Migration failed: {e}")

# Run migrations on startup
run_database_migrations()








@app.route('/api/dashboard/stats', methods=['GET'])
@auth_required
def get_dashboard_stats(user):
    """Get dashboard statistics efficiently (counts only, no full records)."""
    try:
        from sqlalchemy import func
        from src.models import ProcessedMeeting

        with session_scope() as db_session:
            # Count total meetings (processed meetings from Fireflies)
            total_meetings = db_session.query(func.count(ProcessedMeeting.id)).scalar() or 0

            # Count todos by status with visibility rules
            if user.role.value != 'admin':
                # Non-admin users see:
                # 1. Their own Slack-created TODOs
                # 2. Meeting-created TODOs for projects they're following
                from src.models.user import UserWatchedProject
                watched_project_keys = [
                    wp.project_key
                    for wp in db_session.query(UserWatchedProject).filter(
                        UserWatchedProject.user_id == user.id
                    ).all()
                ]

                visibility_filter = or_(
                    and_(TodoItem.source == 'slack', TodoItem.user_id == user.id),
                    and_(
                        TodoItem.source == 'meeting_analysis',
                        TodoItem.project_key.in_(watched_project_keys) if watched_project_keys else False
                    )
                )

                total_todos = db_session.query(func.count(TodoItem.id)).filter(visibility_filter).scalar() or 0
                completed_todos = db_session.query(func.count(TodoItem.id)).filter(
                    visibility_filter,
                    TodoItem.status == 'done'
                ).scalar() or 0
            else:
                # Admin sees all todos
                total_todos = db_session.query(func.count(TodoItem.id)).scalar() or 0
                completed_todos = db_session.query(func.count(TodoItem.id)).filter(
                    TodoItem.status == 'done'
                ).scalar() or 0

            # Count active projects (assumes JiraProject model exists)
            try:
                from src.models import JiraProject
                total_projects = db_session.query(func.count(JiraProject.key)).filter(
                    JiraProject.is_active == True
                ).scalar() or 0
            except (ImportError, AttributeError):
                # If JiraProject model doesn't exist, return 0
                total_projects = 0

            return success_response(data={
                'total_meetings': total_meetings,
                'total_todos': total_todos,
                'completed_todos': completed_todos,
                'active_todos': total_todos - completed_todos,
                'total_projects': total_projects,
                'todo_completion_rate': round((completed_todos / total_todos * 100) if total_todos > 0 else 0)
            })

    except Exception as e:
        logger.error(f"Error fetching dashboard stats: {e}")
        return error_response(str(e), status_code=500)


















# Watched Projects API Routes
@app.route('/api/watched-projects', methods=['GET'])
@auth_required
def get_watched_projects(user):
    """Get user's watched projects."""
    try:
        with session_scope() as session:
            watched_projects = session.query(UserWatchedProject)\
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


@app.route('/api/watched-projects/<project_key>', methods=['POST'])
@auth_required
def watch_project(user, project_key):
    """Add a project to user's watched list."""
    try:
        with session_scope() as session:
            # Check if already watching
            existing = session.query(UserWatchedProject)\
                .filter_by(user_id=user.id, project_key=project_key)\
                .first()

            if existing:
                return jsonify({'success': True, 'message': 'Already watching this project'})

            # Add new watched project
            watched_project = UserWatchedProject(
                user_id=user.id,
                project_key=project_key
            )
            session.add(watched_project)

        return jsonify({'success': True, 'message': f'Now watching {project_key}'})

    except Exception as e:
        logger.error(f"Failed to watch project {project_key}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/watched-projects/<project_key>', methods=['DELETE'])
@auth_required
def unwatch_project(user, project_key):
    """Remove a project from user's watched list."""
    try:
        with session_scope() as session:
            watched_project = session.query(UserWatchedProject)\
                .filter_by(user_id=user.id, project_key=project_key)\
                .first()

            if watched_project:
                session.delete(watched_project)
                return jsonify({'success': True, 'message': f'Stopped watching {project_key}'})
            else:
                return jsonify({'success': False, 'message': 'Project not in watched list'})

    except Exception as e:
        logger.error(f"Failed to unwatch project {project_key}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# Slack Bot Routes
@app.route("/slack/events", methods=["POST"])
def slack_events():
    """Handle Slack events and commands."""
    # Handle URL verification challenge from Slack
    if request.is_json and request.json and request.json.get('type') == 'url_verification':
        return jsonify({'challenge': request.json.get('challenge')}), 200

    if not slack_bot:
        return jsonify({"error": "Slack bot not configured"}), 503

    # Let Slack Bolt handler process all requests (slash commands, events, etc.)
    return slack_bot.get_handler().handle(request)


@app.route("/slack/commands", methods=["POST"])
def slack_commands():
    """Handle Slack slash commands."""
    if not slack_bot:
        return jsonify({"error": "Slack bot not configured"}), 503

    return slack_bot.get_handler().handle(request)


@app.route("/slack/interactive", methods=["POST"])
def slack_interactive():
    """Handle Slack interactive components."""
    if not slack_bot:
        return jsonify({"error": "Slack bot not configured"}), 503

    return slack_bot.get_handler().handle(request)


@app.route("/api/slack/digest", methods=["POST"])
def send_slack_digest():
    """Manually trigger Slack daily digest."""
    if not slack_bot:
        return jsonify({"error": "Slack bot not configured"}), 503

    try:
        import asyncio
        channel = request.json.get('channel') if request.json else None
        asyncio.run(slack_bot.send_daily_digest(channel))
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Scheduler and Notification Routes


































# My Projects Routes - Handled by React app

@app.route('/api/my-projects/user/<email>', methods=['GET'])
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


@app.route('/api/my-projects/user', methods=['POST'])
def save_user_settings():
    """Save or update user settings."""
    try:
        data = request.json
        email = data.get('email')

        if not email:
            return jsonify({'success': False, 'error': 'Email is required'}), 400

        from main import UserPreference
        import uuid

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
                from sqlalchemy import text
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




@app.route('/api/my-projects/test-notification', methods=['POST'])
def send_test_notification():
    """Send a test notification to user."""
    try:
        data = request.json
        email = data.get('email')

        if not email:
            return jsonify({'success': False, 'error': 'Email is required'}), 400

        # Create a test notification
        notification = NotificationContent(
            title="Test Notification - My Projects",
            body=f"This is a test notification for {email}. Your project monitoring is working correctly!",
            priority="normal"
        )

        # Send notification
        asyncio.run(notifier.send_notification(notification, channels=["slack"]))

        return jsonify({'success': True, 'message': 'Test notification sent'})

    except Exception as e:
        logger.error(f"Error sending test notification: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/my-projects/poll-changes', methods=['POST'])
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


@app.route('/api/my-projects/changes/<email>', methods=['GET'])
def get_user_changes(email):
    """Get recent changes for a user's selected projects."""
    try:
        from src.services.project_monitor import ProjectMonitor
        from datetime import datetime, timedelta

        # Get number of days to look back (default: 7 days)
        days_back = int(request.args.get('days', 7))
        since = datetime.now() - timedelta(days=days_back)

        monitor = ProjectMonitor()
        changes = asyncio.run(monitor.get_user_project_changes(email, since))

        return jsonify({'success': True, 'changes': changes, 'count': len(changes)})

    except Exception as e:
        logger.error(f"Error getting user changes: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/my-projects/send-notification/<email>', methods=['POST'])
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


@app.route('/api/my-projects/send-daily-notifications', methods=['POST'])
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



# Meeting-Project Linking Routes








@app.route('/api/sync-hours', methods=['POST'])
def sync_hours():
    """
    Manual sync of CURRENT MONTH hours only from Tempo API.
    This is optimized for quick manual updates via the UI button.
    For full YTD sync, use the nightly job at 4am EST.
    """
    try:
        from sqlalchemy import create_engine, text
        from datetime import datetime
        import requests
        import base64
        import re
        from collections import defaultdict

        engine = get_engine()
        projects_updated = 0

        # Get all active projects
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT key, name, project_work_type
                FROM projects
                WHERE is_active = true
            """))
            active_projects = [{'key': row[0], 'name': row[1], 'project_work_type': row[2]} for row in result]

        if not active_projects:
            return jsonify({
                'success': True,
                'message': 'No active projects to sync',
                'projects_updated': 0
            })

        # Helper function to get issue key from Jira using issue ID
        def get_issue_key_from_jira(issue_id, issue_cache):
            """Get issue key from Jira using issue ID."""
            if issue_id in issue_cache:
                return issue_cache[issue_id]

            try:
                credentials = f"{settings.jira.username}:{settings.jira.api_token}"
                encoded_credentials = base64.b64encode(credentials.encode()).decode()

                headers = {
                    "Authorization": f"Basic {encoded_credentials}",
                    "Accept": "application/json"
                }

                url = f"{settings.jira.url}/rest/api/3/issue/{issue_id}"
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                issue_data = response.json()
                issue_key = issue_data.get("key")
                issue_cache[issue_id] = issue_key
                return issue_key
            except Exception as e:
                logger.debug(f"Error getting issue key for ID {issue_id}: {e}")
                issue_cache[issue_id] = None
                return None

        # Helper function to get Tempo worklogs with complete accuracy
        def get_tempo_worklogs(from_date: str, to_date: str):
            """Get worklogs from Tempo API v4 for a date range."""
            tempo_token = settings.jira.api_token  # Fallback if no specific Tempo token
            for key in ['TEMPO_API_TOKEN', 'tempo_api_token']:
                if hasattr(settings, key):
                    tempo_token = getattr(settings, key)
                    break
                try:
                    import os
                    env_token = os.getenv(key)
                    if env_token:
                        tempo_token = env_token
                        break
                except:
                    pass

            headers = {
                "Authorization": f"Bearer {tempo_token}",
                "Accept": "application/json"
            }

            url = "https://api.tempo.io/4/worklogs"
            params = {
                "from": from_date,
                "to": to_date,
                "limit": 5000
            }

            logger.info(f"Fetching Tempo worklogs from {from_date} to {to_date}")

            try:
                response = requests.get(url, headers=headers, params=params)
                response.raise_for_status()

                data = response.json()
                worklogs = data.get("results", [])

                # Handle pagination
                page_count = 1
                while data.get("metadata", {}).get("next"):
                    next_url = data["metadata"]["next"]
                    logger.info(f"Fetching page {page_count + 1}")
                    response = requests.get(next_url, headers=headers)
                    response.raise_for_status()
                    data = response.json()
                    page_worklogs = data.get("results", [])
                    worklogs.extend(page_worklogs)
                    page_count += 1

                logger.info(f"Retrieved {len(worklogs)} total worklogs from Tempo API across {page_count} pages")
                return worklogs

            except requests.exceptions.RequestException as e:
                logger.error(f"Error fetching Tempo data: {e}")
                if hasattr(e, 'response') and e.response:
                    logger.error(f"Response: {e.response.text}")
                return []

        # Helper function to process worklogs with complete accuracy
        def process_worklogs(worklogs, target_projects):
            """Process worklogs and aggregate hours by project using both description parsing and issue ID lookups."""
            current_month = datetime.now().month
            current_year = datetime.now().year

            current_month_hours = defaultdict(float)
            cumulative_hours = defaultdict(float)

            # Cache issue ID to key mappings
            issue_cache = {}
            processed_count = 0
            skipped_count = 0

            for worklog in worklogs:
                description = worklog.get("description", "")
                issue_key = None

                # First try extracting project key from description (faster)
                issue_match = re.search(r'([A-Z]+-\d+)', description)
                if issue_match:
                    issue_key = issue_match.group(1)
                else:
                    # If not found in description, look up via issue ID
                    issue_id = worklog.get("issue", {}).get("id")
                    if issue_id:
                        issue_key = get_issue_key_from_jira(issue_id, issue_cache)

                if not issue_key:
                    skipped_count += 1
                    continue

                processed_count += 1
                project_key = issue_key.split("-")[0]

                # Only process if this project is in our target list
                if project_key not in [p['key'] for p in target_projects]:
                    continue

                # Get hours (timeSpentSeconds / 3600)
                seconds = worklog.get("timeSpentSeconds", 0)
                hours = seconds / 3600

                # Get worklog date
                worklog_date_str = worklog.get("startDate", "")
                if not worklog_date_str:
                    continue

                try:
                    worklog_date = datetime.strptime(worklog_date_str, "%Y-%m-%d")
                except ValueError:
                    continue

                # Add to cumulative
                cumulative_hours[project_key] += hours

                # Add to current month if applicable
                if worklog_date.year == current_year and worklog_date.month == current_month:
                    current_month_hours[project_key] += hours

            logger.info(f"Processed {processed_count} worklogs, skipped {skipped_count}")
            logger.info(f"Made {len(issue_cache)} Jira API calls for issue key lookups")

            return current_month_hours, cumulative_hours

        # Get date ranges
        current_date = datetime.now()
        start_of_month = current_date.replace(day=1)

        # Manual sync: Only fetch current month worklogs (fast!)
        # The nightly job at 4am EST handles full YTD sync
        logger.info("Starting manual Tempo sync (current month only)")

        # Get current month worklogs
        current_month_worklogs = get_tempo_worklogs(
            start_of_month.strftime('%Y-%m-%d'),
            current_date.strftime('%Y-%m-%d')
        )

        if not current_month_worklogs:
            logger.warning("No worklogs retrieved from Tempo API for current month")
            return jsonify({
                'success': False,
                'message': 'No worklogs retrieved from Tempo API for current month. Check API token configuration.',
                'projects_updated': 0
            })

        # Process current month data only
        current_month_hours, _ = process_worklogs(current_month_worklogs, active_projects)

        # Update database - only update current_month_hours
        # The nightly job handles cumulative_hours updates
        with engine.connect() as conn:
            for project in active_projects:
                try:
                    project_key = project['key']
                    current_hours = current_month_hours.get(project_key, 0)

                    # Update only current month hours for all projects
                    conn.execute(text("""
                        UPDATE projects
                        SET current_month_hours = :hours,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE key = :key
                    """), {"hours": current_hours, "key": project_key})

                    logger.info(f"Updated {project_key} with {current_hours:.2f} current month hours")
                    projects_updated += 1

                except Exception as e:
                    logger.error(f"Error syncing hours for project {project_key}: {e}")
                    continue

            # Commit all changes
            conn.commit()

        return jsonify({
            'success': True,
            'message': f'Successfully synced current month hours for {projects_updated} projects',
            'projects_updated': projects_updated,
            'current_month_total': sum(current_month_hours.values()),
            'note': 'Only current month synced. Cumulative hours updated by nightly job at 4am EST.'
        })

    except Exception as e:
        logger.error(f"Error syncing hours: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


async def _execute_decisions(decisions, analysis):
    """Execute the user decisions."""
    results = {
        'jira_created': [],
        'todos_created': [],
        'errors': []
    }

    jira_client = JiraMCPClient(
        jira_url=settings.jira.url,
        username=settings.jira.username,
        api_token=settings.jira.api_token
    )

    async with jira_client:
        for item_id, decision in decisions.items():
            try:
                # Skip non-item keys like 'type'
                if not item_id.isdigit() and not item_id.startswith('item_'):
                    logger.info(f"Skipping non-item key: {item_id}")
                    continue

                # Handle both numeric keys ('0', '1', '2') and item_ prefixed keys ('item_0', 'item_1')
                if item_id.isdigit():
                    item_index = int(item_id)
                else:
                    item_index = int(item_id.split('_')[1])

                action_items = analysis.get('action_items', [])
                logger.info(f"Processing item {item_id}, index {item_index}, total items: {len(action_items)}")

                # Safety check to prevent index out of range
                if item_index >= len(action_items):
                    logger.error(f"Index {item_index} out of range for {len(action_items)} action items")
                    results['errors'].append(f"Invalid item index {item_index} for item {item_id}")
                    continue

                action_item = action_items[item_index]

                if decision['destination'] == 'jira':
                    # Create Jira ticket
                    ticket = JiraTicket(
                        summary=decision.get('title', action_item['title']),
                        description=f"From meeting: {analysis['meeting_title']}\n\n"
                                  f"{action_item['description']}\n\n"
                                  f"Context: {action_item['context']}",
                        issue_type=decision.get('issue_type', 'Task'),
                        priority=decision.get('priority', action_item['priority']),
                        project_key=decision.get('project', 'PM'),
                        assignee=decision.get('assignee', action_item['assignee']),
                        due_date=decision.get('due_date', action_item['due_date']),
                        labels=["pm-agent", "web-interface"]
                    )

                    result = await jira_client.create_ticket(ticket)
                    if result.get("success"):
                        results['jira_created'].append(result.get("key"))
                    else:
                        results['errors'].append(f"Failed to create ticket: {result.get('error')}")

                elif decision['destination'] == 'todo':
                    # Create TODO item in database
                    import uuid

                    todo = TodoItem(
                        id=str(uuid.uuid4()),
                        title=decision.get('title', action_item['title']),
                        description=f"From meeting: {analysis['meeting_title']}\n\n"
                                  f"{action_item['description']}\n\n"
                                  f"Context: {action_item['context']}",
                        assignee=decision.get('assignee', action_item['assignee']),
                        priority=decision.get('priority', action_item['priority']),
                        status='pending',
                        created_at=datetime.now(),
                        updated_at=datetime.now()
                    )

                    if decision.get('due_date', action_item['due_date']):
                        try:
                            due_date_str = decision.get('due_date', action_item['due_date'])
                            todo.due_date = datetime.fromisoformat(due_date_str) if due_date_str else None
                        except:
                            pass

                    todo_manager.session.add(todo)
                    todo_manager.session.commit()
                    results['todos_created'].append(todo.title)

            except Exception as e:
                results['errors'].append(f"Error processing item {item_id}: {str(e)}")

    # Send notification
    if results['jira_created'] or results['todos_created']:
        await _send_completion_notification(analysis['meeting_title'], results)

    return results


async def _send_completion_notification(meeting_title, results):
    """Send notification about processing completion."""
    body = f"Meeting *{meeting_title}* processed via web interface.\n\n"

    if results['jira_created']:
        body += f"✅ Created {len(results['jira_created'])} Jira tickets\n"
        for ticket in results['jira_created'][:5]:
            body += f"  • {ticket}\n"

    if results['todos_created']:
        body += f"\n✅ Added {len(results['todos_created'])} TODO items\n"
        for todo in results['todos_created'][:5]:
            body += f"  • {todo}\n"

    notification = NotificationContent(
        title="Meeting Processed (Web Interface)",
        body=body,
        priority="normal"
    )

    await notifier.send_notification(notification, channels=["slack"])


# HTML Templates (store in templates/ directory)
@app.route('/api/project-digest/<project_key>', methods=['POST'])
def generate_project_digest(project_key):
    """Generate a comprehensive project digest for client meetings."""
    try:
        data = request.json or {}
        days_back = int(data.get('days', 7))
        project_name = data.get('project_name', project_key)

        logger.info(f"Generating project digest for {project_key} ({days_back} days)")

        async def generate_digest():
            from src.services.project_activity_aggregator import ProjectActivityAggregator

            aggregator = ProjectActivityAggregator()
            activity = await aggregator.aggregate_project_activity(
                project_key=project_key,
                project_name=project_name,
                days_back=days_back
            )

            # Format the digest
            markdown_agenda = aggregator.format_client_agenda(activity)

            return {
                'success': True,
                'project_key': project_key,
                'project_name': project_name,
                'days_back': days_back,
                'activity_data': {
                    'meetings_count': len(activity.meetings),
                    'tickets_completed': len(activity.completed_tickets),
                    'tickets_created': len(activity.new_tickets),
                    'hours_logged': activity.total_hours,
                    'progress_summary': activity.progress_summary,
                    'key_achievements': activity.key_achievements,
                    'blockers_risks': activity.blockers_risks,
                    'next_steps': activity.next_steps
                },
                'formatted_agenda': markdown_agenda
            }

        # Run the async function
        import asyncio
        result = asyncio.run(generate_digest())
        return jsonify(result)

    except Exception as e:
        logger.error(f"Error generating project digest: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>PM Agent - Dashboard</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        .meeting { border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 5px; }
        .meeting:hover { background-color: #f5f5f5; }
        .btn { background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; }
    </style>
</head>
<body>
    <h1>🎯 PM Agent Dashboard</h1>
    <h2>Recent Meetings</h2>

    {% for meeting in meetings %}
    <div class="meeting">
        <h3>{{ meeting.title }}</h3>
        <p>📅 {{ meeting.date }} | ⏱️ {{ meeting.duration|round|int }} minutes</p>
        <a href="/analyze/{{ meeting.id }}" class="btn">Analyze Meeting</a>
    </div>
    {% endfor %}
</body>
</html>
"""

ANALYSIS_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Meeting Analysis</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        .summary { background: #f8f9fa; padding: 20px; margin: 20px 0; border-radius: 5px; }
        .action-item { border: 1px solid #ddd; padding: 15px; margin: 10px 0; }
        .btn { background: #28a745; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; }
    </style>
</head>
<body>
    <h1>📋 {{ meeting_title }}</h1>

    <div class="summary">
        <h2>Summary</h2>
        <p>{{ analysis.summary }}</p>
    </div>

    <h2>🎯 Action Items ({{ analysis.action_items|length }})</h2>
    {% for item in analysis.action_items %}
    <div class="action-item">
        <h3>{{ item.title }}</h3>
        <p><strong>Assignee:</strong> {{ item.assignee or "Unassigned" }}</p>
        <p><strong>Priority:</strong> {{ item.priority }}</p>
        <p>{{ item.description }}</p>
    </div>
    {% endfor %}

    <a href="/review" class="btn">Review & Process Items</a>
</body>
</html>
"""

# Learning API endpoints




















# =============================================================================
# User Settings API Endpoints
# =============================================================================

@app.route("/api/user/settings", methods=["GET"])
@auth_required
def get_user_settings(user):
    """Get current user settings."""
    try:
        # Refresh user from database to get latest data
        from sqlalchemy.orm import Session

        # Get the session that the user object is attached to
        session = Session.object_session(user)
        if session:
            session.expire(user)  # Mark user as expired to force refresh
            session.refresh(user)  # Refresh from database

        return jsonify({
            'success': True,
            'data': {
                'user': user.to_dict(),
                'settings': {
                    'has_fireflies_key': user.has_fireflies_api_key(),
                    'fireflies_key_valid': user.validate_fireflies_api_key() if user.has_fireflies_api_key() else False
                }
            }
        })
    except Exception as e:
        logger.error(f"Error getting user settings for user {user.id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route("/api/user/fireflies-key", methods=["POST"])
@auth_required
def save_fireflies_api_key(user):
    """Save or update user's Fireflies API key."""
    try:
        data = request.get_json()
        api_key = data.get('api_key', '').strip()

        if not api_key:
            return jsonify({
                'success': False,
                'error': 'API key is required'
            }), 400

        # Skip validation here since the frontend already validates via the separate endpoint

        # Save the encrypted API key
        # Inline encryption to avoid import issues
        def encrypt_api_key_inline(api_key: str) -> str:
            """Encrypt an API key for database storage."""
            import os
            import base64
            from cryptography.fernet import Fernet
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

            # Get encryption key from environment
            encryption_key = os.getenv('ENCRYPTION_KEY')
            if not encryption_key:
                # Generate a temporary key (not recommended for production)
                encryption_key = Fernet.generate_key().decode()

            # If the key is a password/phrase, derive a proper key
            if len(encryption_key) != 44 or not encryption_key.endswith('='):
                # Derive key from password using PBKDF2
                salt = b'syatt_pm_agent_salt_v1'  # Static salt for consistency
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=salt,
                    iterations=100000,
                )
                key = base64.urlsafe_b64encode(kdf.derive(encryption_key.encode()))
            else:
                # Use the key directly (it's already a Fernet key)
                key = encryption_key.encode()

            fernet = Fernet(key)
            encrypted_bytes = fernet.encrypt(api_key.encode())
            return base64.urlsafe_b64encode(encrypted_bytes).decode()

        try:
            with session_scope() as db_session:
                # Refresh user object from database
                db_user = db_session.merge(user)

                # Set encrypted API key directly
                db_user.fireflies_api_key_encrypted = encrypt_api_key_inline(api_key) if api_key.strip() else None

            logger.info(f"Fireflies API key saved for user {user.id}")
            return jsonify({
                'success': True,
                'message': 'Fireflies API key saved successfully'
            })

        except Exception as e:
            raise e

    except Exception as e:
        logger.error(f"Error saving Fireflies API key for user {user.id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route("/api/user/fireflies-key", methods=["DELETE"])
@auth_required
def delete_fireflies_api_key(user):
    """Delete user's Fireflies API key."""
    try:
        with session_scope() as db_session:
            # Refresh user object from database
            db_user = db_session.merge(user)
            db_user.clear_fireflies_api_key()

        logger.info(f"Fireflies API key deleted for user {user.id}")
        return jsonify({
            'success': True,
            'message': 'Fireflies API key deleted successfully'
        })

    except Exception as e:
        logger.error(f"Error deleting Fireflies API key for user {user.id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route("/api/user/fireflies-key/validate", methods=["POST"])
@auth_required
def validate_fireflies_api_key_endpoint(user):
    """Validate a Fireflies API key without saving it."""
    try:
        data = request.get_json()
        api_key = data.get('api_key', '').strip()

        if not api_key:
            return jsonify({
                'valid': False,
                'error': 'API key is required'
            }), 400

        # Validate the API key format (simple check to avoid timeout issues)
        def validate_fireflies_api_key_inline(api_key: str) -> bool:
            """Validate a Fireflies API key format."""
            if not api_key or not api_key.strip():
                return False
            # Basic format check - Fireflies API keys are typically long alphanumeric strings
            api_key = api_key.strip()
            return len(api_key) > 20 and api_key.replace('-', '').replace('_', '').isalnum()

        is_valid = validate_fireflies_api_key_inline(api_key)

        return jsonify({
            'valid': is_valid,
            'message': 'API key is valid' if is_valid else 'API key is invalid'
        })

    except Exception as e:
        logger.error(f"Error validating Fireflies API key: {e}")
        return jsonify({
            'valid': False,
            'error': 'Failed to validate API key'
        }), 500


# Emergency route to create users table
@app.route('/api/admin/create-users-table', methods=['POST', 'GET'])
def create_users_table_endpoint():
    """Create users table in the database - emergency endpoint."""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            trans = conn.begin()
            try:
                # Create users table without custom enum (use VARCHAR for role)
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS users (
                        id SERIAL PRIMARY KEY,
                        email VARCHAR(255) UNIQUE NOT NULL,
                        name VARCHAR(255),
                        google_id VARCHAR(255) UNIQUE,
                        role VARCHAR(50) DEFAULT 'MEMBER',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_login TIMESTAMP,
                        is_active BOOLEAN DEFAULT TRUE,
                        fireflies_api_key_encrypted TEXT
                    );
                """))

                trans.commit()

                # Verify table exists
                result = conn.execute(text("SELECT COUNT(*) FROM users"))
                count = result.scalar()

                return jsonify({
                    'success': True,
                    'message': 'Users table created successfully',
                    'table_exists': True,
                    'row_count': count
                })

            except Exception as e:
                trans.rollback()
                return jsonify({
                    'success': False,
                    'error': f'Failed to create table: {str(e)}'
                }), 500

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Database connection failed: {str(e)}'
        }), 500
# Serve React build files in production
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_react(path):
    """Serve React application in production."""
    try:
        print(f"=== SERVE_REACT CALLED: path='{path}' ===", flush=True)

        # Skip API and Slack routes
        if path.startswith('api/') or path.startswith('slack/'):
            print(f"Skipping API/Slack route: {path}", flush=True)
            return jsonify({'error': 'Not found'}), 404

        # Try multiple possible build directory paths
        possible_build_dirs = [
            '/workspace/frontend/build',  # DigitalOcean workspace (production)
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'frontend', 'build'),  # Local dev
            os.path.join(os.getcwd(), 'frontend', 'build'),  # Current working directory
            'frontend/build'  # Relative path
        ]

        print(f"Checking build directories...", flush=True)
        react_build_dir = None
        for build_dir in possible_build_dirs:
            exists = os.path.exists(build_dir)
            print(f"  {build_dir}: exists={exists}", flush=True)
            if exists:
                react_build_dir = build_dir
                print(f"✓ Found React build directory: {build_dir}", flush=True)
                break

        # In production, serve React build
        if react_build_dir:
            index_path = os.path.join(react_build_dir, 'index.html')
            index_exists = os.path.exists(index_path)
            print(f"index.html exists: {index_exists}", flush=True)

            # Try to serve the requested file
            if path != "" and os.path.exists(os.path.join(react_build_dir, path)):
                print(f"Serving specific file: {path}", flush=True)
                return send_from_directory(react_build_dir, path)
            else:
                # Serve index.html for client-side routing
                print(f"Serving index.html for SPA route: '{path}'", flush=True)
                return send_from_directory(react_build_dir, 'index.html')
        else:
            # Debug information for troubleshooting
            debug_info = {
                'message': 'React build directory not found',
                'cwd': os.getcwd(),
                'checked_paths': possible_build_dirs,
                'exists_checks': [os.path.exists(p) for p in possible_build_dirs]
            }
            print(f"❌ ERROR: React build not found! {debug_info}", flush=True)
            return jsonify(debug_info), 404

    except Exception as e:
        print(f"❌ EXCEPTION in serve_react: {e}", flush=True)
        import traceback
        traceback.print_exc()
        raise


# 404 error handler - serve React app for client-side routing
@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors by serving React app for client-side routing."""
    # Get the requested path
    path = request.path

    # Skip API routes - return actual 404
    if path.startswith('/api/') or path.startswith('/slack/'):
        return jsonify({'error': 'Not found'}), 404

    # For all other routes, serve React app (let React Admin handle routing)
    print(f"=== 404 HANDLER: serving React for path '{path}' ===", flush=True)
    return serve_react(path.lstrip('/'))


if __name__ == '__main__':
    # Create templates directory and files
    import os
    os.makedirs('templates', exist_ok=True)

    with open('templates/dashboard.html', 'w') as f:
        f.write(DASHBOARD_TEMPLATE)

    with open('templates/analysis.html', 'w') as f:
        f.write(ANALYSIS_TEMPLATE)

    # Get port from environment variable, default to 4000
    port = int(os.getenv('BACKEND_PORT', 4000))
    app.run(debug=True, host='127.0.0.1', port=port)