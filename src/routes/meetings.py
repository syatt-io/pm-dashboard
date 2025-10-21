"""Meeting management and analysis API endpoints."""

from flask import Blueprint, jsonify, request, render_template, session, redirect
from datetime import datetime
import logging
import asyncio
import os
import json

from config.settings import settings
from src.services.auth import auth_required
from src.integrations.fireflies import FirefliesClient
from src.processors.transcript_analyzer import TranscriptAnalyzer
from src.utils.database import get_engine, session_scope

logger = logging.getLogger(__name__)

# Create blueprint
meetings_bp = Blueprint('meetings', __name__)

# Initialize analyzer
analyzer = TranscriptAnalyzer()


# Import response helpers from parent module
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


# Helper function for project keyword mapping
def get_project_keywords_from_db():
    """Get project keywords mapping from database."""
    from sqlalchemy import text
    try:
        engine = get_engine()
        with engine.connect() as conn:
            # Aggregate keywords by project_key (note: column is 'keyword' not 'keywords')
            result = conn.execute(text("""
                SELECT project_key, array_agg(LOWER(keyword)) as keywords
                FROM project_keywords
                GROUP BY project_key
            """))
            return {row[0]: row[1] for row in result}
    except Exception as e:
        logger.warning(f"Error loading project keywords: {e}")
        return {}


# =============================================================================
# Page Routes
# =============================================================================

@meetings_bp.route('/meetings')
def meetings_dashboard():
    """Dashboard showing recent meetings."""
    try:
        # Get Fireflies client
        from src.integrations.fireflies import FirefliesClient
        fireflies = FirefliesClient(settings.fireflies.api_key)

        meetings = fireflies.get_recent_meetings(days_back=10, limit=200)

        # Check which meetings have been analyzed
        from src.models import ProcessedMeeting

        analyzed_meetings = {}
        with session_scope() as db_session:
            processed_meetings = db_session.query(ProcessedMeeting).all()
            for pm in processed_meetings:
                if pm.analyzed_at:
                    analyzed_meetings[pm.meeting_id] = pm.analyzed_at

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


