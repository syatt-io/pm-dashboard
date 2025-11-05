"""Meeting management and analysis API endpoints."""

from flask import Blueprint, jsonify, request, session
from datetime import datetime
import logging
import asyncio
import os
import json
import re

from config.settings import settings
from src.services.auth import auth_required, admin_required
from src.integrations.fireflies import FirefliesClient
from src.processors.transcript_analyzer import TranscriptAnalyzer
from src.utils.database import get_engine, session_scope
from src.utils.cache_manager import cached_endpoint, invalidate_cache

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


# =============================================================================
# API Routes
# =============================================================================

@meetings_bp.route("/api/meetings", methods=["GET"])
@auth_required
@cached_endpoint('meetings', ttl=3600, user_specific=True, exclude_params=['page', 'perPage', 'sort_field', 'sort', 'sort_order', 'order'])
def get_meetings(user):
    """Get meetings using live Fireflies data with cached analysis overlay.

    Cached for 1 hour (3600 seconds) with per-user caching (user-specific filtering).
    Cache is invalidated when meetings are analyzed.
    """
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

                            # Use word boundary regex matching to prevent false positives
                            # e.g., "project" won't match "projections"
                            def matches_keyword(text, keyword):
                                # Escape special regex characters in the keyword
                                escaped_keyword = re.escape(keyword)
                                # Match whole words only using word boundaries
                                pattern = r'\b' + escaped_keyword + r'\b'
                                return bool(re.search(pattern, text, re.IGNORECASE))

                            project_match = any(
                                matches_keyword(title_lower, keyword) or matches_keyword(summary_lower, keyword)
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
            # New topic-based structure
            'topics': [],
            # Legacy fields for backward compatibility (deprecated)
            'executive_summary': None,
            'outcomes': [],
            'blockers_and_constraints': [],
            'timeline_and_milestones': [],
            'key_discussions': [],
            'key_decisions': [],
            'blockers': [],
            'follow_ups': [],
            'summary': None
        }

        # Add cached analysis data if available
        if cached_dto:
            logger.info(f"Found cached analysis for meeting {meeting_id}")
            logger.info(f"  topics count: {len(cached_dto.topics) if cached_dto.topics else 0}")
            logger.info(f"  action_items count: {len(cached_dto.action_items) if cached_dto.action_items else 0}")

            meeting_data.update({
                'action_items_count': len(cached_dto.action_items) if cached_dto.action_items else 0,
                'relevance_score': 0,  # Not stored in DTO currently
                'confidence': 0,  # Not stored in DTO currently
                'analyzed_at': cached_dto.analyzed_at.isoformat() if cached_dto.analyzed_at else None,
                'action_items': cached_dto.action_items or [],
                # New topic-based structure
                'topics': cached_dto.topics or [],
                # Legacy fields for backward compatibility (deprecated)
                'executive_summary': cached_dto.executive_summary if hasattr(cached_dto, 'executive_summary') else None,
                'outcomes': cached_dto.outcomes or [] if hasattr(cached_dto, 'outcomes') else [],
                'blockers_and_constraints': cached_dto.blockers_and_constraints or [] if hasattr(cached_dto, 'blockers_and_constraints') else [],
                'timeline_and_milestones': cached_dto.timeline_and_milestones or [] if hasattr(cached_dto, 'timeline_and_milestones') else [],
                'key_discussions': cached_dto.key_discussions or [] if hasattr(cached_dto, 'key_discussions') else [],
                'key_decisions': cached_dto.key_decisions or [] if hasattr(cached_dto, 'key_decisions') else [],
                'blockers': cached_dto.blockers or [] if hasattr(cached_dto, 'blockers') else [],
                'follow_ups': [],  # Not stored in DTO currently
                'summary': cached_dto.summary if hasattr(cached_dto, 'summary') else None
            })

            logger.info(f"Returning meeting_data with {len(meeting_data.get('topics', []))} topics")
        else:
            logger.warning(f"No cached analysis found for meeting {meeting_id}")

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
                # New topic-based structure
                topics_data = [
                    {
                        "title": topic.title,
                        "content_items": topic.content_items
                    }
                    for topic in analysis.topics
                ] if analysis.topics else []
                existing_meeting.topics = json.dumps(topics_data)
                existing_meeting.action_items = json.dumps(action_items_data)  # Always serialize
                # Legacy fields for backward compatibility (deprecated, will be removed in future)
                existing_meeting.executive_summary = None  # No longer generated
                existing_meeting.outcomes = json.dumps([])
                existing_meeting.blockers_and_constraints = json.dumps([])
                existing_meeting.timeline_and_milestones = json.dumps([])
                existing_meeting.key_discussions = json.dumps([])
                existing_meeting.summary = None
                existing_meeting.key_decisions = json.dumps([])
                existing_meeting.blockers = json.dumps([])
                existing_meeting.title = transcript['title']
                existing_meeting.date = meeting_date
                logger.info(f"Updated existing processed meeting record for {meeting_id} with {len(topics_data)} topics")
            else:
                # Create new record - Always serialize to JSON, even empty lists
                import uuid
                # Convert topics to dict format for JSON storage
                topics_data = [
                    {
                        "title": topic.title,
                        "content_items": topic.content_items
                    }
                    for topic in analysis.topics
                ] if analysis.topics else []

                processed_meeting = ProcessedMeeting(
                    id=str(uuid.uuid4()),
                    fireflies_id=meeting_id,
                    title=transcript['title'],
                    date=meeting_date,
                    analyzed_at=analyzed_at,
                    # New topic-based structure
                    topics=json.dumps(topics_data),
                    action_items=json.dumps(action_items_data),  # Always serialize
                    # Legacy fields for backward compatibility (deprecated, will be removed in future)
                    executive_summary=None,  # No longer generated
                    outcomes=json.dumps([]),
                    blockers_and_constraints=json.dumps([]),
                    timeline_and_milestones=json.dumps([]),
                    key_discussions=json.dumps([]),
                    summary=None,
                    key_decisions=json.dumps([]),
                    blockers=json.dumps([])
                )
                db_session.add(processed_meeting)
                logger.info(f"Created new processed meeting record for {meeting_id} with {len(topics_data)} topics")

        # Invalidate meetings cache after successful analysis
        invalidated = invalidate_cache('api_cache:meetings:*')
        logger.info(f"Invalidated {invalidated} meetings cache entries after analysis")

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


