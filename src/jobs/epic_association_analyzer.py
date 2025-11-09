"""
Epic Association Analyzer Job

Analyzes unassigned Jira tickets and suggests (or auto-applies) epic associations
using AI-powered semantic matching.

Runs as part of Monthly Epic Reconciliation process.
"""

import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import asyncio

from src.services.epic_matcher import EpicMatcher
from src.integrations.jira_mcp import JiraMCPClient
from src.models import SystemSettings
from src.utils.database import get_session

logger = logging.getLogger(__name__)


class EpicAssociationAnalyzer:
    """Analyze and associate unassigned tickets to epics."""

    def __init__(self):
        """Initialize the analyzer."""
        self.database_url = os.getenv("DATABASE_URL")
        self.engine = create_engine(self.database_url)
        self.Session = sessionmaker(bind=self.engine)

        # Initialize Jira client with direct API credentials (fallback to MCP if not available)
        self.jira_client = JiraMCPClient(
            jira_url=os.getenv("JIRA_URL"),
            username=os.getenv("JIRA_USERNAME"),
            api_token=os.getenv("JIRA_API_TOKEN")
        )
        self.epic_matcher = EpicMatcher()

    def get_active_project_based_projects(self) -> List[str]:
        """
        Get list of active project-based projects from database.

        Returns:
            List of project keys (e.g., ["SUBS", "SATG"])
        """
        session = self.Session()
        try:
            # Query projects table
            result = session.execute(text("""
                SELECT key
                FROM projects
                WHERE is_active = true
                AND project_work_type = 'project-based'
                ORDER BY key
            """))

            project_keys = [row[0] for row in result.fetchall()]
            logger.info(f"Found {len(project_keys)} active project-based projects: {project_keys}")
            return project_keys

        except Exception as e:
            logger.error(f"Error fetching active projects: {e}", exc_info=True)
            return []
        finally:
            session.close()

    async def get_unassigned_tickets(self, project_key: str) -> List[Dict[str, Any]]:
        """
        Fetch tickets without epic link for a project.
        Only includes tickets with time logged in the last 60 days (actively worked on).

        Args:
            project_key: Project key (e.g., "SUBS")

        Returns:
            List of ticket dicts with 'key', 'summary', 'description'
        """
        try:
            # JQL to find unassigned tickets with recent work
            # worklogDate >= -60d filters to tickets with time logged in last 60 days
            # issuetype != Epic excludes Epic-type issues (which don't need epic links)
            jql = f'project = {project_key} AND "Epic Link" IS EMPTY AND issuetype != Epic AND status != Done AND worklogDate >= -60d ORDER BY created DESC'

            logger.info(f"Fetching unassigned tickets for {project_key}")
            issues = await self.jira_client.search_tickets(jql=jql, max_results=1000)

            # Extract relevant fields
            tickets = []
            for issue in issues:
                fields = issue.get('fields', {})
                tickets.append({
                    'key': issue['key'],
                    'summary': fields.get('summary', ''),
                    'description': fields.get('description', '') or ''
                })

            logger.info(f"Found {len(tickets)} unassigned tickets in {project_key}")
            return tickets

        except Exception as e:
            logger.error(f"Error fetching unassigned tickets for {project_key}: {e}", exc_info=True)
            return []

    async def get_project_epics(self, project_key: str) -> List[Dict[str, str]]:
        """
        Fetch all epics for a project.

        Args:
            project_key: Project key (e.g., "SUBS")

        Returns:
            List of epic dicts with 'key' and 'summary'
        """
        try:
            # JQL to find epics
            jql = f'project = {project_key} AND issuetype = Epic ORDER BY created DESC'

            logger.info(f"Fetching epics for {project_key}")
            issues = await self.jira_client.search_tickets(jql=jql, max_results=1000)

            # Extract epic data
            epics = []
            for issue in issues:
                fields = issue.get('fields', {})
                epics.append({
                    'key': issue['key'],
                    'summary': fields.get('summary', '')
                })

            logger.info(f"Found {len(epics)} epics in {project_key}")
            return epics

        except Exception as e:
            logger.error(f"Error fetching epics for {project_key}: {e}", exc_info=True)
            return []

    async def update_ticket_epic_link(self, ticket_key: str, epic_key: str) -> bool:
        """
        Update a ticket's epic link in Jira.

        Args:
            ticket_key: Ticket key (e.g., "SUBS-123")
            epic_key: Epic key (e.g., "SUBS-10")

        Returns:
            True if successful, False otherwise
        """
        try:
            # Update via Jira API
            # customfield_10014 is the Epic Link field in Jira Cloud
            updates = {
                "fields": {
                    "customfield_10014": epic_key
                }
            }

            await self.jira_client.update_ticket(ticket_key, updates)
            logger.info(f"✅ Updated {ticket_key} -> Epic: {epic_key}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to update {ticket_key} with epic {epic_key}: {e}")
            return False

    async def analyze_project(
        self,
        project_key: str,
        auto_update: bool = False
    ) -> Dict[str, Any]:
        """
        Analyze unassigned tickets in a project and suggest/apply epic associations.

        Args:
            project_key: Project key to analyze
            auto_update: If True, update Jira. If False, just return suggestions.

        Returns:
            Analysis results dict
        """
        logger.info(f"{'='*60}")
        logger.info(f"Analyzing project: {project_key}")
        logger.info(f"Mode: {'AUTO-UPDATE' if auto_update else 'SUMMARY ONLY'}")
        logger.info(f"{'='*60}")

        # 1. Fetch unassigned tickets
        tickets = await self.get_unassigned_tickets(project_key)
        if not tickets:
            logger.info(f"No unassigned tickets found in {project_key}")
            return {
                'project_key': project_key,
                'total_tickets': 0,
                'matches': [],
                'updates_applied': 0,
                'update_failures': 0
            }

        # 2. Fetch project epics
        epics = await self.get_project_epics(project_key)
        if not epics:
            logger.warning(f"No epics found in {project_key}, skipping analysis")
            return {
                'project_key': project_key,
                'total_tickets': len(tickets),
                'matches': [],
                'updates_applied': 0,
                'update_failures': 0,
                'error': 'No epics available'
            }

        # 3. Use AI to match tickets to epics
        logger.info(f"Running AI analysis on {len(tickets)} tickets...")
        matches = self.epic_matcher.batch_match_tickets(
            tickets=tickets,
            available_epics=epics,
            confidence_threshold=0.5
        )

        # 4. Optionally update Jira
        updates_applied = 0
        update_failures = 0

        if auto_update and matches:
            logger.info(f"Applying {len(matches)} epic associations to Jira...")
            for match in matches:
                success = await self.update_ticket_epic_link(
                    ticket_key=match['ticket_key'],
                    epic_key=match['suggested_epic_key']
                )
                if success:
                    updates_applied += 1
                else:
                    update_failures += 1

        # 5. Return results
        result = {
            'project_key': project_key,
            'total_tickets': len(tickets),
            'matches': matches,
            'updates_applied': updates_applied,
            'update_failures': update_failures
        }

        logger.info(f"\nProject {project_key} Analysis Complete:")
        logger.info(f"  - Total unassigned tickets: {len(tickets)}")
        logger.info(f"  - AI matches found: {len(matches)}")
        if auto_update:
            logger.info(f"  - Updates applied: {updates_applied}")
            logger.info(f"  - Update failures: {update_failures}")
        logger.info("")

        return result

    async def run(self) -> Dict[str, Any]:
        """
        Main execution: Analyze all active project-based projects.

        Returns:
            Summary statistics and match results
        """
        logger.info("="*80)
        logger.info("EPIC ASSOCIATION ANALYZER")
        logger.info("="*80)
        logger.info(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("")

        # 1. Check if auto-update is enabled
        session = get_session()
        try:
            settings = session.query(SystemSettings).first()
            auto_update = settings.epic_auto_update_enabled if settings else False
        except Exception as e:
            logger.error(f"Error loading settings: {e}")
            auto_update = False
        finally:
            session.close()

        logger.info(f"Auto-update mode: {'ENABLED ✅' if auto_update else 'DISABLED (Summary only)'}")
        logger.info("")

        # 2. Get active project-based projects
        project_keys = self.get_active_project_based_projects()
        if not project_keys:
            logger.warning("No active project-based projects found")
            return {
                'total_projects': 0,
                'projects': []
            }

        # 3. Analyze each project
        project_results = []
        for project_key in project_keys:
            result = await self.analyze_project(project_key, auto_update=auto_update)
            project_results.append(result)

        # 4. Calculate summary statistics
        total_tickets = sum(r['total_tickets'] for r in project_results)
        total_matches = sum(len(r['matches']) for r in project_results)
        total_updates = sum(r['updates_applied'] for r in project_results)
        total_failures = sum(r['update_failures'] for r in project_results)

        # Categorize by confidence
        all_matches = []
        for r in project_results:
            all_matches.extend(r['matches'])

        categorized = self.epic_matcher.categorize_by_confidence(all_matches)

        summary = {
            'total_projects': len(project_keys),
            'total_tickets_analyzed': total_tickets,
            'total_matches_found': total_matches,
            'high_confidence_matches': len(categorized['high']),
            'medium_confidence_matches': len(categorized['medium']),
            'low_confidence_matches': len(categorized['low']),
            'updates_applied': total_updates,
            'update_failures': total_failures,
            'auto_update_enabled': auto_update,
            'projects': project_results
        }

        # 4.5. Save detailed match results to CSV
        self._save_detailed_results(all_matches, project_results)

        # 5. Log summary
        logger.info("="*80)
        logger.info("ANALYSIS SUMMARY")
        logger.info("="*80)
        logger.info(f"Projects analyzed: {summary['total_projects']}")
        logger.info(f"Total tickets analyzed: {summary['total_tickets_analyzed']}")
        logger.info(f"Total matches found: {summary['total_matches_found']}")
        logger.info(f"  - High confidence (0.8+): {summary['high_confidence_matches']}")
        logger.info(f"  - Medium confidence (0.5-0.79): {summary['medium_confidence_matches']}")
        logger.info(f"  - Low confidence (<0.5): {summary['low_confidence_matches']}")

        if auto_update:
            logger.info(f"\nJira Updates:")
            logger.info(f"  - Successfully applied: {summary['updates_applied']}")
            logger.info(f"  - Failed: {summary['update_failures']}")

        logger.info("="*80)
        logger.info(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("="*80)

        # Send Slack notification
        self.send_slack_notification(summary)

        return summary

    def _save_detailed_results(self, all_matches: List[Dict[str, Any]], project_results: List[Dict[str, Any]]) -> None:
        """Save detailed match results to CSV files for review."""
        try:
            import csv
            from pathlib import Path

            # Save all matches to a detailed CSV
            detailed_file = Path("/Users/msamimi/syatt/projects/agent-pm/epic_matches_detailed.csv")

            with open(detailed_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'Ticket Key',
                    'Ticket Summary',
                    'Suggested Epic',
                    'Epic Summary',
                    'Confidence',
                    'Confidence Level',
                    'Reason'
                ])

                for match in sorted(all_matches, key=lambda x: (-x['confidence'], x['ticket_key'])):
                    level = 'HIGH' if match['confidence'] >= 0.8 else ('MEDIUM' if match['confidence'] >= 0.5 else 'LOW')
                    writer.writerow([
                        match['ticket_key'],
                        match.get('ticket_summary', 'N/A'),
                        match['suggested_epic_key'],
                        match.get('epic_summary', 'N/A'),
                        f"{match['confidence']:.2f}",
                        level,
                        match.get('reason', '')
                    ])

            logger.info(f"Saved detailed results to {detailed_file}")

            # Save project summary
            summary_file = Path("/Users/msamimi/syatt/projects/agent-pm/epic_matches_by_project.csv")

            with open(summary_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Project', 'Total Tickets', 'Matches Found', 'High Conf', 'Medium Conf', 'Low Conf'])

                for project in project_results:
                    matches = project.get('matches', [])
                    high = sum(1 for m in matches if m['confidence'] >= 0.8)
                    medium = sum(1 for m in matches if 0.5 <= m['confidence'] < 0.8)
                    low = sum(1 for m in matches if m['confidence'] < 0.5)

                    writer.writerow([
                        project['project_key'],
                        project['total_tickets'],
                        len(matches),
                        high,
                        medium,
                        low
                    ])

            logger.info(f"Saved project summary to {summary_file}")

        except Exception as e:
            logger.error(f"Failed to save detailed results: {e}", exc_info=True)

    def send_slack_notification(self, summary: Dict[str, Any]) -> None:
        """Send Slack notification with epic association results."""
        try:
            from slack_sdk import WebClient

            slack_token = os.getenv("SLACK_BOT_TOKEN")
            slack_channel = os.getenv("SLACK_CHANNEL")

            if not slack_token or not slack_channel:
                logger.info("Slack not configured, skipping notification")
                return

            client = WebClient(token=slack_token)

            # Build message
            auto_update = summary.get('auto_update_enabled', False)
            mode_emoji = "🔄" if auto_update else "📋"
            mode_text = "Auto-Update Mode" if auto_update else "Summary Mode"

            emoji = "✅" if summary['total_matches_found'] > 0 else "ℹ️"
            title = f"Epic Association Analysis Complete ({mode_text})"

            # Build stats fields
            fields = [
                {
                    "type": "mrkdwn",
                    "text": f"*Projects Analyzed:* {summary['total_projects']}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Tickets Analyzed:* {summary['total_tickets_analyzed']}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Matches Found:* {summary['total_matches_found']}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*High Confidence:* {summary['high_confidence_matches']}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Medium Confidence:* {summary['medium_confidence_matches']}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Low Confidence:* {summary['low_confidence_matches']}"
                }
            ]

            # Add update stats if auto-update is enabled
            if auto_update:
                fields.extend([
                    {
                        "type": "mrkdwn",
                        "text": f"*✅ Updates Applied:* {summary['updates_applied']}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*❌ Update Failures:* {summary['update_failures']}"
                    }
                ])

            message_blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"{emoji} {title}"
                    }
                },
                {
                    "type": "section",
                    "fields": fields
                }
            ]

            # Add mode explanation
            mode_explanation = (
                "*Auto-Update Mode:* AI automatically updates Jira tickets with suggested epics."
                if auto_update
                else "*Summary Mode:* AI provides suggestions without making changes to Jira."
            )

            message_blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": mode_explanation
                    }
                ]
            })

            # Add project breakdown
            if summary.get('projects'):
                project_details = []
                for project in summary['projects']:
                    proj_key = project['project_key']
                    matches = len(project.get('matches', []))
                    if matches > 0:
                        updates_text = f" ({project['updates_applied']} applied)" if auto_update else ""
                        project_details.append(f"• *{proj_key}:* {matches} matches{updates_text}")

                if project_details:
                    message_blocks.append({
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*Project Breakdown:*\n" + "\n".join(project_details[:10])  # Limit to 10
                        }
                    })

            # Send to Slack
            client.chat_postMessage(
                channel=slack_channel,
                blocks=message_blocks,
                text=title  # Fallback text
            )

            logger.info(f"Sent Slack notification to {slack_channel}")

        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}", exc_info=True)


async def run_epic_association_analysis() -> Dict[str, Any]:
    """
    Entry point for running epic association analysis.

    Returns:
        Analysis results dict
    """
    analyzer = EpicAssociationAnalyzer()
    return await analyzer.run()


if __name__ == "__main__":
    # Run standalone for testing
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    results = asyncio.run(run_epic_association_analysis())

    print("\n" + "="*80)
    print("RESULTS")
    print("="*80)
    print(f"Total projects: {results.get('total_projects', 0)}")
    print(f"Total tickets: {results.get('total_tickets_analyzed', 0)}")
    print(f"Matches found: {results.get('total_matches_found', 0)}")

    if results.get('auto_update_enabled'):
        print(f"Updates applied: {results.get('updates_applied', 0)}")
        print(f"Failures: {results.get('update_failures', 0)}")
    else:
        print("(Summary mode - no updates applied)")
