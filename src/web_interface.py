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

# Defer project_keywords migration to background thread to avoid blocking startup
import threading

def run_migration_background():
    """Run migration in background thread to not block startup."""
    try:
        from scripts.run_migration import run_migration
        run_migration()
        logger.info("✅ Project keywords migration completed")
    except Exception as e:
        logger.warning(f"Project keywords migration skipped or failed: {e}")

# Start migration in background
migration_thread = threading.Thread(target=run_migration_background, daemon=True)
migration_thread.start()

# Get session factory for auth services
db_session_factory = get_session_factory()

# Initialize auth service with factory, not instance
auth_service = AuthService(db_session_factory)
app.auth_service = auth_service

# Start the scheduler for nightly jobs (Tempo sync, reminders, etc.)
logger.info("Starting TODO scheduler...")
start_scheduler()

# Register cleanup on application shutdown
import atexit
atexit.register(stop_scheduler)

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
from src.routes.slack import slack_bp, init_slack_routes
from src.routes.projects import projects_bp, init_projects_routes
from src.routes.tempo import tempo_bp
from src.routes.user import user_bp
from src.routes.dashboard import dashboard_bp
from src.routes.feedback import feedback_bp

app.register_blueprint(health_bp)
app.register_blueprint(todos_bp)
app.register_blueprint(meetings_bp)
app.register_blueprint(jira_bp)
app.register_blueprint(learnings_bp)
app.register_blueprint(scheduler_bp)
app.register_blueprint(slack_bp)
app.register_blueprint(projects_bp)
app.register_blueprint(tempo_bp)
app.register_blueprint(user_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(feedback_bp)

# Initialize components
fireflies = FirefliesClient(settings.fireflies.api_key)
analyzer = TranscriptAnalyzer()
notifier = NotificationManager(settings.notifications)
todo_manager = TodoManager()

# Initialize Slack routes with config (lazy initialization - bot created on first use)
init_slack_routes(
    bot_token=settings.notifications.slack_bot_token,
    signing_secret=getattr(settings.notifications, 'slack_signing_secret', 'dummy_secret')
)
logger.info("Slack routes initialized (bot will be created on first use)")

# Initialize Projects routes with notifier
init_projects_routes(notifier)


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
# TEMPORARILY DISABLED: Causing health check failures due to blocking each gunicorn worker
# TODO: Move migrations to a separate pre-deployment step or run only in master process
# run_database_migrations()








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
    # Get port from environment variable, default to 4000
    port = int(os.getenv('BACKEND_PORT', 4000))
    app.run(debug=True, host='127.0.0.1', port=port)