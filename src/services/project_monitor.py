"""Project monitoring service for tracking Jira changes."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import uuid

from config.settings import settings
from src.integrations.jira_mcp import JiraMCPClient


logger = logging.getLogger(__name__)


class ProjectMonitor:
    """Service for monitoring Jira project changes."""

    def __init__(self):
        """Initialize the project monitor."""
        self.jira_client = JiraMCPClient(
            jira_url=settings.jira.url,
            username=settings.jira.username,
            api_token=settings.jira.api_token
        )

    async def poll_project_changes(self, project_keys: List[str], since_timestamp: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Poll for changes in specified projects."""
        if not since_timestamp:
            # Default to last 24 hours
            since_timestamp = datetime.now() - timedelta(hours=24)

        changes = []

        async with self.jira_client as client:
            for project_key in project_keys:
                try:
                    project_changes = await self._detect_project_changes(client, project_key, since_timestamp)
                    changes.extend(project_changes)
                except Exception as e:
                    logger.error(f"Error polling changes for project {project_key}: {e}")
                    continue

        # Group changes by ticket to show distinct tickets with combined context
        grouped_changes = self._group_changes_by_ticket(changes)
        return grouped_changes

    async def _detect_project_changes(self, client: JiraMCPClient, project_key: str, since: datetime) -> List[Dict[str, Any]]:
        """Detect changes in a specific project."""
        changes = []

        try:
            # Format timestamp for JQL
            since_jql = since.strftime("%Y-%m-%d %H:%M")

            # Query for recently created tickets
            created_jql = f'project = "{project_key}" AND created >= "{since_jql}" ORDER BY created DESC'
            created_tickets = await client.search_tickets(created_jql, max_results=100)

            for ticket in created_tickets:
                changes.append(self._format_change(
                    project_key=project_key,
                    change_type='created',
                    ticket=ticket,
                    change_timestamp=self._parse_jira_timestamp(ticket['fields']['created'])
                ))

            # Query for recently updated tickets
            updated_jql = f'project = "{project_key}" AND updated >= "{since_jql}" ORDER BY updated DESC'
            updated_tickets = await client.search_tickets(updated_jql, max_results=100)

            for ticket in updated_tickets:
                # Skip if this was already captured as a new ticket
                created_time = self._parse_jira_timestamp(ticket['fields']['created'])
                if created_time >= since:
                    continue

                # Get detailed change history
                detailed_changes = await self._get_ticket_change_history(client, ticket, since)
                changes.extend(detailed_changes)

        except Exception as e:
            logger.error(f"Error detecting changes for project {project_key}: {e}")

        return changes

    async def _get_ticket_change_history(self, client: JiraMCPClient, ticket: Dict[str, Any], since: datetime) -> List[Dict[str, Any]]:
        """Get detailed change history for a ticket."""
        changes = []
        ticket_key = ticket['key']
        project_key = ticket['fields']['project']['key']

        try:
            # Get ticket with change history
            changelog_ticket = await client.get_ticket_with_changelog(ticket_key)

            if not changelog_ticket or 'changelog' not in changelog_ticket:
                return changes

            for history in changelog_ticket['changelog']['histories']:
                change_time = self._parse_jira_timestamp(history['created'])

                # Only include changes after our since timestamp
                if change_time < since:
                    continue

                author = history.get('author', {}).get('displayName', 'Unknown')

                for item in history.get('items', []):
                    field = item.get('field', '')
                    from_value = item.get('fromString', '')
                    to_value = item.get('toString', '')

                    # Skip less meaningful changes
                    if self._should_skip_change(field, from_value, to_value):
                        continue

                    # Determine change type based on field
                    change_type = self._determine_change_type(field)

                    changes.append(self._format_change(
                        project_key=project_key,
                        change_type=change_type,
                        ticket=ticket,
                        change_timestamp=change_time,
                        old_value=from_value,
                        new_value=to_value,
                        change_author=author,
                        field_changed=field
                    ))

        except Exception as e:
            logger.error(f"Error getting change history for ticket {ticket_key}: {e}")

        return changes

    def _should_skip_change(self, field: str, from_value: str, to_value: str) -> bool:
        """Determine if a change should be skipped as less meaningful."""
        # Only allow these specific meaningful change types
        allowed_fields = {
            'status',            # Status changes (most important)
            'assignee',          # Assignee changes (very important)
            'comment',           # Comments (communication)
            'timespent',         # Time tracking (work progress)
            'worklog',           # Work logging (also time tracking)
            'timeoriginalestimate',  # Time estimates
        }

        # Skip anything not in our allowed list
        if field not in allowed_fields:
            return True

        # Skip changes where from and to values are the same (no actual change)
        if from_value == to_value:
            return True

        # Skip changes with empty values (often automated cleanup)
        if not from_value and not to_value:
            return True

        return False

    def _determine_change_type(self, field: str) -> str:
        """Determine change type based on the field that changed."""
        # Only map the specific fields we're tracking
        field_mappings = {
            'status': 'status_changed',
            'assignee': 'assignee_changed',
            'comment': 'comment_added',
            'timespent': 'time_logged',
            'worklog': 'time_logged',
            'timeoriginalestimate': 'estimate_changed',
        }

        return field_mappings.get(field, 'updated')

    def _group_changes_by_ticket(self, changes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Group multiple changes by ticket to show distinct tickets with combined context."""
        ticket_groups = {}

        for change in changes:
            ticket_key = change['ticket_key']

            if ticket_key not in ticket_groups:
                # Initialize with the first change for this ticket
                ticket_groups[ticket_key] = {
                    'id': change['id'],
                    'project_key': change['project_key'],
                    'ticket_key': change['ticket_key'],
                    'ticket_title': change['ticket_title'],
                    'assignee': change['assignee'],
                    'reporter': change['reporter'],
                    'priority': change['priority'],
                    'status': change['status'],
                    'change_timestamp': change['change_timestamp'],
                    'detected_at': change['detected_at'],
                    'change_types': [],
                    'change_summary': [],
                    'authors': set(),
                    'change_details': change['change_details']
                }

            # Collect all change types and details for this ticket
            ticket_groups[ticket_key]['change_types'].append(change['change_type'])
            author = change.get('change_details', {}).get('change_author')
            if author:
                ticket_groups[ticket_key]['authors'].add(author)
            else:
                ticket_groups[ticket_key]['authors'].add('Unknown')

            # Create human-readable change summary
            if change['change_type'] == 'status_changed':
                if change['old_value'] and change['new_value']:
                    ticket_groups[ticket_key]['change_summary'].append(f"Status: {change['old_value']} → {change['new_value']}")
                else:
                    ticket_groups[ticket_key]['change_summary'].append("Status changed")
            elif change['change_type'] == 'assignee_changed':
                old_assignee = change['old_value'] or 'Unassigned'
                new_assignee = change['new_value'] or 'Unassigned'
                ticket_groups[ticket_key]['change_summary'].append(f"Assigned: {old_assignee} → {new_assignee}")
            elif change['change_type'] == 'comment_added':
                ticket_groups[ticket_key]['change_summary'].append("Comment added")
            elif change['change_type'] == 'time_logged':
                if change['new_value']:
                    ticket_groups[ticket_key]['change_summary'].append(f"Time logged: {change['new_value']}")
                else:
                    ticket_groups[ticket_key]['change_summary'].append("Time logged")
            elif change['change_type'] == 'estimate_changed':
                if change['old_value'] and change['new_value']:
                    ticket_groups[ticket_key]['change_summary'].append(f"Estimate: {change['old_value']} → {change['new_value']}")
                else:
                    ticket_groups[ticket_key]['change_summary'].append("Estimate changed")

            # Keep the most recent timestamp
            if change['change_timestamp'] > ticket_groups[ticket_key]['change_timestamp']:
                ticket_groups[ticket_key]['change_timestamp'] = change['change_timestamp']

        # Convert back to list and add combined change info
        result = []
        for ticket_data in ticket_groups.values():
            # Convert authors set to list
            ticket_data['authors'] = list(ticket_data['authors'])

            # Create a combined change type for the main change_type field
            unique_types = list(set(ticket_data['change_types']))
            if len(unique_types) == 1:
                ticket_data['change_type'] = unique_types[0]
            else:
                ticket_data['change_type'] = 'multiple_changes'

            # Create old_value and new_value with summary
            # Filter out None values from authors
            valid_authors = [a for a in ticket_data['authors'] if a]
            if valid_authors:
                ticket_data['old_value'] = f"Multiple changes by {', '.join(valid_authors)}"
            else:
                ticket_data['old_value'] = "Multiple changes"
            ticket_data['new_value'] = '; '.join(ticket_data['change_summary']) if ticket_data['change_summary'] else "Changes detected"

            # Clean up temporary fields
            del ticket_data['change_types']
            del ticket_data['change_summary']
            del ticket_data['authors']

            result.append(ticket_data)

        return result

    def _format_change(self, project_key: str, change_type: str, ticket: Dict[str, Any],
                      change_timestamp: datetime, old_value: str = None, new_value: str = None,
                      change_author: str = None, field_changed: str = None) -> Dict[str, Any]:
        """Format a change into our standard format."""
        fields = ticket.get('fields', {})

        return {
            'id': str(uuid.uuid4()),
            'project_key': project_key,
            'change_type': change_type,
            'ticket_key': ticket['key'],
            'ticket_title': fields.get('summary', ''),
            'old_value': old_value,
            'new_value': new_value,
            'assignee': self._get_user_display_name(fields.get('assignee')),
            'reporter': self._get_user_display_name(fields.get('reporter')),
            'priority': fields.get('priority', {}).get('name', ''),
            'status': fields.get('status', {}).get('name', ''),
            'change_timestamp': change_timestamp,
            'detected_at': datetime.now(),
            'change_details': {
                'field_changed': field_changed,
                'change_author': change_author,
                'ticket_url': f"{settings.jira.url}/browse/{ticket['key']}",
                'project_name': fields.get('project', {}).get('name', ''),
                'issue_type': fields.get('issuetype', {}).get('name', ''),
                'labels': fields.get('labels', [])
            }
        }

    def _get_user_display_name(self, user_field: Optional[Dict[str, Any]]) -> str:
        """Extract display name from Jira user field."""
        if not user_field:
            return ''
        return user_field.get('displayName', user_field.get('name', ''))

    def _parse_jira_timestamp(self, timestamp_str: str) -> datetime:
        """Parse Jira timestamp string to datetime."""
        try:
            # Jira timestamps are in ISO format like "2023-12-01T10:30:00.000+0000"
            # Strip the timezone and microseconds for simple parsing
            clean_timestamp = timestamp_str.split('.')[0].replace('T', ' ')
            if '+' in clean_timestamp:
                clean_timestamp = clean_timestamp.split('+')[0]
            elif 'Z' in clean_timestamp:
                clean_timestamp = clean_timestamp.replace('Z', '')

            return datetime.strptime(clean_timestamp, "%Y-%m-%d %H:%M:%S")
        except Exception as e:
            logger.error(f"Error parsing Jira timestamp {timestamp_str}: {e}")
            return datetime.now()

    async def save_changes_to_db(self, changes: List[Dict[str, Any]]):
        """Save detected changes to the database."""
        if not changes:
            return

        try:
            from main import ProjectChange
            from sqlalchemy.orm import sessionmaker
            from sqlalchemy import create_engine

            engine = create_engine(settings.agent.database_url)
            Session = sessionmaker(bind=engine)
            db_session = Session()

            for change_data in changes:
                # Check if this change already exists (avoid duplicates)
                existing = db_session.query(ProjectChange).filter_by(
                    ticket_key=change_data['ticket_key'],
                    change_type=change_data['change_type'],
                    change_timestamp=change_data['change_timestamp']
                ).first()

                if not existing:
                    change = ProjectChange(
                        id=change_data['id'],
                        project_key=change_data['project_key'],
                        change_type=change_data['change_type'],
                        ticket_key=change_data['ticket_key'],
                        ticket_title=change_data['ticket_title'],
                        old_value=change_data['old_value'],
                        new_value=change_data['new_value'],
                        assignee=change_data['assignee'],
                        reporter=change_data['reporter'],
                        priority=change_data['priority'],
                        status=change_data['status'],
                        change_timestamp=change_data['change_timestamp'],
                        detected_at=change_data['detected_at'],
                        change_details=change_data['change_details']
                    )
                    db_session.add(change)

            db_session.commit()
            db_session.close()

            logger.info(f"Saved {len(changes)} project changes to database")

        except Exception as e:
            logger.error(f"Error saving changes to database: {e}")

    async def get_user_project_changes(self, email: str, since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Get project changes for a specific user's selected projects."""
        try:
            from main import UserPreference, ProjectChange
            from sqlalchemy.orm import sessionmaker
            from sqlalchemy import create_engine

            engine = create_engine(settings.agent.database_url)
            Session = sessionmaker(bind=engine)
            db_session = Session()

            # Get user preferences
            user_pref = db_session.query(UserPreference).filter_by(email=email).first()
            if not user_pref or not user_pref.selected_projects:
                db_session.close()
                return []

            # Build query for changes in user's selected projects
            query = db_session.query(ProjectChange).filter(
                ProjectChange.project_key.in_(user_pref.selected_projects)
            )

            if since:
                query = query.filter(ProjectChange.change_timestamp >= since)

            # Order by newest first
            changes = query.order_by(ProjectChange.change_timestamp.desc()).limit(100).all()

            # Convert to dictionaries
            result = []
            for change in changes:
                result.append({
                    'id': change.id,
                    'project_key': change.project_key,
                    'change_type': change.change_type,
                    'ticket_key': change.ticket_key,
                    'ticket_title': change.ticket_title,
                    'old_value': change.old_value,
                    'new_value': change.new_value,
                    'assignee': change.assignee,
                    'reporter': change.reporter,
                    'priority': change.priority,
                    'status': change.status,
                    'change_timestamp': change.change_timestamp,
                    'detected_at': change.detected_at,
                    'change_details': change.change_details or {}
                })

            db_session.close()

            # Group changes by ticket to show distinct tickets with combined context
            grouped_result = self._group_changes_by_ticket(result)
            return grouped_result

        except Exception as e:
            logger.error(f"Error getting user project changes: {e}")
            return []

    async def run_daily_poll(self):
        """Run daily polling for all user-selected projects."""
        try:
            from main import UserPreference
            from sqlalchemy.orm import sessionmaker
            from sqlalchemy import create_engine

            engine = create_engine(settings.agent.database_url)
            Session = sessionmaker(bind=engine)
            db_session = Session()

            # Get all unique project keys from user preferences
            users = db_session.query(UserPreference).all()
            all_projects = set()

            for user in users:
                if user.selected_projects:
                    all_projects.update(user.selected_projects)

            db_session.close()

            if not all_projects:
                logger.info("No projects selected by any users, skipping poll")
                return

            logger.info(f"Polling changes for {len(all_projects)} projects: {list(all_projects)}")

            # Poll for changes in the last 24 hours
            since = datetime.now() - timedelta(hours=24)
            changes = await self.poll_project_changes(list(all_projects), since)

            # Save changes to database
            await self.save_changes_to_db(changes)

            logger.info(f"Daily poll completed: found {len(changes)} changes")

        except Exception as e:
            logger.error(f"Error in daily poll: {e}")