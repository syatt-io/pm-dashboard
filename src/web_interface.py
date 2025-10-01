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
app.secret_key = os.getenv('JWT_SECRET_KEY', 'your-secret-key-here')

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

app.register_blueprint(health_bp)
app.register_blueprint(todos_bp)
app.register_blueprint(meetings_bp)
app.register_blueprint(jira_bp)
app.register_blueprint(learnings_bp)

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




@app.route('/api/process', methods=['POST'])
def process_decisions():
    """Process user decisions and create tickets/todos."""
    try:
        decisions = request.json
        analysis = session.get('current_analysis')

        if not analysis:
            return jsonify({'error': 'No analysis found in session'}), 400

        # Debug logging
        logger.info(f"Processing {len(decisions)} decisions")
        logger.info(f"Analysis has {len(analysis.get('action_items', []))} action items")
        logger.info(f"Decision keys: {list(decisions.keys())}")
        logger.info(f"Action items preview: {[item.get('title', 'No title') for item in analysis.get('action_items', [])]}")

        # Process decisions
        results = asyncio.run(_execute_decisions(decisions, analysis))

        return jsonify(results)

    except Exception as e:
        logger.error(f"Error in process_decisions: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/todos', methods=['GET'])
@auth_required
def get_todos(user):
    """Get all TODO items for React Admin."""
    try:
        with session_scope() as db_session:
            # Get pagination parameters
            page = int(request.args.get('page', 1))
            per_page = int(request.args.get('perPage', 25))
            sort_field = request.args.get('sort', 'created_at')
            sort_order = request.args.get('order', 'DESC')

            # Calculate offset
            offset = (page - 1) * per_page

            # Build query with visibility rules
            query = db_session.query(TodoItem)
            if user.role.value != 'admin':
                # Non-admin users see:
                # 1. Their own Slack-created TODOs (source='slack' AND user_id=current_user.id)
                # 2. Meeting-created TODOs for projects they're following (source='meeting_analysis' AND project in watched_projects)

                # Get user's watched projects
                from src.models.user import UserWatchedProject
                watched_project_keys = [
                    wp.project_key
                    for wp in db_session.query(UserWatchedProject).filter(
                        UserWatchedProject.user_id == user.id
                    ).all()
                ]

                # Apply visibility filter
                visibility_filter = or_(
                    # Own Slack TODOs
                    and_(TodoItem.source == 'slack', TodoItem.user_id == user.id),
                    # Meeting TODOs for watched projects
                    and_(
                        TodoItem.source == 'meeting_analysis',
                        TodoItem.project_key.in_(watched_project_keys) if watched_project_keys else False
                    )
                )
                query = query.filter(visibility_filter)

            # Apply sorting
            if hasattr(TodoItem, sort_field):
                column = getattr(TodoItem, sort_field)
                if sort_order.upper() == 'DESC':
                    query = query.order_by(column.desc())
                else:
                    query = query.order_by(column.asc())
            else:
                # Default sort by created_at DESC
                query = query.order_by(TodoItem.created_at.desc())

            # Get total count for pagination
            total = query.count()

            # Apply pagination
            todos = query.offset(offset).limit(per_page).all()

            # Convert to list of dictionaries
            todo_list = []
            for todo in todos:
                todo_data = {
                    'id': todo.id,
                    'title': todo.title,
                    'description': todo.description,
                    'assignee': todo.assignee,
                    'due_date': todo.due_date.isoformat() if todo.due_date else None,
                    'status': todo.status,
                    'ticket_key': todo.ticket_key,
                    'created_at': todo.created_at.isoformat() if todo.created_at else None,
                    'updated_at': todo.updated_at.isoformat() if todo.updated_at else None,
                    'source_meeting_id': todo.source_meeting_id,
                    'priority': todo.priority,
                    'project_key': getattr(todo, 'project_key', None)
                }
                todo_list.append(todo_data)

        # Return in React Admin format
        return jsonify({
            'data': todo_list,
            'total': total
        })

    except Exception as e:
        logger.error(f"Error fetching todos: {e}")
        return error_response(str(e), status_code=500)


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


@app.route('/api/todos', methods=['POST'])
@auth_required
def create_todo(user):
    """Create a new TODO item."""
    try:
        data = request.json

        # Import here to avoid circular imports
        from datetime import datetime
        import uuid

        # Create new TODO
        todo = TodoItem(
            id=str(uuid.uuid4()),
            title=data.get('title', ''),
            description=data.get('description', ''),
            assignee=data.get('assignee', ''),
            priority=data.get('priority', 'Medium'),
            status='pending',
            project_key=data.get('project_key'),
            user_id=user.id,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        if data.get('due_date'):
            try:
                todo.due_date = datetime.fromisoformat(data['due_date'])
            except:
                pass

        # Add to database
        todo_manager.session.add(todo)
        todo_manager.session.commit()

        return success_response(data={'id': todo.id}, message='TODO created successfully', status_code=201)

    except Exception as e:
        return error_response(str(e), status_code=500)


@app.route('/api/todos/<todo_id>/complete', methods=['POST'])
@auth_required
def complete_todo_api(user, todo_id):
    """Mark a TODO as complete."""
    try:
        data = request.json or {}
        completed_by = data.get('completed_by', 'Web User')
        notes = data.get('notes', '')

        success = todo_manager.complete_todo(todo_id, completed_by, notes)

        if success:
            return success_response(message='TODO marked as complete')
        else:
            return error_response('TODO not found', status_code=404)

    except Exception as e:
        return error_response(str(e), status_code=500)


@app.route('/api/todos/<todo_id>/snooze', methods=['POST'])
@auth_required
def snooze_todo_api(user, todo_id):
    """Snooze a TODO by extending its due date."""
    try:
        data = request.json or {}
        days = data.get('days', 1)

        success = todo_manager.snooze_todo(todo_id, days)

        if success:
            return success_response(message=f'TODO snoozed for {days} day(s)')
        else:
            return error_response('TODO not found', status_code=404)

    except Exception as e:
        return error_response(str(e), status_code=500)


@app.route('/api/todos/<todo_id>/update', methods=['POST'])
@auth_required
def update_todo_api(user, todo_id):
    """Update a TODO item."""
    try:
        data = request.json or {}
        success = todo_manager.update_todo(todo_id, data)

        if success:
            return success_response(message='TODO updated successfully')
        else:
            return error_response('TODO not found', status_code=404)

    except Exception as e:
        return error_response(str(e), status_code=500)


@app.route('/api/todos/<todo_id>', methods=['GET'])
@auth_required
def get_todo_api(user, todo_id):
    """Get a single TODO item (React Admin compatible)."""
    try:
        todo = todo_manager.get_todo(todo_id)
        if not todo:
            return error_response('TODO not found', status_code=404)

        todo_data = {
            'id': todo.id,
            'title': todo.title,
            'description': todo.description,
            'status': todo.status,
            'assignee': todo.assignee,
            'priority': getattr(todo, 'priority', 'Medium'),
            'created_at': todo.created_at.isoformat() if todo.created_at else None,
            'updated_at': todo.updated_at.isoformat() if todo.updated_at else None,
            'due_date': todo.due_date.isoformat() if todo.due_date else None,
            'source_meeting_id': todo.source_meeting_id,
            'ticket_key': todo.ticket_key,
            'project_key': getattr(todo, 'project_key', None)
        }

        return jsonify(todo_data)

    except Exception as e:
        return error_response(str(e), status_code=500)


@app.route('/api/todos/<todo_id>', methods=['PUT'])
@auth_required
def update_todo_put_api(user, todo_id):
    """Update a TODO item (React Admin compatible)."""
    try:
        data = request.json or {}
        success = todo_manager.update_todo(todo_id, data)

        if success:
            # Get the updated todo and return it
            todo = todo_manager.get_todo(todo_id)
            if todo:
                todo_data = {
                    'id': todo.id,
                    'title': todo.title,
                    'description': todo.description,
                    'assignee': todo.assignee,
                    'due_date': todo.due_date.isoformat() if todo.due_date else None,
                    'status': todo.status,
                    'ticket_key': todo.ticket_key,
                    'created_at': todo.created_at.isoformat() if todo.created_at else None,
                    'updated_at': todo.updated_at.isoformat() if todo.updated_at else None,
                    'source_meeting_id': todo.source_meeting_id,
                    'priority': todo.priority,
                    'project_key': getattr(todo, 'project_key', None)
                }
                return jsonify(todo_data)
            else:
                return error_response('TODO not found after update', status_code=404)
        else:
            return error_response('TODO not found', status_code=404)

    except Exception as e:
        return error_response(str(e), status_code=500)


@app.route('/api/todos/<todo_id>', methods=['DELETE'])
@auth_required
def delete_todo_api(user, todo_id):
    """Delete a TODO item."""
    try:
        success = todo_manager.delete_todo(todo_id)

        if success:
            return success_response(message='TODO deleted successfully')
        else:
            return error_response('TODO not found', status_code=404)

    except Exception as e:
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
@app.route("/api/scheduler/start", methods=["POST"])
def start_scheduler_api():
    """Start the TODO scheduler."""
    try:
        start_scheduler()
        return jsonify({"success": True, "message": "Scheduler started"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/scheduler/stop", methods=["POST"])
def stop_scheduler_api():
    """Stop the TODO scheduler."""
    try:
        stop_scheduler()
        return jsonify({"success": True, "message": "Scheduler stopped"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/scheduler/status")
def scheduler_status():
    """Get scheduler status."""
    try:
        scheduler = get_scheduler()
        status = {
            "running": scheduler is not None and scheduler.running if scheduler else False,
            "active_jobs": len(schedule.jobs) if scheduler else 0
        }
        return jsonify(status)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/notifications/daily-digest", methods=["POST"])
def trigger_daily_digest():
    """Manually trigger daily digest."""
    try:
        scheduler = get_scheduler()
        if not scheduler:
            return jsonify({"error": "Scheduler not running"}), 503

        asyncio.run(scheduler.send_daily_digest())
        return jsonify({"success": True, "message": "Daily digest sent"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/notifications/overdue-reminders", methods=["POST"])
def trigger_overdue_reminders():
    """Manually trigger overdue reminders."""
    try:
        scheduler = get_scheduler()
        if not scheduler:
            return jsonify({"error": "Scheduler not running"}), 503

        asyncio.run(scheduler.send_overdue_reminders())
        return jsonify({"success": True, "message": "Overdue reminders sent"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/notifications/due-today", methods=["POST"])
def trigger_due_today_reminders():
    """Manually trigger due today reminders."""
    try:
        scheduler = get_scheduler()
        if not scheduler:
            return jsonify({"error": "Scheduler not running"}), 503

        asyncio.run(scheduler.send_due_today_reminders())
        return jsonify({"success": True, "message": "Due today reminders sent"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/notifications/custom", methods=["POST"])
def send_custom_notification():
    """Send custom notification."""
    try:
        data = request.json or {}
        assignee = data.get('assignee', '')
        message = data.get('message', '')
        priority = data.get('priority', 'normal')

        if not assignee or not message:
            return jsonify({"error": "Assignee and message are required"}), 400

        scheduler = get_scheduler()
        if not scheduler:
            return jsonify({"error": "Scheduler not running"}), 503

        asyncio.run(scheduler.send_custom_reminder(assignee, message, priority))
        return jsonify({"success": True, "message": "Custom notification sent"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/scheduler/hours-report", methods=["POST"])
def trigger_hours_report():
    """Manually trigger weekly hours report."""
    try:
        scheduler = get_scheduler()
        if not scheduler:
            return jsonify({'success': False, 'error': 'Scheduler not running'}), 500

        asyncio.run(scheduler.send_weekly_hours_reports())

        return jsonify({'success': True, 'message': 'Hours report sent successfully'})
    except Exception as e:
        logger.error(f"Error triggering hours report: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route("/api/meetings", methods=["GET"])
@auth_required
def get_meetings(user):
    """Get meetings using live Fireflies data with cached analysis overlay."""
    try:
        # Get pagination parameters
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('perPage', 25))
        sort_field = request.args.get('sort_field', request.args.get('sort', 'date'))
        sort_order = request.args.get('sort_order', request.args.get('order', 'DESC'))

        # Get filter parameters
        date_range = request.args.get('date_range', '7')  # Default to 7 days
        projects = request.args.get('projects', '')  # Comma-separated project keys

        logger.info(f"Fetching live meetings for user {user.id} - date_range={date_range}, projects={projects}")

        # Check if user has configured their own Fireflies API key
        user_api_key = user.get_fireflies_api_key()

        if not user_api_key:
            # User hasn't configured their API key
            logger.info(f"User {user.id} has no Fireflies API key configured")
            return jsonify({
                'data': [],
                'total': 0,
                'page': page,
                'perPage': per_page,
                'totalPages': 0,
                'error': 'no_api_key',
                'message': 'Please configure your Fireflies API key in Settings to view meetings.'
            })

        # Initialize Fireflies client with user's API key
        try:
            fireflies_client = FirefliesClient(user_api_key)
        except Exception as e:
            logger.error(f"Failed to initialize Fireflies client for user {user.id}: {e}")
            return jsonify({
                'data': [],
                'total': 0,
                'page': page,
                'perPage': per_page,
                'totalPages': 0,
                'error': 'invalid_api_key',
                'message': 'Invalid Fireflies API key. Please check your Settings.'
            }), 400

        # Fetch live meetings from Fireflies
        if date_range == 'all':
            days_back = 90  # Reasonable limit for 'all'
        else:
            try:
                days_back = int(date_range)
            except ValueError:
                days_back = 7

        # Fetch live meetings from Fireflies with error handling
        try:
            live_meetings = fireflies_client.get_recent_meetings(days_back=days_back, limit=200)
            logger.info(f"Fetched {len(live_meetings)} meetings from Fireflies for user {user.id}")
        except Exception as e:
            logger.error(f"Failed to fetch meetings from Fireflies for user {user.id}: {e}")
            return jsonify({
                'data': [],
                'total': 0,
                'page': page,
                'perPage': per_page,
                'totalPages': 0,
                'error': 'fireflies_error',
                'message': 'Failed to fetch meetings from Fireflies. Please check your API key and try again.'
            }), 500

        # Get cached analysis data for overlay
        from src.models import ProcessedMeeting, ProcessedMeetingDTO

        # Create lookup dict for cached analysis (using DTOs to avoid detached object issues)
        cached_analyses = {}
        try:
            with session_scope() as db_session:
                all_cached = db_session.query(ProcessedMeeting).all()
                for cached in all_cached:
                    cached_analyses[cached.meeting_id] = ProcessedMeetingDTO.from_orm(cached)
        except Exception as e:
            logger.warning(f"Error loading cached analyses: {e}")

        # Convert Fireflies data to our format and apply project filtering
        meeting_list = []
        for meeting in live_meetings:
            try:
                # Handle date conversion
                if meeting.get('date'):
                    if isinstance(meeting['date'], (int, float)) and meeting['date'] > 1000000000000:
                        meeting_date = datetime.fromtimestamp(meeting['date'] / 1000)
                    else:
                        meeting_date = datetime.fromisoformat(str(meeting['date']))
                else:
                    meeting_date = datetime.now()

                # Create meeting dict in our expected format
                meeting_data = {
                    'id': meeting.get('id'),
                    'meeting_id': meeting.get('id'),
                    'title': meeting.get('title', 'Untitled Meeting'),
                    'date': meeting_date.isoformat(),
                    'duration': meeting.get('duration', 0),
                    'summary': meeting.get('summary', ''),
                    'action_items': [],
                    'action_items_count': 0,
                    'relevance_score': 0,
                    'confidence': 0.0,
                    'analyzed_at': None,
                    'key_decisions': [],
                    'blockers': []
                }

                # Overlay cached analysis if available
                cached = cached_analyses.get(meeting.get('id'))
                if cached:
                    meeting_data.update({
                        'action_items': cached.action_items or [],
                        'action_items_count': len(cached.action_items) if cached.action_items else 0,
                        'relevance_score': getattr(cached, 'relevance_score', 0) or 0,
                        'confidence': getattr(cached, 'confidence', 0.0) or 0.0,
                        'analyzed_at': cached.analyzed_at.isoformat() if cached.analyzed_at else None,
                        'summary': cached.summary or meeting_data['summary'],
                        'key_decisions': getattr(cached, 'key_decisions', []) or [],
                        'blockers': getattr(cached, 'blockers', []) or []
                    })

                # For the Analysis tab, apply special filtering
                resource_context = request.args.get('resource_context', 'meetings')

                if resource_context == 'analysis':
                    # Apply project filtering for Analysis tab - show ALL meetings for watched projects
                    # (both analyzed and unanalyzed)
                    if projects:
                        project_list = [p.strip().upper() for p in projects.split(',') if p.strip()]
                        if project_list:
                            # Get keyword mapping for projects from database
                            project_keywords = get_project_keywords_from_db()

                            # Get all keywords for the selected projects
                            search_keywords = []
                            for project in project_list:
                                search_keywords.extend(project_keywords.get(project, [project.lower()]))

                            # Check if any project keyword appears in title or summary
                            title_lower = meeting_data['title'].lower()
                            summary_lower = meeting_data['summary'].lower()

                            # Debug logging to see what we're comparing
                            logger.info(f"Checking meeting '{meeting_data['title']}' against projects {project_list}")
                            logger.info(f"Search keywords: {search_keywords}")
                            logger.info(f"Title: '{title_lower}', Summary: '{summary_lower[:100]}...'")

                            project_match = any(
                                keyword in title_lower or keyword in summary_lower
                                for keyword in search_keywords
                            )

                            logger.info(f"Project match result: {project_match}")

                            if not project_match:
                                continue  # Skip this meeting if no project match

                meeting_list.append(meeting_data)

            except Exception as e:
                logger.warning(f"Error processing meeting {meeting.get('id', 'unknown')}: {e}")
                continue

        # Apply sorting
        if sort_field == 'date':
            meeting_list.sort(key=lambda x: x['date'], reverse=(sort_order.upper() == 'DESC'))
        elif sort_field == 'title':
            meeting_list.sort(key=lambda x: x['title'], reverse=(sort_order.upper() == 'DESC'))

        # Apply pagination
        total = len(meeting_list)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_meetings = meeting_list[start_idx:end_idx]

        logger.info(f"Returning {len(paginated_meetings)} meetings out of {total} total for page {page}")

        # Return in React Admin format
        return jsonify({
            'data': paginated_meetings,
            'total': total
        })

    except Exception as e:
        logger.error(f"Error fetching live meetings: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route("/api/meetings/<meeting_id>", methods=["GET"])
@auth_required
def get_meeting_detail(user, meeting_id):
    """Get details for a specific meeting."""
    try:
        # Check if user has configured their own Fireflies API key
        user_api_key = user.get_fireflies_api_key()

        if not user_api_key:
            return jsonify({
                'error': 'no_api_key',
                'message': 'Please configure your Fireflies API key in Settings to view meeting details.'
            }), 400

        # Initialize Fireflies client with user's API key
        try:
            fireflies_client = FirefliesClient(api_key=user_api_key)
        except Exception as e:
            logger.error(f"Failed to initialize Fireflies client for user {user.id}: {e}")
            return jsonify({
                'error': 'invalid_api_key',
                'message': 'Invalid Fireflies API key. Please check your Settings.'
            }), 400

        # Get the meeting transcript from Fireflies
        transcript = fireflies_client.get_meeting_transcript(meeting_id)
        if not transcript:
            return jsonify({'error': 'Meeting not found'}), 404

        # Check if we have analysis cached for this meeting (convert to DTO)
        from src.models import ProcessedMeeting, ProcessedMeetingDTO
        cached_dto = None
        with session_scope() as db_session:
            cached = db_session.query(ProcessedMeeting).filter_by(meeting_id=meeting_id).first()
            if cached:
                cached_dto = ProcessedMeetingDTO.from_orm(cached)

        # Build the response
        meeting_data = {
            'id': transcript.id,
            'meeting_id': transcript.id,
            'title': transcript.title,
            'date': transcript.date.isoformat(),
            'duration': transcript.duration,
            'transcript': transcript.transcript,
            'action_items_count': 0,
            'relevance_score': 0,
            'confidence': 0,
            'analyzed_at': None,
            'action_items': [],
            'key_decisions': [],
            'blockers': [],
            'follow_ups': [],
            'summary': None
        }

        # Add cached analysis data if available
        if cached_dto:
            meeting_data.update({
                'action_items_count': len(cached_dto.action_items) if cached_dto.action_items else 0,
                'relevance_score': 0,  # Not stored in DTO currently
                'confidence': 0,  # Not stored in DTO currently
                'analyzed_at': cached_dto.analyzed_at.isoformat() if cached_dto.analyzed_at else None,
                'action_items': cached_dto.action_items or [],
                'key_decisions': cached_dto.key_decisions or [],
                'blockers': cached_dto.blockers or [],
                'follow_ups': [],  # Not stored in DTO currently
                'summary': cached_dto.summary
            })

        return jsonify(meeting_data)

    except Exception as e:
        logger.error(f"Error fetching meeting detail for {meeting_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route("/api/meetings/<meeting_id>/analyze", methods=["POST"])
@auth_required
def analyze_meeting_api(user, meeting_id):
    """Trigger analysis for a specific meeting via API."""
    try:
        from src.models import ProcessedMeeting

        # Check if user has configured their own Fireflies API key
        user_api_key = user.get_fireflies_api_key()

        if not user_api_key:
            return jsonify({
                'error': 'no_api_key',
                'message': 'Please configure your Fireflies API key in Settings to analyze meetings.'
            }), 400

        # Initialize Fireflies client with user's API key
        try:
            user_fireflies_client = FirefliesClient(api_key=user_api_key)
        except Exception as e:
            logger.error(f"Failed to initialize Fireflies client for user {user.id}: {e}")
            return jsonify({
                'error': 'invalid_api_key',
                'message': 'Invalid Fireflies API key. Please check your Settings.'
            }), 400

        # Get meeting transcript using user's API key
        transcript = user_fireflies_client.get_meeting_transcript(meeting_id)
        if not transcript:
            return jsonify({'error': 'Meeting not found'}), 404

        logger.info(f"Starting API analysis for meeting {meeting_id}")

        # Analyze with AI using global analyzer
        analysis = analyzer.analyze_transcript(
            transcript.transcript,
            transcript.title,
            transcript.date
        )

        # Store analysis results in database
        analyzed_at = datetime.now()
        action_items_data = [
            {
                'title': item.title,
                'description': item.description,
                'assignee': item.assignee,
                'due_date': item.due_date,
                'priority': item.priority,
                'context': item.context
            }
            for item in analysis.action_items
        ]

        # Check for existing record to handle race conditions
        with session_scope() as db_session:
            existing_meeting = db_session.query(ProcessedMeeting).filter_by(meeting_id=meeting_id).first()

            if existing_meeting:
                # Update existing record
                existing_meeting.analyzed_at = analyzed_at
                existing_meeting.summary = analysis.summary
                existing_meeting.key_decisions = analysis.key_decisions
                existing_meeting.blockers = analysis.blockers
                existing_meeting.action_items = action_items_data
                existing_meeting.title = transcript.title
                existing_meeting.date = transcript.date
                logger.info(f"Updated existing processed meeting record for {meeting_id}")
            else:
                # Create new record
                processed_meeting = ProcessedMeeting(
                    meeting_id=meeting_id,
                    title=transcript.title,
                    date=transcript.date,
                    analyzed_at=analyzed_at,
                    summary=analysis.summary,
                    key_decisions=analysis.key_decisions,
                    blockers=analysis.blockers,
                    action_items=action_items_data
                )
                db_session.add(processed_meeting)
                logger.info(f"Created new processed meeting record for {meeting_id}")

        return jsonify({
            'success': True,
            'message': 'Meeting analyzed successfully',
            'meeting_id': meeting_id,
            'analyzed_at': analyzed_at.isoformat(),
            'action_items_count': len(action_items_data)
        })

    except Exception as e:
        logger.error(f"Error analyzing meeting {meeting_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route("/api/jira/projects", methods=["GET"])
def get_jira_projects():
    """Get all Jira projects with local database enhancements."""
    try:
        # Check if Jira credentials are configured
        if not settings.jira.url or not settings.jira.username or not settings.jira.api_token:
            logger.error("Jira credentials not configured")
            return jsonify({"success": False, "error": "Jira credentials not configured"}), 500

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

        return jsonify({"success": True, "projects": enhanced_projects})
    except Exception as e:
        logger.error(f"Error fetching Jira projects: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/jira/issue-types", methods=["GET"])
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
        return jsonify({"success": True, "issue_types": issue_types})
    except Exception as e:
        logger.error(f"Error fetching Jira issue types: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/jira/users", methods=["GET"])
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
        return jsonify({"success": True, "users": users})
    except Exception as e:
        logger.error(f"Error fetching Jira users: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/jira/users/search", methods=["GET"])
def search_jira_users():
    """Search users with autocomplete - requires minimum 3 characters."""
    try:
        query = request.args.get('q', '').strip()

        # Require minimum 3 characters
        if len(query) < 3:
            return jsonify({"success": True, "users": []})

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
        return jsonify({"success": True, "users": users})
    except Exception as e:
        logger.error(f"Error searching Jira users: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/jira/priorities", methods=["GET"])
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
        return jsonify({"success": True, "priorities": priorities})
    except Exception as e:
        logger.error(f"Error fetching Jira priorities: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/jira/metadata/<project_key>", methods=["GET"])
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
        return jsonify({"success": True, "metadata": metadata})
    except Exception as e:
        logger.error(f"Error fetching Jira metadata: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


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


@app.route('/api/jira/projects/<project_key>', methods=['PUT'])
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

        return jsonify({'success': True, 'message': 'Project updated successfully'})

    except Exception as e:
        logger.error(f"Error updating project {project_key}: {e}")
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
@app.route('/api/meeting-project-analysis/<meeting_id>')
def analyze_meeting_projects(meeting_id):
    """Analyze which Jira projects a meeting is relevant to."""
    try:
        from src.services.meeting_project_linker import MeetingProjectLinker

        linker = MeetingProjectLinker()
        result = asyncio.run(linker.analyze_meeting_project_relevance(meeting_id))

        return jsonify({'success': True, 'analysis': result})

    except Exception as e:
        logger.error(f"Error analyzing meeting projects: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/project-meetings/<project_key>')
def get_project_meetings(project_key):
    """Get meetings relevant to a specific project."""
    try:
        from src.services.meeting_project_linker import MeetingProjectLinker

        days_back = int(request.args.get('days', 30))

        linker = MeetingProjectLinker()
        result = asyncio.run(linker.get_meetings_for_projects([project_key], days_back))

        meetings = result.get(project_key, [])

        return jsonify({
            'success': True,
            'project_key': project_key,
            'meetings': meetings,
            'count': len(meetings)
        })

    except Exception as e:
        logger.error(f"Error getting project meetings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/project-suggestions/<project_key>')
def get_project_suggestions(project_key):
    """Get action suggestions for a project based on recent meetings."""
    try:
        from src.services.meeting_project_linker import MeetingProjectLinker

        days_back = int(request.args.get('days', 30))

        linker = MeetingProjectLinker()
        result = asyncio.run(linker.suggest_project_actions(project_key, days_back))

        return jsonify({'success': True, 'suggestions': result})

    except Exception as e:
        logger.error(f"Error getting project suggestions: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/meeting-project-dashboard')
def meeting_project_dashboard():
    """Get dashboard data for meeting-project relationships."""
    try:
        # Get days parameter from query string, default to 7 days
        days = request.args.get('days', 7, type=int)

        # Get project keys from query params or user's selected projects
        project_keys = request.args.getlist('projects')

        if not project_keys:
            # If no projects specified, try to get from user's email
            email = request.args.get('email')
            if email:
                from main import UserPreference

                with session_scope() as db_session:
                    user_pref = db_session.query(UserPreference).filter_by(email=email).first()
                    if user_pref and user_pref.selected_projects:
                        project_keys = user_pref.selected_projects

        if not project_keys:
            return jsonify({'success': False, 'error': 'No projects specified'}), 400

        # Check if we have cached data in the temp file first
        cache_file = '/tmp/meeting_data.json'
        try:
            if os.path.exists(cache_file):
                # Check if file is recent (less than 5 minutes old)
                file_age = datetime.now().timestamp() - os.path.getmtime(cache_file)
                if file_age < 300:  # 5 minutes
                    logger.info("Using cached meeting dashboard data")
                    with open(cache_file, 'r') as f:
                        cached_data = json.load(f)
                        if cached_data.get('success'):
                            return jsonify(cached_data)
        except Exception as cache_error:
            logger.warning(f"Error reading cache: {cache_error}")

        # If no valid cache, generate new data
        from src.services.meeting_project_linker import MeetingProjectLinker
        linker = MeetingProjectLinker()
        result = asyncio.run(linker.create_project_meeting_dashboard_data(project_keys, days))

        # Cache the result
        try:
            with open(cache_file, 'w') as f:
                json.dump({'success': True, 'dashboard': result}, f, indent=2)
        except Exception as cache_error:
            logger.warning(f"Error writing cache: {cache_error}")

        return jsonify({'success': True, 'dashboard': result})

    except Exception as e:
        logger.error(f"Error creating meeting-project dashboard: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/sync-hours', methods=['POST'])
def sync_hours():
    """Sync project hours from Jira/Tempo to local database using accurate Tempo v4 API."""
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
                WHERE is_active = 1
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
        current_year = current_date.year

        # Fetch worklogs using the proven accurate method
        logger.info("Starting accurate Tempo v4 API sync")

        # Get current month worklogs
        current_month_worklogs = get_tempo_worklogs(
            start_of_month.strftime('%Y-%m-%d'),
            current_date.strftime('%Y-%m-%d')
        )

        # Get year-to-date worklogs for cumulative data
        cumulative_worklogs = get_tempo_worklogs(
            f"{current_year}-01-01",
            current_date.strftime('%Y-%m-%d')
        )

        if not current_month_worklogs and not cumulative_worklogs:
            logger.warning("No worklogs retrieved from Tempo API")
            return jsonify({
                'success': False,
                'message': 'No worklogs retrieved from Tempo API. Check API token configuration.',
                'projects_updated': 0
            })

        # Process current month data
        current_month_hours, _ = process_worklogs(current_month_worklogs, active_projects)

        # Process cumulative data
        _, cumulative_hours = process_worklogs(cumulative_worklogs, active_projects)

        # Update database
        with engine.connect() as conn:
            for project in active_projects:
                try:
                    project_key = project['key']
                    project_work_type = project['project_work_type'] or 'project-based'

                    logger.info(f"Updating project {project_key} (type: {project_work_type})")

                    if project_work_type == 'growth-support':
                        # For growth & support: use current month hours
                        hours = current_month_hours.get(project_key, 0)
                        conn.execute(text("""
                            UPDATE projects
                            SET current_month_hours = :hours, updated_at = CURRENT_TIMESTAMP
                            WHERE key = :key
                        """), {"hours": hours, "key": project_key})
                        logger.info(f"Updated {project_key} with {hours:.2f} current month hours")

                    else:
                        # For project-based: use cumulative hours
                        hours = cumulative_hours.get(project_key, 0)
                        current_hours = current_month_hours.get(project_key, 0)

                        conn.execute(text("""
                            UPDATE projects
                            SET cumulative_hours = :cumulative_hours,
                                current_month_hours = :current_month_hours,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE key = :key
                        """), {
                            "cumulative_hours": hours,
                            "current_month_hours": current_hours,
                            "key": project_key
                        })
                        logger.info(f"Updated {project_key} with {hours:.2f} cumulative hours, {current_hours:.2f} current month hours")

                    projects_updated += 1

                except Exception as e:
                    logger.error(f"Error syncing hours for project {project_key}: {e}")
                    continue

            # Commit all changes
            conn.commit()

        return jsonify({
            'success': True,
            'message': f'Successfully synced hours for {projects_updated} projects using accurate Tempo v4 API',
            'projects_updated': projects_updated,
            'current_month_total': sum(current_month_hours.values()),
            'cumulative_total': sum(cumulative_hours.values())
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
@app.route('/api/learnings', methods=['GET'])
@auth_required
def get_learnings(user):
    """Get all learnings with optional filtering."""
    try:
        from src.managers.learning_manager import LearningManager
        manager = LearningManager()

        category = request.args.get('category')
        limit = int(request.args.get('limit', 20))
        offset = int(request.args.get('offset', 0))

        learnings = manager.get_learnings(
            limit=limit,
            offset=offset,
            category=category
        )

        return jsonify({
            'success': True,
            'learnings': [learning.to_dict() for learning in learnings],
            'total': len(learnings)
        })

    except Exception as e:
        logger.error(f"Error fetching learnings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/learnings', methods=['POST'])
@auth_required
def create_learning(user):
    """Create a new learning."""
    try:
        from src.managers.learning_manager import LearningManager
        manager = LearningManager()

        data = request.json
        content = data.get('content')

        if not content:
            return jsonify({'success': False, 'error': 'Content is required'}), 400

        learning = manager.create_learning(
            content=content,
            submitted_by=user.name,
            submitted_by_id=str(user.id),
            category=data.get('category'),
            source='web'
        )

        return jsonify({
            'success': True,
            'learning': learning.to_dict(),
            'message': 'Learning saved successfully'
        })

    except Exception as e:
        logger.error(f"Error creating learning: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/learnings/<learning_id>', methods=['GET'])
@auth_required
def get_learning(user, learning_id):
    """Get a single learning by ID."""
    try:
        from src.managers.learning_manager import LearningManager
        manager = LearningManager()

        learning = manager.get_learning(learning_id)

        if learning:
            return jsonify({
                'success': True,
                'data': learning.to_dict()
            })
        else:
            return jsonify({'success': False, 'error': 'Learning not found'}), 404

    except Exception as e:
        logger.error(f"Error fetching learning: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/learnings/<learning_id>', methods=['PUT'])
@auth_required
def update_learning(user, learning_id):
    """Update an existing learning."""
    try:
        from src.managers.learning_manager import LearningManager
        manager = LearningManager()

        data = request.json
        success = manager.update_learning(
            learning_id=learning_id,
            content=data.get('content'),
            category=data.get('category')
        )

        if success:
            return jsonify({'success': True, 'message': 'Learning updated'})
        else:
            return jsonify({'success': False, 'error': 'Learning not found'}), 404

    except Exception as e:
        logger.error(f"Error updating learning: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/learnings/<learning_id>', methods=['DELETE'])
@auth_required
def delete_learning(user, learning_id):
    """Archive (soft delete) a learning."""
    try:
        from src.managers.learning_manager import LearningManager
        manager = LearningManager()

        success = manager.archive_learning(learning_id)

        if success:
            return jsonify({'success': True, 'message': 'Learning archived'})
        else:
            return jsonify({'success': False, 'error': 'Learning not found'}), 404

    except Exception as e:
        logger.error(f"Error archiving learning: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/learnings/search', methods=['GET'])
@auth_required
def search_learnings(user):
    """Search learnings by content."""
    try:
        from src.managers.learning_manager import LearningManager
        manager = LearningManager()

        search_term = request.args.get('q')
        if not search_term:
            return jsonify({'success': False, 'error': 'Search term required'}), 400

        learnings = manager.search_learnings(search_term)

        return jsonify({
            'success': True,
            'learnings': [learning.to_dict() for learning in learnings],
            'total': len(learnings)
        })

    except Exception as e:
        logger.error(f"Error searching learnings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/learnings/categories', methods=['GET'])
@auth_required
def get_learning_categories(user):
    """Get all learning categories."""
    try:
        from src.managers.learning_manager import LearningManager
        manager = LearningManager()

        categories = manager.get_categories()

        return jsonify({
            'success': True,
            'categories': categories
        })

    except Exception as e:
        logger.error(f"Error fetching categories: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/learnings/stats', methods=['GET'])
@auth_required
def get_learning_stats(user):
    """Get statistics about learnings."""
    try:
        from src.managers.learning_manager import LearningManager
        manager = LearningManager()

        stats = manager.get_stats()

        return jsonify({
            'success': True,
            'stats': stats
        })

    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint for DigitalOcean App Platform."""
    try:
        # Basic health check - can add database check if needed
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat()
        }), 200
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500


@app.route('/api/health/jira', methods=['GET'])
def jira_health_check():
    """Diagnostic endpoint for Jira connection."""
    try:
        import os
        import base64
        import httpx

        diagnostics = {
            'jira_url': settings.jira.url if hasattr(settings, 'jira') else 'NOT_LOADED',
            'jira_username': settings.jira.username if hasattr(settings, 'jira') else 'NOT_LOADED',
            'jira_token_set': bool(settings.jira.api_token) if hasattr(settings, 'jira') and hasattr(settings.jira, 'api_token') else False,
            'jira_token_length': len(settings.jira.api_token) if hasattr(settings, 'jira') and hasattr(settings.jira, 'api_token') and settings.jira.api_token else 0,
            'jira_token_prefix': settings.jira.api_token[:10] + '...' if hasattr(settings, 'jira') and hasattr(settings.jira, 'api_token') and settings.jira.api_token else None,
            'env_jira_url': os.getenv('JIRA_URL'),
            'env_jira_username': os.getenv('JIRA_USERNAME'),
            'env_jira_token_set': bool(os.getenv('JIRA_API_TOKEN')),
            'env_jira_token_length': len(os.getenv('JIRA_API_TOKEN', '')),
            'env_jira_token_prefix': os.getenv('JIRA_API_TOKEN', '')[:10] + '...' if os.getenv('JIRA_API_TOKEN') else None,
        }

        # Test actual Jira API call synchronously
        try:
            auth_string = base64.b64encode(f"{settings.jira.username}:{settings.jira.api_token}".encode()).decode()

            # Use httpx synchronously for testing
            client = httpx.Client(timeout=30.0)
            response = client.get(
                f"{settings.jira.url}/rest/api/3/project",
                headers={
                    "Authorization": f"Basic {auth_string}",
                    "Accept": "application/json"
                }
            )

            response_data = response.json() if response.status_code == 200 else None
            diagnostics['api_test'] = {
                'status_code': response.status_code,
                'success': response.status_code == 200,
                'project_count': len(response_data) if response_data else 0,
                'sample_response': response_data[:2] if response_data and len(response_data) > 0 else response_data,
                'error': response.text if response.status_code != 200 else None
            }

            client.close()

        except Exception as api_error:
            import traceback
            diagnostics['api_test'] = {
                'success': False,
                'error': str(api_error),
                'traceback': traceback.format_exc()
            }

        return jsonify(diagnostics)
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


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
# Explicit route for /login (React Admin's default login page path)
@app.route('/login')
def serve_login():
    """Explicitly serve React app for login page."""
    return serve_react('login')

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