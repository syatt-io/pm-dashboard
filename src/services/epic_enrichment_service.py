"""Epic enrichment service for fetching real epic names from Jira.

This service enriches epic_hours records that have Jira ticket keys as their
epic_summary (e.g., CAR-57, COOP-104) with the actual epic names from Jira.
"""

import logging
import os
from typing import Dict, Set, Optional
from collections import defaultdict
import httpx

from src.models import EpicHours
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class EpicEnrichmentService:
    """Service for enriching epic summaries with real names from Jira."""

    def __init__(self, session: Session):
        """Initialize enrichment service.

        Args:
            session: SQLAlchemy database session
        """
        self.session = session
        self.jira_url = os.environ.get('JIRA_URL')
        self.jira_username = os.environ.get('JIRA_USERNAME')
        self.jira_api_token = os.environ.get('JIRA_API_TOKEN')

        if not all([self.jira_url, self.jira_username, self.jira_api_token]):
            logger.warning("Jira credentials not configured - enrichment will be skipped")

    def get_epics_needing_enrichment(self, project_key: Optional[str] = None) -> Dict[str, Set[str]]:
        """Get epic keys that need epic summary enrichment (where epic_summary == epic_key).

        Args:
            project_key: Optional project key to filter by

        Returns:
            Dict mapping project_key -> set of epic_keys that need enrichment
        """
        logger.info("Finding epics with epic_summary == epic_key...")

        query = self.session.query(
            EpicHours.project_key,
            EpicHours.epic_key,
            EpicHours.epic_summary
        ).distinct()

        if project_key:
            query = query.filter(EpicHours.project_key == project_key)

        results = query.all()

        # Group by project, filter where epic_summary == epic_key
        epics_by_project = defaultdict(set)

        for proj_key, epic_key, epic_summary in results:
            # Check if epic_summary is the same as epic_key (needs enrichment)
            if epic_summary and epic_summary == epic_key:
                epics_by_project[proj_key].add(epic_key)

        total_epics = sum(len(epics) for epics in epics_by_project.values())
        logger.info(f"Found {total_epics} epics across {len(epics_by_project)} projects needing enrichment")

        return dict(epics_by_project)

    def fetch_epic_summaries_from_jira(self, epics_by_project: Dict[str, Set[str]]) -> Dict[str, str]:
        """Fetch actual epic summaries from Jira.

        Args:
            epics_by_project: Dict of project_key -> set of epic_keys

        Returns:
            Dict mapping epic_key -> epic_summary
        """
        if not all([self.jira_url, self.jira_username, self.jira_api_token]):
            logger.error("Jira credentials not configured")
            return {}

        logger.info("Fetching epic summaries from Jira...")

        epic_summaries = {}
        total_epics = sum(len(epics) for epics in epics_by_project.values())
        processed = 0

        # Use httpx for API calls with basic auth
        auth = (self.jira_username, self.jira_api_token)

        with httpx.Client(auth=auth, timeout=30.0) as client:
            for project_key, epic_keys in sorted(epics_by_project.items()):
                logger.debug(f"Processing {project_key} ({len(epic_keys)} epics)...")

                for epic_key in sorted(epic_keys):
                    try:
                        # Fetch epic details from Jira REST API
                        url = f"{self.jira_url}/rest/api/3/issue/{epic_key}?fields=summary"
                        response = client.get(url)

                        if response.status_code == 200:
                            epic_data = response.json()
                            if 'fields' in epic_data and 'summary' in epic_data['fields']:
                                epic_summary = epic_data['fields']['summary']
                                epic_summaries[epic_key] = epic_summary
                                logger.debug(f"  {epic_key} → {epic_summary}")
                            else:
                                logger.warning(f"  {epic_key}: No summary found, keeping original")
                                epic_summaries[epic_key] = epic_key
                        elif response.status_code == 404:
                            logger.warning(f"  {epic_key}: Not found in Jira (404), keeping original")
                            epic_summaries[epic_key] = epic_key
                        else:
                            logger.error(f"  {epic_key}: HTTP {response.status_code}, keeping original")
                            epic_summaries[epic_key] = epic_key

                        processed += 1

                        if processed % 10 == 0:
                            logger.debug(f"  Progress: {processed}/{total_epics} epics")

                    except Exception as e:
                        logger.error(f"  Error fetching {epic_key}: {e}")
                        # Keep the original epic_key as fallback
                        epic_summaries[epic_key] = epic_key

        logger.info(f"Successfully fetched {len(epic_summaries)} epic summaries")
        return epic_summaries

    def update_epic_summaries(self, epic_summaries: Dict[str, str]) -> int:
        """Update epic_summary field in epic_hours table.

        Args:
            epic_summaries: Dict of epic_key -> epic_summary

        Returns:
            Number of records updated
        """
        logger.info(f"Updating {len(epic_summaries)} epic summaries in database...")

        updated = 0
        for epic_key, epic_summary in epic_summaries.items():
            # Skip if epic_summary is the same as epic_key (no enrichment)
            if epic_summary == epic_key:
                continue

            # Update all records for this epic_key
            result = (
                self.session.query(EpicHours)
                .filter_by(epic_key=epic_key)
                .update({"epic_summary": epic_summary})
            )

            if result > 0:
                updated += result
                logger.debug(f"  Updated {result} records for {epic_key}")

        self.session.commit()
        logger.info(f"Updated {updated} records successfully")
        return updated

    def enrich_project_epics(self, project_key: str) -> Dict[str, any]:
        """Enrich epic summaries for a specific project.

        Args:
            project_key: Project key to enrich

        Returns:
            Dict with enrichment statistics
        """
        # Step 1: Find epics needing enrichment
        epics_by_project = self.get_epics_needing_enrichment(project_key)

        if not epics_by_project:
            logger.info(f"No epics need enrichment for project {project_key}")
            return {
                'success': True,
                'project_key': project_key,
                'epics_found': 0,
                'records_updated': 0,
                'enriched_count': 0
            }

        # Step 2: Fetch epic summaries from Jira
        epic_summaries = self.fetch_epic_summaries_from_jira(epics_by_project)

        # Step 3: Update database
        records_updated = self.update_epic_summaries(epic_summaries)

        # Calculate enrichment stats
        enriched = {k: v for k, v in epic_summaries.items() if k != v}

        return {
            'success': True,
            'project_key': project_key,
            'epics_found': len(epic_summaries),
            'records_updated': records_updated,
            'enriched_count': len(enriched)
        }

    def enrich_all_epics(self) -> Dict[str, any]:
        """Enrich epic summaries for all projects.

        Returns:
            Dict with enrichment statistics
        """
        # Step 1: Find all epics needing enrichment
        epics_by_project = self.get_epics_needing_enrichment()

        if not epics_by_project:
            logger.info("No epics need enrichment")
            return {
                'success': True,
                'epics_found': 0,
                'records_updated': 0,
                'enriched_count': 0
            }

        # Step 2: Fetch epic summaries from Jira
        epic_summaries = self.fetch_epic_summaries_from_jira(epics_by_project)

        # Step 3: Update database
        records_updated = self.update_epic_summaries(epic_summaries)

        # Calculate enrichment stats
        enriched = {k: v for k, v in epic_summaries.items() if k != v}

        return {
            'success': True,
            'epics_found': len(epic_summaries),
            'records_updated': records_updated,
            'enriched_count': len(enriched)
        }
