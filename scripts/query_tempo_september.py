#!/usr/bin/env python3
"""Query Pinecone for Tempo worklogs in September 2025, grouped by person and project."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.vector_search import VectorSearchService
from datetime import datetime
from collections import defaultdict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def query_september_tempo_hours():
    """Query Pinecone for September Tempo worklogs and aggregate by person/project."""

    logger.info("🔍 Querying Pinecone for September 2025 Tempo worklogs...\n")

    try:
        vector_service = VectorSearchService()

        if not vector_service.is_available():
            logger.error("❌ Pinecone not available")
            return

        # Calculate September 2025 date range in Unix timestamps
        sept_start = datetime(2025, 9, 1, 0, 0, 0)
        sept_end = datetime(2025, 9, 30, 23, 59, 59)

        start_epoch = int(sept_start.timestamp())
        end_epoch = int(sept_end.timestamp())

        logger.info(f"📅 Date range: {sept_start.strftime('%Y-%m-%d')} to {sept_end.strftime('%Y-%m-%d')}")
        logger.info(f"   Epoch range: {start_epoch} to {end_epoch}\n")

        # Get a dummy query embedding (we just need metadata, not semantic search)
        query_embedding = vector_service.get_embedding("tempo worklogs")

        if not query_embedding:
            logger.error("❌ Failed to get query embedding")
            return

        # Build filter for Tempo worklogs in September
        filter_query = {
            "$and": [
                {"source": "tempo"},
                {"timestamp_epoch": {"$gte": start_epoch}},
                {"timestamp_epoch": {"$lte": end_epoch}}
            ]
        }

        logger.info(f"🔍 Querying Pinecone with filter: {filter_query}\n")

        # Query Pinecone with large top_k to get all September worklogs
        results = vector_service.pinecone_index.query(
            vector=query_embedding,
            top_k=10000,  # Large number to get all September worklogs
            filter=filter_query,
            include_metadata=True
        )

        matches = results.get('matches', [])
        logger.info(f"✅ Found {len(matches)} Tempo worklogs in September 2025\n")

        if not matches:
            logger.warning("⚠️  No Tempo worklogs found in Pinecone for September 2025")
            logger.warning("    Make sure the Tempo backfill has been run: python src/tasks/backfill_tempo.py")
            return

        # Aggregate hours by person and project
        person_project_hours = defaultdict(lambda: defaultdict(float))
        person_totals = defaultdict(float)
        project_totals = defaultdict(float)

        worklogs_processed = 0
        worklogs_missing_data = 0

        for match in matches:
            metadata = match.get('metadata', {})

            # Extract required fields
            author_name = metadata.get('author_name')
            issue_key = metadata.get('issue_key')
            # Note: Ingestion stores as 'hours_logged', not 'time_spent_seconds'
            hours_logged = metadata.get('hours_logged')

            # Skip worklogs with missing data
            if not author_name or not issue_key or hours_logged is None:
                worklogs_missing_data += 1
                continue

            # Extract project key from issue key (e.g., "SUBS-123" -> "SUBS")
            project_key = issue_key.split('-')[0] if '-' in issue_key else issue_key

            # hours_logged is already in hours
            hours = float(hours_logged)

            # Aggregate
            person_project_hours[author_name][project_key] += hours
            person_totals[author_name] += hours
            project_totals[project_key] += hours
            worklogs_processed += 1

        logger.info(f"📊 Processed {worklogs_processed} worklogs")
        if worklogs_missing_data > 0:
            logger.warning(f"⚠️  Skipped {worklogs_missing_data} worklogs with missing data\n")

        # Display results
        print("=" * 100)
        print("📊 SEPTEMBER 2025 TEMPO HOURS BY PERSON AND PROJECT")
        print("=" * 100)
        print()

        # Sort people by total hours descending
        sorted_people = sorted(person_totals.items(), key=lambda x: x[1], reverse=True)

        for person, total_hours in sorted_people:
            print(f"👤 {person}: {total_hours:.2f} hours total")

            # Sort projects by hours descending for this person
            projects = person_project_hours[person]
            sorted_projects = sorted(projects.items(), key=lambda x: x[1], reverse=True)

            for project, hours in sorted_projects:
                print(f"   └─ {project}: {hours:.2f} hours")
            print()

        print("=" * 100)
        print("📊 TOTALS BY PROJECT")
        print("=" * 100)
        print()

        # Sort projects by total hours descending
        sorted_projects = sorted(project_totals.items(), key=lambda x: x[1], reverse=True)

        for project, hours in sorted_projects:
            print(f"📁 {project}: {hours:.2f} hours")

        print()
        print("=" * 100)
        print(f"🎯 GRAND TOTAL: {sum(person_totals.values()):.2f} hours")
        print(f"👥 Total People: {len(person_totals)}")
        print(f"📁 Total Projects: {len(project_totals)}")
        print(f"📝 Total Worklogs: {worklogs_processed}")
        print("=" * 100)

    except Exception as e:
        logger.error(f"❌ Error querying Tempo data: {e}", exc_info=True)


if __name__ == "__main__":
    query_september_tempo_hours()
