#!/usr/bin/env python3
"""
Analyze tracked hours from Tempo grouped by epic and month.

This script fetches worklogs from Tempo API, resolves epic associations from Jira,
and provides detailed breakdowns by epic and month for specified projects.

Usage:
    python scripts/analyze_hours_by_epic.py --projects COOP SUBS --months 6
    python scripts/analyze_hours_by_epic.py --projects COOP --start-date 2024-01-01 --end-date 2024-12-31
    python scripts/analyze_hours_by_epic.py --all-projects --months 3
"""

import argparse
import sys
import os
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Tuple
import logging

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
from src.integrations.tempo import TempoAPIClient

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class HoursByEpicAnalyzer:
    """Analyze Tempo hours grouped by epic and month."""

    def __init__(self):
        """Initialize analyzer with Tempo API client."""
        self.tempo_client = TempoAPIClient()
        self.epic_cache: Dict[str, str] = {}  # issue_key -> epic_key
        self.issue_summary_cache: Dict[str, str] = {}  # issue_key -> summary

    def get_epic_for_issue(self, issue_key: str) -> Tuple[str, str]:
        """
        Get epic key and summary for a given issue.

        Args:
            issue_key: Jira issue key (e.g., "COOP-123")

        Returns:
            Tuple of (epic_key, epic_summary) or ("No Epic", "") if no epic
        """
        if issue_key in self.epic_cache:
            return self.epic_cache[issue_key], self.issue_summary_cache.get(issue_key, "")

        try:
            # Rate limit to avoid hitting Jira API limits
            self.tempo_client._rate_limit()

            url = f"{self.tempo_client.jira_url}/rest/api/3/issue/{issue_key}"
            params = {"fields": "parent,summary,issuetype"}

            import requests
            response = requests.get(
                url,
                headers=self.tempo_client.jira_headers,
                params=params,
                timeout=10
            )
            response.raise_for_status()

            issue_data = response.json()
            fields = issue_data.get("fields", {})
            issue_type = fields.get("issuetype", {}).get("name", "")

            # If this IS an epic, return itself
            if issue_type == "Epic":
                summary = fields.get("summary", "")
                self.epic_cache[issue_key] = issue_key
                self.issue_summary_cache[issue_key] = summary
                return issue_key, summary

            # Check for parent (epic) field
            parent = fields.get("parent")
            if parent:
                epic_key = parent.get("key")
                # Get parent details
                parent_url = f"{self.tempo_client.jira_url}/rest/api/3/issue/{epic_key}"
                parent_response = requests.get(
                    parent_url,
                    headers=self.tempo_client.jira_headers,
                    params={"fields": "summary"},
                    timeout=10
                )
                parent_response.raise_for_status()
                parent_data = parent_response.json()
                epic_summary = parent_data.get("fields", {}).get("summary", "")

                self.epic_cache[issue_key] = epic_key
                self.issue_summary_cache[issue_key] = epic_summary
                return epic_key, epic_summary

            # No epic found
            self.epic_cache[issue_key] = "No Epic"
            self.issue_summary_cache[issue_key] = ""
            return "No Epic", ""

        except Exception as e:
            logger.debug(f"Error getting epic for {issue_key}: {e}")
            self.epic_cache[issue_key] = "Unknown"
            self.issue_summary_cache[issue_key] = ""
            return "Unknown", ""

    def analyze_worklogs(
        self,
        project_keys: List[str],
        start_date: str,
        end_date: str
    ) -> Dict[str, Dict[str, Dict[str, float]]]:
        """
        Analyze worklogs grouped by project, epic, and month.

        Args:
            project_keys: List of project keys to analyze (e.g., ["COOP", "SUBS"])
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format

        Returns:
            Nested dict: {project_key: {month: {epic_key: hours}}}
        """
        logger.info(f"Fetching worklogs from {start_date} to {end_date}")

        # Fetch all worklogs for date range
        worklogs = self.tempo_client.get_worklogs(start_date, end_date)
        logger.info(f"Retrieved {len(worklogs)} worklogs")

        # Structure: {project: {month: {epic: hours}}}
        results = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))

        # Track epic summaries
        epic_summaries = {}

        processed = 0
        skipped = 0

        for worklog in worklogs:
            try:
                # Get issue key
                issue_id = worklog.get("issue", {}).get("id")
                if not issue_id:
                    skipped += 1
                    continue

                # Resolve issue key
                issue_key = self.tempo_client.get_issue_key_from_jira(str(issue_id))
                if not issue_key:
                    skipped += 1
                    continue

                # Extract project key
                project_key = issue_key.split("-")[0]

                # Filter by requested projects
                if project_keys and project_key not in project_keys:
                    continue

                # Get epic association
                epic_key, epic_summary = self.get_epic_for_issue(issue_key)
                if epic_key not in epic_summaries and epic_summary:
                    epic_summaries[epic_key] = epic_summary

                # Get date and convert to month
                worklog_date_str = worklog.get("startDate", "")
                if not worklog_date_str:
                    skipped += 1
                    continue

                worklog_date = datetime.strptime(worklog_date_str, "%Y-%m-%d")
                month_key = worklog_date.strftime("%Y-%m")  # e.g., "2024-10"

                # Convert seconds to hours
                seconds = worklog.get("timeSpentSeconds", 0)
                hours = seconds / 3600

                # Add to results
                results[project_key][month_key][epic_key] += hours
                processed += 1

            except Exception as e:
                logger.debug(f"Error processing worklog: {e}")
                skipped += 1
                continue

        logger.info(f"Processed {processed} worklogs, skipped {skipped}")
        logger.info(f"Made {len(self.epic_cache)} Jira API calls for epic lookups")

        # Store epic summaries for reporting
        self.epic_summaries = epic_summaries

        return dict(results)

    def print_report(
        self,
        results: Dict[str, Dict[str, Dict[str, float]]],
        format_type: str = "table"
    ):
        """
        Print analysis results in various formats.

        Args:
            results: Analysis results from analyze_worklogs
            format_type: Output format - "table", "csv", or "json"
        """
        if format_type == "json":
            import json
            print(json.dumps(results, indent=2))
            return

        if format_type == "csv":
            print("Project,Month,Epic,Epic_Summary,Hours")
            for project, months in sorted(results.items()):
                for month, epics in sorted(months.items()):
                    for epic, hours in sorted(epics.items()):
                        epic_summary = self.epic_summaries.get(epic, "")
                        print(f"{project},{month},{epic},\"{epic_summary}\",{hours:.2f}")
            return

        # Table format (default)
        print("\n" + "=" * 100)
        print("HOURS ANALYSIS BY PROJECT, EPIC, AND MONTH")
        print("=" * 100)

        for project in sorted(results.keys()):
            print(f"\n{'=' * 100}")
            print(f"📦 PROJECT: {project}")
            print(f"{'=' * 100}")

            months = results[project]

            # Calculate totals
            project_total = sum(
                sum(epics.values()) for epics in months.values()
            )

            print(f"\n   Total Hours: {project_total:.2f}h")

            # Print by month
            for month in sorted(months.keys()):
                epics = months[month]
                month_total = sum(epics.values())

                print(f"\n   {'─' * 90}")
                print(f"   📅 {month} - Total: {month_total:.2f}h")
                print(f"   {'─' * 90}")

                # Sort epics by hours (descending)
                sorted_epics = sorted(epics.items(), key=lambda x: x[1], reverse=True)

                for epic_key, hours in sorted_epics:
                    epic_summary = self.epic_summaries.get(epic_key, "")
                    percentage = (hours / month_total * 100) if month_total > 0 else 0

                    if epic_summary:
                        print(f"      🎯 {epic_key}: {hours:6.2f}h ({percentage:5.1f}%) - {epic_summary}")
                    else:
                        print(f"      🎯 {epic_key}: {hours:6.2f}h ({percentage:5.1f}%)")

        print("\n" + "=" * 100)
        print("SUMMARY")
        print("=" * 100)

        # Print grand totals by project
        print("\n| Project | Total Hours | Months | Epics |")
        print("|---------|-------------|--------|-------|")

        for project in sorted(results.keys()):
            months = results[project]
            total_hours = sum(sum(epics.values()) for epics in months.values())
            num_months = len(months)
            all_epics = set()
            for epics in months.values():
                all_epics.update(epics.keys())
            num_epics = len(all_epics)

            print(f"| {project:7} | {total_hours:11.2f} | {num_months:6} | {num_epics:5} |")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze Tempo hours grouped by epic and month",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze specific projects for last 6 months
  python scripts/analyze_hours_by_epic.py --projects COOP SUBS --months 6

  # Analyze with custom date range
  python scripts/analyze_hours_by_epic.py --projects COOP --start-date 2024-01-01 --end-date 2024-12-31

  # Analyze all projects for last 3 months
  python scripts/analyze_hours_by_epic.py --all-projects --months 3

  # Export to CSV
  python scripts/analyze_hours_by_epic.py --projects COOP --months 6 --format csv > coop_analysis.csv
        """
    )

    parser.add_argument(
        '--projects',
        nargs='+',
        help='Project keys to analyze (e.g., COOP SUBS). If not specified, use --all-projects'
    )
    parser.add_argument(
        '--all-projects',
        action='store_true',
        help='Analyze all projects (ignores --projects)'
    )
    parser.add_argument(
        '--months',
        type=int,
        help='Number of months back to analyze (from today)'
    )
    parser.add_argument(
        '--start-date',
        help='Start date in YYYY-MM-DD format (overrides --months)'
    )
    parser.add_argument(
        '--end-date',
        help='End date in YYYY-MM-DD format (defaults to today)'
    )
    parser.add_argument(
        '--format',
        choices=['table', 'csv', 'json'],
        default='table',
        help='Output format (default: table)'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate arguments
    if not args.all_projects and not args.projects:
        parser.error("Must specify --projects or --all-projects")

    # Determine date range
    if args.start_date:
        start_date = args.start_date
    elif args.months:
        start_date = (datetime.now() - timedelta(days=args.months * 30)).strftime("%Y-%m-%d")
    else:
        parser.error("Must specify --months or --start-date")

    end_date = args.end_date or datetime.now().strftime("%Y-%m-%d")

    # Determine projects
    project_keys = [] if args.all_projects else args.projects

    # Run analysis
    try:
        analyzer = HoursByEpicAnalyzer()

        logger.info(f"Starting analysis for projects: {project_keys or 'ALL'}")
        logger.info(f"Date range: {start_date} to {end_date}")

        results = analyzer.analyze_worklogs(
            project_keys=project_keys,
            start_date=start_date,
            end_date=end_date
        )

        analyzer.print_report(results, format_type=args.format)

    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