@meetings_bp.route("/api/meetings/<meeting_id>", methods=["DELETE"])
@admin_required
def delete_meeting(user, meeting_id):
    """Delete a meeting analysis (admin only).

    This endpoint permanently deletes a meeting analysis from the processed_meetings table.
    Only users with admin role can delete meetings.

    Args:
        meeting_id: The UUID of the meeting to delete

    Returns:
        200: Meeting deleted successfully
        403: User is not an admin
        404: Meeting not found
        500: Server error
    """
    try:
        from sqlalchemy import text

        logger.info(f"Admin user {user.email} (ID: {user.id}) is deleting meeting {meeting_id}")

        with session_scope() as db_session:
            # Check if meeting exists
            result = db_session.execute(
                text("SELECT id, title FROM processed_meetings WHERE id = :meeting_id"),
                {"meeting_id": meeting_id}
            )
            meeting = result.fetchone()

            if not meeting:
                logger.warning(f"Meeting {meeting_id} not found")
                return error_response("Meeting not found", status_code=404)

            meeting_title = meeting[1]

            # Delete the meeting
            db_session.execute(
                text("DELETE FROM processed_meetings WHERE id = :meeting_id"),
                {"meeting_id": meeting_id}
            )
            db_session.commit()

            logger.info(f"Successfully deleted meeting {meeting_id} ({meeting_title})")

            # Invalidate cache for this user
            invalidate_cache('meetings', user.id)

            return success_response(
                message=f"Meeting '{meeting_title}' deleted successfully",
                data={"meeting_id": meeting_id}
            )

    except Exception as e:
        logger.error(f"Error deleting meeting {meeting_id}: {e}")
        import traceback
        traceback.print_exc()
        return error_response(f"Failed to delete meeting: {str(e)}", status_code=500)