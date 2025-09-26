"""Web-based interface for interactive meeting processing."""

from flask import Flask, render_template, request, jsonify, session, redirect
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


logger = logging.getLogger(__name__)

import os
template_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'templates')
app = Flask(__name__, template_folder=template_dir)
app.secret_key = 'your-secret-key-here'  # Change in production

# Enable CORS for React frontend
CORS(app, origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:3002"])

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


def run_database_migrations():
    """Run any necessary database migrations."""
    try:
        from sqlalchemy import create_engine, text
        engine = create_engine(settings.agent.database_url)

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

    except Exception as e:
        logger.warning(f"Migration failed: {e}")

# Run migrations on startup
run_database_migrations()


@app.route('/')
def main_dashboard():
    """Main landing page - redirects to project dashboard or setup form."""
    try:
        # Check if user has set up their email/profile
        user_email = session.get('user_email')

        if user_email:
            # User is set up, redirect to their project dashboard
            return redirect(f'/my-projects/dashboard/{user_email}')
        else:
            # New user, show setup form
            return redirect('/my-projects')
    except Exception as e:
        logger.error(f"Error in main dashboard: {e}")
        return render_template('error.html', error=str(e))

@app.route('/meetings')
def meetings_dashboard():
    """Dashboard showing recent meetings."""
    try:
        meetings = fireflies.get_recent_meetings(days_back=10, limit=200)

        # Check which meetings have been analyzed
        from main import ProcessedMeeting
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy import create_engine

        engine = create_engine(settings.agent.database_url)
        Session = sessionmaker(bind=engine)
        db_session = Session()

        analyzed_meetings = {}
        processed_meetings = db_session.query(ProcessedMeeting).all()
        for pm in processed_meetings:
            if pm.analyzed_at:
                analyzed_meetings[pm.meeting_id] = pm.analyzed_at

        db_session.close()

        # Format meetings for display
        formatted_meetings = []
        for meeting in meetings:
            date_val = meeting.get('date', 0)
            if isinstance(date_val, (int, float)) and date_val > 1000000000000:
                meeting_date = datetime.fromtimestamp(date_val / 1000)
                date_str = meeting_date.strftime('%Y-%m-%d %I:%M %p')
            else:
                date_str = str(date_val)

            meeting_id = meeting['id']
            analyzed_at = analyzed_meetings.get(meeting_id)

            formatted_meetings.append({
                'id': meeting_id,
                'title': meeting.get('title', 'Untitled'),
                'date': date_str,
                'duration': meeting.get('duration', 0),
                'is_analyzed': analyzed_at is not None,
                'analyzed_at': analyzed_at.strftime('%Y-%m-%d %I:%M %p') if analyzed_at else None
            })

        breadcrumbs = [
            {'title': 'Home', 'url': '/'}
        ]
        return render_template('dashboard_new.html', meetings=formatted_meetings, breadcrumbs=breadcrumbs)

    except Exception as e:
        return render_template('error.html', error=str(e))


@app.route('/analyze/<meeting_id>')
def analyze_meeting(meeting_id):
    """Analyze a specific meeting and show results."""
    force_reanalyze = request.args.get('reanalyze', 'false').lower() == 'true'

    try:
        # Check if meeting has been analyzed before (unless forcing re-analysis)
        from main import ProcessedMeeting
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy import create_engine

        engine = create_engine(settings.agent.database_url)
        Session = sessionmaker(bind=engine)
        db_session = Session()

        cached_meeting = None
        if not force_reanalyze:
            cached_meeting = db_session.query(ProcessedMeeting).filter_by(meeting_id=meeting_id).first()

        if cached_meeting and cached_meeting.analyzed_at:
            # Use cached analysis results
            logger.info(f"Using cached analysis for meeting {meeting_id}")

            # Recreate analysis object from cached data
            class CachedAnalysis:
                def __init__(self, cached_data):
                    self.summary = cached_data.summary
                    self.key_decisions = cached_data.key_decisions or []
                    self.blockers = cached_data.blockers or []
                    # Convert action items back to objects
                    self.action_items = []
                    for item_data in (cached_data.action_items or []):
                        class ActionItem:
                            def __init__(self, data):
                                self.title = data.get('title', '')
                                self.description = data.get('description', '')
                                self.assignee = data.get('assignee', '')
                                self.due_date = data.get('due_date', '')
                                self.priority = data.get('priority', 'Medium')
                                self.context = data.get('context', '')
                        self.action_items.append(ActionItem(item_data))

            analysis = CachedAnalysis(cached_meeting)

            # Store in session for later processing
            session['current_analysis'] = {
                'meeting_id': meeting_id,
                'meeting_title': cached_meeting.title,
                'meeting_date': cached_meeting.date.isoformat() if cached_meeting.date else '',
                'summary': analysis.summary,
                'key_decisions': analysis.key_decisions,
                'blockers': analysis.blockers,
                'action_items': [
                    {
                        'title': item.title,
                        'description': item.description,
                        'assignee': item.assignee,
                        'due_date': item.due_date,
                        'priority': item.priority,
                        'context': item.context
                    }
                    for item in analysis.action_items
                ],
                'is_cached': True,
                'analyzed_at': cached_meeting.analyzed_at.isoformat() if cached_meeting.analyzed_at else None
            }

            db_session.close()

            breadcrumbs = [
                {'title': 'Home', 'url': '/'},
                {'title': 'Meetings', 'url': '/'},
                {'title': f'{cached_meeting.title}', 'url': f'/analyze/{meeting_id}'},
                {'title': 'Analysis Results', 'url': '#'}
            ]

            return render_template('analysis_new.html',
                                 meeting_title=cached_meeting.title,
                                 analysis=analysis,
                                 is_cached=True,
                                 analyzed_at=cached_meeting.analyzed_at,
                                 meeting_id=meeting_id,
                                 breadcrumbs=breadcrumbs)

        # No cached analysis or forcing re-analysis - perform new analysis
        logger.info(f"Performing {'re-' if force_reanalyze else ''}analysis for meeting {meeting_id}")

        # Get meeting transcript
        transcript = fireflies.get_meeting_transcript(meeting_id)
        if not transcript:
            db_session.close()
            return render_template('error.html', error="Could not fetch meeting transcript")

        # Analyze with AI
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

        # Always check for existing record to handle race conditions
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

        db_session.commit()
        db_session.close()

        # Store in session for later processing
        session['current_analysis'] = {
            'meeting_id': meeting_id,
            'meeting_title': transcript.title,
            'meeting_date': transcript.date.isoformat(),
            'summary': analysis.summary,
            'key_decisions': analysis.key_decisions,
            'blockers': analysis.blockers,
            'action_items': action_items_data,
            'is_cached': False,
            'analyzed_at': analyzed_at.isoformat()
        }

        breadcrumbs = [
            {'title': 'Home', 'url': '/'},
            {'title': 'Meetings', 'url': '/'},
            {'title': f'{transcript.title}', 'url': f'/analyze/{meeting_id}'},
            {'title': 'Analysis Results', 'url': '#'}
        ]

        return render_template('analysis_new.html',
                             meeting_title=transcript.title,
                             analysis=analysis,
                             is_cached=False,
                             analyzed_at=analyzed_at,
                             meeting_id=meeting_id,
                             breadcrumbs=breadcrumbs)

    except Exception as e:
        logger.error(f"Error analyzing meeting {meeting_id}: {e}")
        return render_template('error.html', error=str(e))


@app.route('/review')
def review_items():
    """Review action items interactively."""
    analysis = session.get('current_analysis')
    if not analysis:
        return redirect('/')

    breadcrumbs = [
        {'title': 'Home', 'url': '/'},
        {'title': 'Meetings', 'url': '/'},
        {'title': analysis['meeting_title'], 'url': f"/analyze/{analysis['meeting_id']}"},
        {'title': 'Review & Process', 'url': '#'}
    ]

    return render_template('review.html',
                         meeting_title=analysis['meeting_title'],
                         action_items=analysis['action_items'],
                         breadcrumbs=breadcrumbs)


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


@app.route('/todos')
def todo_dashboard():
    """Display TODO dashboard with active TODOs."""
    try:
        # Get summary and categorized TODOs
        summary = todo_manager.get_todo_summary()
        overdue_todos = todo_manager.get_overdue_todos()
        active_todos = todo_manager.get_active_todos()

        breadcrumbs = [
            {'title': 'Home', 'url': '/'},
            {'title': 'TODO Dashboard', 'url': '/todos'}
        ]

        return render_template('todos.html',
                             summary=summary,
                             overdue_todos=overdue_todos,
                             active_todos=active_todos,
                             breadcrumbs=breadcrumbs)

    except Exception as e:
        return render_template('error.html', error=f"TODO Dashboard Error: {str(e)}")


@app.route('/api/todos', methods=['GET'])
def get_todos():
    """Get all TODO items for React Admin."""
    try:
        from main import TodoItem
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        engine = create_engine(settings.agent.database_url)
        Session = sessionmaker(bind=engine)
        db_session = Session()

        # Get pagination parameters
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('perPage', 25))
        sort_field = request.args.get('sort', 'created_at')
        sort_order = request.args.get('order', 'DESC')

        # Calculate offset
        offset = (page - 1) * per_page

        # Build query
        query = db_session.query(TodoItem)

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

        db_session.close()

        # Return in React Admin format
        return jsonify({
            'data': todo_list,
            'total': total
        })

    except Exception as e:
        logger.error(f"Error fetching todos: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/todos', methods=['POST'])
def create_todo():
    """Create a new TODO item."""
    try:
        data = request.json

        # Import here to avoid circular imports
        from main import TodoItem
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

        return jsonify({'success': True, 'id': todo.id})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/todos/<todo_id>/complete', methods=['POST'])
def complete_todo_api(todo_id):
    """Mark a TODO as complete."""
    try:
        data = request.json or {}
        completed_by = data.get('completed_by', 'Web User')
        notes = data.get('notes', '')

        success = todo_manager.complete_todo(todo_id, completed_by, notes)

        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'TODO not found'}), 404

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/todos/<todo_id>/snooze', methods=['POST'])
def snooze_todo_api(todo_id):
    """Snooze a TODO by extending its due date."""
    try:
        data = request.json or {}
        days = data.get('days', 1)

        success = todo_manager.snooze_todo(todo_id, days)

        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'TODO not found'}), 404

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/todos/<todo_id>/update', methods=['POST'])
def update_todo_api(todo_id):
    """Update a TODO item."""
    try:
        data = request.json or {}
        success = todo_manager.update_todo(todo_id, data)

        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'TODO not found'}), 404

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/todos/<todo_id>', methods=['GET'])
def get_todo_api(todo_id):
    """Get a single TODO item (React Admin compatible)."""
    try:
        todo = todo_manager.get_todo(todo_id)
        if not todo:
            return jsonify({'error': 'TODO not found'}), 404

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
        return jsonify({'error': str(e)}), 500


