"""Dashboard statistics and admin routes."""
from flask import Blueprint, jsonify
from sqlalchemy import func, and_, or_, text
import logging

from src.services.auth import auth_required
from src.utils.database import session_scope, get_engine
from main import TodoItem

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/api/dashboard')


@dashboard_bp.route('/stats', methods=['GET'])
@auth_required
def get_dashboard_stats(user):
    """Get dashboard statistics efficiently (counts only, no full records)."""
    try:
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

            # Count active projects
            try:
                from src.models import JiraProject
                total_projects = db_session.query(func.count(JiraProject.key)).filter(
                    JiraProject.is_active == True
                ).scalar() or 0
            except (ImportError, AttributeError):
                # If JiraProject model doesn't exist, return 0
                total_projects = 0

            return jsonify({
                'success': True,
                'data': {
                    'total_meetings': total_meetings,
                    'total_todos': total_todos,
                    'completed_todos': completed_todos,
                    'active_todos': total_todos - completed_todos,
                    'total_projects': total_projects,
                    'todo_completion_rate': round((completed_todos / total_todos * 100) if total_todos > 0 else 0)
                }
            })

    except Exception as e:
        logger.error(f"Error fetching dashboard stats: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@dashboard_bp.route('/admin/create-users-table', methods=['POST', 'GET'])
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
