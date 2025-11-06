#!/usr/bin/env python3
"""
Analyze tracked hours from Pinecone vector database grouped by epic and month.

This script queries Pinecone for Tempo worklog data and analyzes it by epic and month.
Used to validate against direct Tempo API results.

Usage:
    python scripts/analyze_hours_pinecone.py --projects COOP --months 12
"""

import argparse
import sys
import os
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List
import logging

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
from pinecone import Pinecone

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PineconeHoursAnalyzer:
    """Analyze Tempo hours from Pinecone vector database."""

    def __init__(self):
        """Initialize Pinecone client."""
        api_key = os.getenv('PINECONE_API_KEY')
        index_name = os.getenv('PINECONE_INDEX_NAME', 'agent-pm-context')

        if not api_key:
            raise ValueError("PINECONE_API_KEY environment variable is required")

        self.pc = Pinecone(api_key=api_key)
        self.index = self.pc.Index(index_name)
        logger.info(f"Connected to Pinecone index: {index_name}")

    def query_tempo_worklogs(
        self,
        project_keys: List[str],
        start_date: str,
        end_date: str
    ) -> List[Dict]:
        """
        Query Pinecone for Tempo worklogs.

        Args:
            project_keys: List of project keys to filter (e.g., ["COOP", "BEVS"])
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format

        Returns:
            List of worklog metadata dictionaries
        """
        logger.info(f"Querying Pinecone for Tempo data: {start_date} to {end_date}")

        # Convert dates to Unix timestamps for Pinecone query
        start_timestamp = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp())
        end_timestamp = int(datetime.strptime(end_date, "%Y-%m-%d").timestamp()) + 86399  # End of day

        # Build filter
        filter_dict = {
            "source": "tempo",
            "timestamp_epoch": {"$gte": start_timestamp, "$lte": end_timestamp}
        }

        if project_keys:
            filter_dict["project_key"] = {"$in": project_keys}

        # Query Pinecone with dummy vector (we only want metadata)
        # Use high top_k to get as many results as possible
        try:
            results = self.index.query(
                vector=[0.0] * 1536,  # Dummy vector
                filter=filter_dict,
                top_k=10000,  # Max allowed
                include_metadata=True
            )

            matches = results.get('matches', [])
            logger.info(f"Retrieved {len(matches)} worklogs from Pinecone")

            # Extract metadata
            worklogs = [match.metadata for match in matches]
            return worklogs

        except Exception as e:
            logger.error(f"Error querying Pinecone: {e}")
            raise

    def analyze_worklogs(
        self,
        worklogs: List[Dict]
    ) -> Dict[str, Dict[str, Dict[str, float]]]:
        """
        Analyze worklogs grouped by project, epic, and month.

        Args:
            worklogs: List of worklog metadata from Pinecone

        Returns:
            Nested dict: {project_key: {month: {epic_key: hours}}}
        """
        # Structure: {project: {month: {epic: hours}}}
        results = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))

        # Track epic summaries
        epic_summaries = {}

        processed = 0
        skipped = 0

        for worklog in worklogs:
            try:
                # Get project key
                project_key = worklog.get('project_key')
                if not project_key:
                    skipped += 1
                    continue

                # Get epic key (stored directly in Pinecone metadata)
                epic_key = worklog.get('epic_key', 'No Epic')

                # Get epic summary if available
                epic_summary = worklog.get('epic_summary', '')
                if epic_key and epic_key != 'No Epic' and epic_summary:
                    epic_summaries[epic_key] = epic_summary

                # Get date
                date_str = worklog.get('date')
                if not date_str:
                    skipped += 1
                    continue

                worklog_date = datetime.strptime(date_str, "%Y-%m-%d")
                month_key = worklog_date.strftime("%Y-%m")

                # Get hours
                hours = worklog.get('hours_logged', 0)

                # Add to results
                results[project_key][month_key][epic_key] += hours
                processed += 1

            except Exception as e:
                logger.debug(f"Error processing worklog: {e}")
                skipped += 1
                continue

        logger.info(f"Processed {processed} worklogs, skipped {skipped}")

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
        print("HOURS ANALYSIS BY PROJECT, EPIC, AND MONTH (Pinecone Data)")
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
        description="Analyze Tempo hours from Pinecone grouped by epic and month",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze specific projects for last 6 months
  python scripts/analyze_hours_pinecone.py --projects COOP BEVS --months 6

  # Analyze with custom date range
  python scripts/analyze_hours_pinecone.py --projects COOP --start-date 2024-01-01 --end-date 2024-12-31

  # Export to CSV
  python scripts/analyze_hours_pinecone.py --projects COOP --months 12 --format csv > coop_pinecone.csv
        """
    )

    parser.add_argument(
        '--projects',
        nargs='+',
        help='Project keys to analyze (e.g., COOP BEVS). If not specified, analyze all'
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

    # Determine date range
    if args.start_date:
        start_date = args.start_date
    elif args.months:
        start_date = (datetime.now() - timedelta(days=args.months * 30)).strftime("%Y-%m-%d")
    else:
        parser.error("Must specify --months or --start-date")

    end_date = args.end_date or datetime.now().strftime("%Y-%m-%d")

    # Determine projects
    project_keys = args.projects or []

    # Run analysis
    try:
        analyzer = PineconeHoursAnalyzer()

        logger.info(f"Starting analysis for projects: {project_keys or 'ALL'}")
        logger.info(f"Date range: {start_date} to {end_date}")

        worklogs = analyzer.query_tempo_worklogs(
            project_keys=project_keys,
            start_date=start_date,
            end_date=end_date
        )

        results = analyzer.analyze_worklogs(worklogs)
        analyzer.print_report(results, format_type=args.format)

    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