@app.route('/api/todos/<todo_id>', methods=['PUT'])
def update_todo_put_api(todo_id):
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
                return jsonify({'success': False, 'error': 'TODO not found after update'}), 404
        else:
            return jsonify({'success': False, 'error': 'TODO not found'}), 404

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/todos/<todo_id>', methods=['DELETE'])
def delete_todo_api(todo_id):
    """Delete a TODO item."""
    try:
        success = todo_manager.delete_todo(todo_id)

        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'TODO not found'}), 404

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/todos/edit/<todo_id>')
def edit_todo_page(todo_id):
    """Show edit page for a TODO item."""
    try:
        from main import TodoItem
        todo = todo_manager.session.query(TodoItem).filter_by(id=todo_id).first()
        if not todo:
            return render_template('error.html', error="TODO not found")

        breadcrumbs = [
            {'title': 'Home', 'url': '/'},
            {'title': 'TODO Dashboard', 'url': '/todos'},
            {'title': f'Edit: {todo.title[:30]}...', 'url': '#'}
        ]

        return render_template('edit_todo.html', todo=todo, breadcrumbs=breadcrumbs)

    except Exception as e:
        return render_template('error.html', error=f"Edit TODO Error: {str(e)}")


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
def get_meetings():
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

        logger.info(f"Fetching live meetings - date_range={date_range}, projects={projects}")

        # Initialize Fireflies client
        fireflies_client = FirefliesClient(settings.fireflies.api_key)

        # Fetch live meetings from Fireflies
        if date_range == 'all':
            days_back = 90  # Reasonable limit for 'all'
        else:
            try:
                days_back = int(date_range)
            except ValueError:
                days_back = 7

        live_meetings = fireflies_client.get_recent_meetings(days_back=days_back, limit=200)
        logger.info(f"Fetched {len(live_meetings)} meetings from Fireflies")

        # Get cached analysis data for overlay
        from main import ProcessedMeeting
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        engine = create_engine(settings.agent.database_url)
        Session = sessionmaker(bind=engine)
        db_session = Session()

        # Create lookup dict for cached analysis
        cached_analyses = {}
        try:
            all_cached = db_session.query(ProcessedMeeting).all()
            for cached in all_cached:
                cached_analyses[cached.meeting_id] = cached
        except Exception as e:
            logger.warning(f"Error loading cached analyses: {e}")
        finally:
            db_session.close()

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
                            # Create better keyword mapping for projects
                            project_keywords = {
                                'BEAU': ['beauchamp', 'beau', 'beauchamps', 'bc'],
                                'RNWL': ['renewal', 'rnwl', 'renew', 'renewals', 'renwil', 'renwl', 'renwal'],
                                'SUBS': ['snuggle bugz', 'subs', 'subscription', 'snugglebugz', 'snuggle', 'bugz', 'sb'],
                                'IRIS': ['iris', 'eye', 'eyes', 'optical', 'vision', 'eyecare'],
                            }

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
def get_meeting_detail(meeting_id):
    """Get details for a specific meeting."""
    try:
        # Initialize database session
        from main import ProcessedMeeting
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        engine = create_engine(settings.agent.database_url)
        Session = sessionmaker(bind=engine)
        db_session = Session()

        # Initialize Fireflies client
        if not settings.fireflies.api_key:
            return jsonify({'error': 'Fireflies API key not configured'}), 500

        fireflies_client = FirefliesClient(api_key=settings.fireflies.api_key)

        # Get the meeting transcript from Fireflies
        transcript = fireflies_client.get_meeting_transcript(meeting_id)
        if not transcript:
            return jsonify({'error': 'Meeting not found'}), 404

        # Check if we have analysis cached for this meeting
        cached = db_session.query(ProcessedMeeting).filter_by(meeting_id=meeting_id).first()

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
        if cached:
            meeting_data.update({
                'action_items_count': getattr(cached, 'action_items_count', 0),
                'relevance_score': getattr(cached, 'relevance_score', 0),
                'confidence': getattr(cached, 'confidence', 0),
                'analyzed_at': cached.analyzed_at.isoformat() if cached.analyzed_at else None,
                'action_items': getattr(cached, 'action_items', []),
                'key_decisions': getattr(cached, 'key_decisions', []),
                'blockers': getattr(cached, 'blockers', []),
                'follow_ups': getattr(cached, 'follow_ups', []),
                'summary': getattr(cached, 'summary', None)
            })

        return jsonify(meeting_data)

    except Exception as e:
        logger.error(f"Error fetching meeting detail for {meeting_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route("/api/meetings/<meeting_id>/analyze", methods=["POST"])
def analyze_meeting_api(meeting_id):
    """Trigger analysis for a specific meeting via API."""
    try:
        # Initialize database
        from main import ProcessedMeeting
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        engine = create_engine(settings.agent.database_url)
        Session = sessionmaker(bind=engine)
        db_session = Session()

        # Get meeting transcript using global fireflies client
        transcript = fireflies.get_meeting_transcript(meeting_id)
        if not transcript:
            db_session.close()
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

        db_session.commit()
        db_session.close()

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
        # Fetch projects from Jira
        async def fetch_projects():
            async with JiraMCPClient(
                jira_url=settings.jira.url,
                username=settings.jira.username,
                api_token=settings.jira.api_token
            ) as jira_client:
                return await jira_client.get_projects()

        jira_projects = asyncio.run(fetch_projects())

        # Merge with local database data
        from sqlalchemy import create_engine, text
        engine = create_engine(settings.agent.database_url)

        enhanced_projects = []
        with engine.connect() as conn:
            for project in jira_projects:
                # Get local project data
                result = conn.execute(text(
                    "SELECT forecasted_hours_month, is_active, project_work_type, total_hours, current_month_hours, cumulative_hours, slack_channel, weekly_meeting_day FROM projects WHERE key = :key"
                ), {"key": project["key"]}).fetchone()

                enhanced_project = project.copy()
                if result:
                    enhanced_project["forecasted_hours_month"] = float(result[0]) if result[0] else 0
                    enhanced_project["is_active"] = bool(result[1]) if result[1] is not None else True
                    enhanced_project["project_work_type"] = result[2] if result[2] else 'project-based'
                    enhanced_project["total_hours"] = float(result[3]) if result[3] else 0
                    enhanced_project["current_month_hours"] = float(result[4]) if result[4] else 0
                    enhanced_project["cumulative_hours"] = float(result[5]) if result[5] else 0
                    enhanced_project["slack_channel"] = result[6] if result[6] else None
                    enhanced_project["weekly_meeting_day"] = result[7] if result[7] else None

                    # Debug logging for BEAU
                    if project["key"] == "BEAU":
                        logger.info(f"BEAU project found in database: current_month_hours={result[4]}, cumulative_hours={result[5]}")
                        logger.info(f"BEAU enhanced_project after assignment: {enhanced_project.get('current_month_hours')}, {enhanced_project.get('cumulative_hours')}")
                else:
                    enhanced_project["forecasted_hours_month"] = 0
                    enhanced_project["is_active"] = True
                    enhanced_project["project_work_type"] = 'project-based'
                    enhanced_project["total_hours"] = 0
                    enhanced_project["current_month_hours"] = 0
                    enhanced_project["cumulative_hours"] = 0
                    enhanced_project["slack_channel"] = None
                    enhanced_project["weekly_meeting_day"] = None

                    # Debug logging for BEAU
                    if project["key"] == "BEAU":
                        logger.info(f"BEAU project NOT found in database - using defaults")

                enhanced_projects.append(enhanced_project)

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


# My Projects Routes
@app.route('/my-projects')
def my_projects():
    """Show My Projects configuration page."""
    breadcrumbs = [
        {'title': 'Home', 'url': '/'},
        {'title': 'My Projects', 'url': '/my-projects'}
    ]
    return render_template('my_projects.html', breadcrumbs=breadcrumbs)


@app.route('/api/my-projects/user/<email>', methods=['GET'])
def get_user_settings(email):
    """Get user settings by email."""
    try:
        from main import UserPreference
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy import create_engine

        engine = create_engine(settings.agent.database_url)
        Session = sessionmaker(bind=engine)
        db_session = Session()

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
            db_session.close()
            return jsonify({'success': True, 'user_settings': settings_data})
        else:
            db_session.close()
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
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy import create_engine
        import uuid

        engine = create_engine(settings.agent.database_url)
        Session = sessionmaker(bind=engine)
        db_session = Session()

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

        db_session.commit()
        db_session.close()

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
        from sqlalchemy import create_engine, text
        engine = create_engine(settings.agent.database_url)

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


@app.route('/my-projects/dashboard/<email>')
def project_dashboard(email):
    """Show project changes dashboard for a user."""
    try:
        from src.services.project_monitor import ProjectMonitor
        from datetime import datetime, timedelta

        # Get days parameter from query string, default to 7 days
        days = request.args.get('days', 7, type=int)

        # Get recent changes with debug info
        monitor = ProjectMonitor()
        since = datetime.now() - timedelta(days=days)
        changes = asyncio.run(monitor.get_user_project_changes(email, since))

        logger.info(f"Dashboard for {email}: Found {len(changes)} changes since {since}")

        # Group changes by project
        changes_by_project = {}
        for change in changes:
            project_key = change['project_key']
            if project_key not in changes_by_project:
                changes_by_project[project_key] = []
            changes_by_project[project_key].append(change)

        # Sort each project's changes by timestamp (newest first)
        for project_key in changes_by_project:
            changes_by_project[project_key].sort(key=lambda x: x['change_timestamp'], reverse=True)

        # If no changes, try to get user preferences to show selected projects
        user_projects = []
        try:
            from main import UserPreference
            from sqlalchemy.orm import sessionmaker
            from sqlalchemy import create_engine

            engine = create_engine(settings.agent.database_url)
            Session = sessionmaker(bind=engine)
            db_session = Session()

            user_pref = db_session.query(UserPreference).filter_by(email=email).first()
            if user_pref:
                user_projects = user_pref.selected_projects or []
                logger.info(f"User {email} has selected projects: {user_projects}")

            db_session.close()
        except Exception as e:
            logger.error(f"Error getting user projects: {e}")

        breadcrumbs = [
            {'title': 'Home', 'url': '/'},
            {'title': 'My Projects', 'url': '/my-projects'},
            {'title': f'Dashboard - {email}', 'url': f'/my-projects/dashboard/{email}'}
        ]

        return render_template('project_dashboard.html',
                             email=email,
                             changes=changes,
                             changes_by_project=changes_by_project,
                             user_projects=user_projects,
                             breadcrumbs=breadcrumbs)

    except Exception as e:
        logger.error(f"Error loading project dashboard: {e}")
        return render_template('error.html', error=str(e))


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
                from sqlalchemy.orm import sessionmaker
                from sqlalchemy import create_engine

                engine = create_engine(settings.agent.database_url)
                Session = sessionmaker(bind=engine)
                db_session = Session()

                user_pref = db_session.query(UserPreference).filter_by(email=email).first()
                if user_pref and user_pref.selected_projects:
                    project_keys = user_pref.selected_projects

                db_session.close()

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

        engine = create_engine(settings.agent.database_url)
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
                    from main import TodoItem
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

if __name__ == '__main__':
    # Create templates directory and files
    import os
    os.makedirs('templates', exist_ok=True)

    with open('templates/dashboard.html', 'w') as f:
        f.write(DASHBOARD_TEMPLATE)

    with open('templates/analysis.html', 'w') as f:
        f.write(ANALYSIS_TEMPLATE)

    app.run(debug=True, host='127.0.0.1', port=3030)