@meetings_bp.route('/analyze/<meeting_id>')
def analyze_meeting(meeting_id):
    """Analyze a specific meeting and show results."""
    force_reanalyze = request.args.get('reanalyze', 'false').lower() == 'true'

    try:
        # Check if meeting has been analyzed before (unless forcing re-analysis)
        from src.models import ProcessedMeeting, ProcessedMeetingDTO

        cached_meeting_dto = None
        if not force_reanalyze:
            with session_scope() as db_session:
                cached_meeting = db_session.query(ProcessedMeeting).filter_by(fireflies_id=meeting_id).first()
                if cached_meeting:
                    cached_meeting_dto = ProcessedMeetingDTO.from_orm(cached_meeting)

        if cached_meeting_dto and cached_meeting_dto.analyzed_at:
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

            analysis = CachedAnalysis(cached_meeting_dto)

            # Store in session for later processing
            session['current_analysis'] = {
                'meeting_id': meeting_id,
                'meeting_title': cached_meeting_dto.title,
                'meeting_date': cached_meeting_dto.date.isoformat() if cached_meeting_dto.date else '',
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
                'analyzed_at': cached_meeting_dto.analyzed_at.isoformat() if cached_meeting_dto.analyzed_at else None
            }

            breadcrumbs = [
                {'title': 'Home', 'url': '/'},
                {'title': 'Meetings', 'url': '/'},
                {'title': f'{cached_meeting_dto.title}', 'url': f'/analyze/{meeting_id}'},
                {'title': 'Analysis Results', 'url': '#'}
            ]

            return render_template('analysis_new.html',
                                 meeting_title=cached_meeting_dto.title,
                                 analysis=analysis,
                                 is_cached=True,
                                 analyzed_at=cached_meeting_dto.analyzed_at,
                                 meeting_id=meeting_id,
                                 breadcrumbs=breadcrumbs)

        # No cached analysis or forcing re-analysis - perform new analysis
        logger.info(f"Performing {'re-' if force_reanalyze else ''}analysis for meeting {meeting_id}")

        # Get meeting transcript
        from src.integrations.fireflies import FirefliesClient
        fireflies = FirefliesClient(settings.fireflies.api_key)

        transcript = fireflies.get_meeting_transcript(meeting_id)
        if not transcript:
            return render_template('error.html', error="Could not fetch meeting transcript")

        # Convert date from milliseconds to datetime if needed
        meeting_date = transcript.get('date')
        if isinstance(meeting_date, (int, float)) and meeting_date > 1000000000000:
            meeting_date = datetime.fromtimestamp(meeting_date / 1000)
        elif not isinstance(meeting_date, datetime):
            meeting_date = datetime.now()

        # Analyze with AI
        analysis = analyzer.analyze_transcript(
            transcript['transcript'],
            transcript['title'],
            meeting_date
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
        with session_scope() as db_session:
            existing_meeting = db_session.query(ProcessedMeeting).filter_by(fireflies_id=meeting_id).first()

            if existing_meeting:
                # Update existing record - Always serialize to JSON, even empty lists
                existing_meeting.analyzed_at = analyzed_at
                existing_meeting.summary = analysis.summary
                existing_meeting.key_decisions = json.dumps(analysis.key_decisions or [])
                existing_meeting.blockers = json.dumps(analysis.blockers or [])
                existing_meeting.action_items = json.dumps(action_items_data)  # Always serialize
                existing_meeting.title = transcript['title']
                existing_meeting.date = meeting_date
                logger.info(f"Updated existing processed meeting record for {meeting_id}")
            else:
                # Create new record - Always serialize to JSON, even empty lists
                import uuid
                import json
                processed_meeting = ProcessedMeeting(
                    id=str(uuid.uuid4()),
                    fireflies_id=meeting_id,
                    title=transcript['title'],
                    date=meeting_date,
                    analyzed_at=analyzed_at,
                    summary=analysis.summary,
                    key_decisions=json.dumps(analysis.key_decisions or []),
                    blockers=json.dumps(analysis.blockers or []),
                    action_items=json.dumps(action_items_data)  # Always serialize
                )
                db_session.add(processed_meeting)
                logger.info(f"Created new processed meeting record for {meeting_id}")

        # Store in session for later processing
        session['current_analysis'] = {
            'meeting_id': meeting_id,
            'meeting_title': transcript['title'],
            'meeting_date': meeting_date.isoformat(),
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
            {'title': f"{transcript['title']}", 'url': f'/analyze/{meeting_id}'},
            {'title': 'Analysis Results', 'url': '#'}
        ]

        return render_template('analysis_new.html',
                             meeting_title=transcript['title'],
                             analysis=analysis,
                             is_cached=False,
                             analyzed_at=analyzed_at,
                             meeting_id=meeting_id,
                             breadcrumbs=breadcrumbs)

    except Exception as e:
        logger.error(f"Error analyzing meeting {meeting_id}: {e}")
        return render_template('error.html', error=str(e))


@meetings_bp.route('/review')
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


# =============================================================================
# API Routes
# =============================================================================

@meetings_bp.route("/api/meetings", methods=["GET"])
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
                    # Use fireflies_id as the key to match Fireflies API meeting IDs
                    cached_analyses[cached.fireflies_id] = ProcessedMeetingDTO.from_orm(cached)
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


@meetings_bp.route("/api/meetings/<meeting_id>", methods=["GET"])
@auth_required
def get_meeting_detail(user, meeting_id):
    """Get details for a specific meeting."""
    try:
        from src.models import ProcessedMeeting, ProcessedMeetingDTO

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
        cached_dto = None
        with session_scope() as db_session:
            cached = db_session.query(ProcessedMeeting).filter_by(fireflies_id=meeting_id).first()
            if cached:
                cached_dto = ProcessedMeetingDTO.from_orm(cached)

        # Convert date from milliseconds to datetime if needed
        meeting_date = transcript.get('date')
        if isinstance(meeting_date, (int, float)) and meeting_date > 1000000000000:
            meeting_date = datetime.fromtimestamp(meeting_date / 1000)
        elif not isinstance(meeting_date, datetime):
            meeting_date = datetime.now()

        # Build the response
        meeting_data = {
            'id': transcript['id'],
            'meeting_id': transcript['id'],
            'title': transcript['title'],
            'date': meeting_date.isoformat(),
            'duration': transcript['duration'],
            'transcript': transcript['transcript'],
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


@meetings_bp.route("/api/meetings/<meeting_id>/analyze", methods=["POST"])
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

        # Convert date from milliseconds to datetime if needed
        meeting_date = transcript.get('date')
        if isinstance(meeting_date, (int, float)) and meeting_date > 1000000000000:
            meeting_date = datetime.fromtimestamp(meeting_date / 1000)
        elif not isinstance(meeting_date, datetime):
            meeting_date = datetime.now()

        # Analyze with AI using global analyzer
        analysis = analyzer.analyze_transcript(
            transcript['transcript'],
            transcript['title'],
            meeting_date
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
            existing_meeting = db_session.query(ProcessedMeeting).filter_by(fireflies_id=meeting_id).first()

            if existing_meeting:
                # Update existing record - Always serialize to JSON, even empty lists
                existing_meeting.analyzed_at = analyzed_at
                existing_meeting.summary = analysis.summary
                existing_meeting.key_decisions = json.dumps(analysis.key_decisions or [])
                existing_meeting.blockers = json.dumps(analysis.blockers or [])
                existing_meeting.action_items = json.dumps(action_items_data)  # Always serialize
                existing_meeting.title = transcript['title']
                existing_meeting.date = meeting_date
                logger.info(f"Updated existing processed meeting record for {meeting_id}")
            else:
                # Create new record - Always serialize to JSON, even empty lists
                import uuid
                import json
                processed_meeting = ProcessedMeeting(
                    id=str(uuid.uuid4()),
                    fireflies_id=meeting_id,
                    title=transcript['title'],
                    date=meeting_date,
                    analyzed_at=analyzed_at,
                    summary=analysis.summary,
                    key_decisions=json.dumps(analysis.key_decisions or []),
                    blockers=json.dumps(analysis.blockers or []),
                    action_items=json.dumps(action_items_data)  # Always serialize
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


@meetings_bp.route('/api/meeting-project-analysis/<meeting_id>')
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


@meetings_bp.route('/api/project-meetings/<project_key>')
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


@meetings_bp.route('/api/project-suggestions/<project_key>')
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


@meetings_bp.route('/api/meeting-project-dashboard')
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


@meetings_bp.route('/api/process', methods=['POST'])
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
        async def _execute_decisions(decisions, analysis):
            """Execute user decisions asynchronously."""
            results = []
            # Implementation here would process each decision
            # This is a placeholder - actual implementation would be more complex
            return results

        results = asyncio.run(_execute_decisions(decisions, analysis))

        return jsonify(results)

    except Exception as e:
        logger.error(f"Error processing decisions: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500