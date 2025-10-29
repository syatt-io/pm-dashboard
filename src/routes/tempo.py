"""Tempo time tracking and project activity routes."""
from flask import Blueprint, jsonify, request
import asyncio
import logging
from datetime import datetime
from sqlalchemy import text

from src.utils.database import get_engine
from config.settings import settings

logger = logging.getLogger(__name__)

tempo_bp = Blueprint('tempo', __name__, url_prefix='/api')


@tempo_bp.route('/sync-hours', methods=['POST'])
def sync_hours():
    """
    Manual sync of CURRENT MONTH hours only from Tempo API.
    This is optimized for quick manual updates via the UI button.
    For full YTD sync, use the nightly job at 4am EST.
    """
    try:
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

        # Update database - upsert into project_monthly_forecast table
        # The nightly job handles cumulative_hours updates
        from datetime import date
        current_month = date.today().replace(day=1)

        with engine.connect() as conn:
            for project in active_projects:
                try:
                    project_key = project['key']
                    current_hours = current_month_hours.get(project_key, 0)

                    # Upsert into project_monthly_forecast table (same as nightly job)
                    conn.execute(text("""
                        INSERT INTO project_monthly_forecast
                            (project_key, month_year, actual_monthly_hours)
                        VALUES (:project_key, :month_year, :actual_hours)
                        ON CONFLICT (project_key, month_year)
                        DO UPDATE SET
                            actual_monthly_hours = :actual_hours,
                            updated_at = NOW()
                    """), {
                        "project_key": project_key,
                        "month_year": current_month,
                        "actual_hours": current_hours
                    })

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


@tempo_bp.route('/project-digest/<project_key>', methods=['POST'])
def generate_project_digest(project_key):
    """Generate a comprehensive project digest for client meetings.

    Supports caching with 6-hour TTL. Use force_refresh=true to bypass cache.
    """
    try:
        data = request.json or {}
        days_back = int(data.get('days', 7))
        project_name = data.get('project_name', project_key)
        force_refresh = data.get('force_refresh', False)

        # Check cache first unless force refresh
        if not force_refresh:
            from src.models import ProjectDigestCache
            from src.utils.database import get_session

            session = get_session()
            try:
                # Find most recent cache entry for this project/days combo
                cache_entry = session.query(ProjectDigestCache).filter(
                    ProjectDigestCache.project_key == project_key,
                    ProjectDigestCache.days == days_back
                ).order_by(ProjectDigestCache.created_at.desc()).first()

                if cache_entry and not cache_entry.is_expired(ttl_hours=6):
                    logger.info(f"Returning cached digest for {project_key} ({days_back} days), created at {cache_entry.created_at}")
                    import json
                    cached_data = json.loads(cache_entry.digest_data)
                    cached_data['from_cache'] = True
                    cached_data['cached_at'] = cache_entry.created_at.isoformat()
                    return jsonify(cached_data)
                else:
                    if cache_entry:
                        logger.info(f"Cache expired for {project_key}, regenerating digest")
            finally:
                session.close()

        logger.info(f"Generating fresh project digest for {project_key} ({days_back} days)")

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
                'formatted_agenda': markdown_agenda,
                'from_cache': False
            }

        # Run the async function
        result = asyncio.run(generate_digest())

        # Cache the result
        from src.models import ProjectDigestCache
        from src.utils.database import get_session
        import json

        session = get_session()
        try:
            cache_entry = ProjectDigestCache(
                project_key=project_key,
                days=days_back,
                digest_data=json.dumps(result)
            )
            session.add(cache_entry)
            session.commit()
            logger.info(f"Cached digest for {project_key} ({days_back} days)")
        except Exception as cache_error:
            logger.error(f"Failed to cache digest: {cache_error}")
            session.rollback()
        finally:
            session.close()

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error generating project digest: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
