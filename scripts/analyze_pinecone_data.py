#!/usr/bin/env python3
"""Analyze Pinecone database to determine date ranges for each data source."""

import os
from dotenv import load_dotenv
from pinecone import Pinecone
from datetime import datetime
from collections import defaultdict

load_dotenv()

# Initialize Pinecone
pc = Pinecone(api_key=os.getenv('PINECONE_API_KEY'))
index = pc.Index(os.getenv('PINECONE_INDEX_NAME', 'agent-pm-context'))

print("=" * 80)
print("PINECONE DATABASE ANALYSIS")
print("=" * 80)

# Get index stats
stats = index.describe_index_stats()
print(f"\n📊 Total vectors in database: {stats.get('total_vector_count', 0):,}")
print(f"   Index dimension: {stats.get('dimension', 0)}")
print(f"   Index fullness: {stats.get('index_fullness', 0) * 100:.2f}%")

# Query by source to get counts and date ranges
sources = ['jira', 'slack', 'tempo', 'fireflies', 'notion']

print("\n" + "=" * 80)
print("DATA SOURCE ANALYSIS")
print("=" * 80)

for source in sources:
    print(f"\n{'=' * 80}")
    print(f"📁 {source.upper()}")
    print(f"{'=' * 80}")

    try:
        # Get total count for this source (using a dummy vector and metadata filter)
        count_result = index.query(
            vector=[0.0] * 1536,
            filter={"source": source},
            top_k=10000,  # Max results to get a count
            include_metadata=True
        )

        total_count = len(count_result.matches)
        print(f"   Total documents: {total_count:,}")

        if total_count == 0:
            print(f"   ❌ No data found for {source}")
            continue

        # Collect all dates from metadata
        dates = []
        timestamps = []

        for match in count_result.matches:
            metadata = match.metadata
            date_str = metadata.get('date')
            timestamp_epoch = metadata.get('timestamp_epoch')

            if date_str:
                dates.append(date_str)
            if timestamp_epoch:
                timestamps.append(timestamp_epoch)

        if dates:
            dates.sort()
            oldest_date = dates[0]
            newest_date = dates[-1]

            print(f"\n   📅 Date Range:")
            print(f"      Oldest: {oldest_date}")
            print(f"      Newest: {newest_date}")

            # Calculate how far back
            oldest_dt = datetime.strptime(oldest_date, '%Y-%m-%d')
            newest_dt = datetime.strptime(newest_date, '%Y-%m-%d')
            days_span = (newest_dt - oldest_dt).days
            days_from_today = (datetime.now() - oldest_dt).days

            print(f"      Span: {days_span} days")
            print(f"      Oldest is {days_from_today} days ago")

        # Get source-specific metadata
        if source == 'jira':
            # Count by project
            projects = defaultdict(int)
            statuses = defaultdict(int)
            issue_types = defaultdict(int)

            for match in count_result.matches:
                metadata = match.metadata
                project = metadata.get('project_key', 'Unknown')
                status = metadata.get('status', 'Unknown')
                issue_type = metadata.get('issue_type', 'Unknown')

                projects[project] += 1
                statuses[status] += 1
                issue_types[issue_type] += 1

            print(f"\n   📊 Breakdown:")
            print(f"      Projects: {len(projects)}")
            for project, count in sorted(projects.items(), key=lambda x: x[1], reverse=True)[:10]:
                print(f"         {project}: {count:,}")

            print(f"\n      Top Issue Types:")
            for itype, count in sorted(issue_types.items(), key=lambda x: x[1], reverse=True)[:5]:
                print(f"         {itype}: {count:,}")

        elif source == 'slack':
            # Count by channel
            channels = defaultdict(int)

            for match in count_result.matches:
                metadata = match.metadata
                channel = metadata.get('channel_name', 'Unknown')
                channels[channel] += 1

            print(f"\n   📊 Breakdown:")
            print(f"      Channels: {len(channels)}")
            for channel, count in sorted(channels.items(), key=lambda x: x[1], reverse=True)[:10]:
                print(f"         {channel}: {count:,}")

        elif source == 'tempo':
            # Count by project and author
            projects = defaultdict(int)
            authors = defaultdict(int)
            total_hours = 0

            for match in count_result.matches:
                metadata = match.metadata
                project = metadata.get('project_key', 'Unknown')
                author = metadata.get('author_name', 'Unknown')
                hours = metadata.get('hours_logged', 0)

                projects[project] += 1
                authors[author] += 1
                total_hours += hours

            print(f"\n   📊 Breakdown:")
            print(f"      Total hours logged: {total_hours:,.1f}h")
            print(f"      Projects: {len(projects)}")
            for project, count in sorted(projects.items(), key=lambda x: x[1], reverse=True)[:10]:
                print(f"         {project}: {count:,} worklogs")

            print(f"\n      Top Contributors:")
            for author, count in sorted(authors.items(), key=lambda x: x[1], reverse=True)[:5]:
                print(f"         {author}: {count:,} worklogs")

        elif source == 'fireflies':
            # Count meetings
            project_tags = defaultdict(int)

            for match in count_result.matches:
                metadata = match.metadata
                tags = metadata.get('project_tags', [])
                if tags:
                    for tag in tags:
                        project_tags[tag] += 1

            print(f"\n   📊 Breakdown:")
            print(f"      Total meetings: {total_count:,}")
            if project_tags:
                print(f"      Project tags:")
                for tag, count in sorted(project_tags.items(), key=lambda x: x[1], reverse=True)[:10]:
                    print(f"         {tag}: {count:,} meetings")

        elif source == 'notion':
            print(f"\n   📊 Breakdown:")
            print(f"      Total pages: {total_count:,}")

    except Exception as e:
        print(f"   ❌ Error querying {source}: {e}")
        continue

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)

# Print summary table
print("\n| Source     | Count  | Oldest Date | Newest Date | Days Back |")
print("|------------|--------|-------------|-------------|-----------|")

for source in sources:
    try:
        result = index.query(
            vector=[0.0] * 1536,
            filter={"source": source},
            top_k=10000,
            include_metadata=True
        )

        count = len(result.matches)

        if count == 0:
            print(f"| {source:10} | {count:6} | N/A         | N/A         | N/A       |")
            continue

        dates = [m.metadata.get('date') for m in result.matches if m.metadata.get('date')]
        if dates:
            dates.sort()
            oldest = dates[0]
            newest = dates[-1]
            oldest_dt = datetime.strptime(oldest, '%Y-%m-%d')
            days_back = (datetime.now() - oldest_dt).days
            print(f"| {source:10} | {count:6,} | {oldest}  | {newest}  | {days_back:5} d  |")
        else:
            print(f"| {source:10} | {count:6,} | N/A         | N/A         | N/A       |")
    except:
        print(f"| {source:10} | ERROR  | ERROR       | ERROR       | ERROR     |")

print("\n" + "=" * 80)
print("COMPLETE")
print("=" * 80)
