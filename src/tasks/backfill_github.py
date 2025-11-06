#!/usr/bin/env python3
"""
Backfill GitHub Pull Requests into Pinecone Vector Database

This script fetches pull requests from all accessible GitHub repositories
and ingests them into the Pinecone vector database for semantic search.

Usage:
    python src/tasks/backfill_github.py --days 730
    python src/tasks/backfill_github.py --from-date 2023-01-01 --to-date 2025-11-06
"""

import os
import sys
import time
import argparse
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.insert(0, project_root)

from src.integrations.github_client import GitHubClient
from src.services.vector_ingest import VectorIngestService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Rate limiting configuration
DELAY_BETWEEN_REPOS = 2.0  # Seconds between repositories
DELAY_BETWEEN_BATCHES = 1.0  # Seconds between PR batches
BATCH_SIZE = 50  # PRs per batch


async def backfill_github_prs(
    days_back: int = 730,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    repos: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Backfill GitHub pull requests into Pinecone vector database.

    Args:
        days_back: Number of days to look back (default: 730 = 2 years)
        from_date: Start date in YYYY-MM-DD format (overrides days_back)
        to_date: End date in YYYY-MM-DD format (defaults to today)
        repos: Optional list of specific repo names (format: 'owner/repo')
               If None, fetches from all accessible repositories

    Returns:
        Dictionary with backfill statistics
    """
    start_time = time.time()
    logger.info("=" * 80)
    logger.info("GITHUB PR BACKFILL STARTED")
    logger.info("=" * 80)

    # Initialize clients
    github_client = GitHubClient()
    vector_service = VectorIngestService()

    # Calculate date range
    if from_date and to_date:
        start_date_str = from_date
        end_date_str = to_date
        start_date = datetime.strptime(from_date, '%Y-%m-%d')
        end_date = datetime.strptime(to_date, '%Y-%m-%d')
    else:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')

    logger.info(f"Date range: {start_date_str} to {end_date_str}")
    logger.info(f"Days span: {(end_date - start_date).days}")

    # Get list of repositories to process
    if repos:
        repo_list = repos
        logger.info(f"Processing {len(repo_list)} specific repositories")
    else:
        logger.info("Fetching all accessible repositories...")
        repo_list = await github_client.list_accessible_repos()
        logger.info(f"Found {len(repo_list)} accessible repositories")

    # Statistics
    stats = {
        'success': True,
        'repos_processed': 0,
        'repos_with_prs': 0,
        'total_prs_found': 0,
        'total_prs_ingested': 0,
        'errors': [],
        'start_time': start_time,
        'date_range': f"{start_date_str} to {end_date_str}"
    }

    # Process each repository
    for idx, repo_name in enumerate(repo_list, 1):
        try:
            logger.info("-" * 80)
            logger.info(f"[{idx}/{len(repo_list)}] Processing repository: {repo_name}")

            # Fetch PRs for this repo within date range
            logger.info(f"Fetching PRs from {start_date_str} to {end_date_str}...")

            # Get PRs using GitHub client
            # States: 'open', 'closed', 'all'
            prs = await github_client.get_prs_by_date_range(
                repo_name=repo_name,
                start_date=start_date_str,
                end_date=end_date_str,
                state='all'  # Get both open and closed PRs
            )

            if not prs:
                logger.info(f"✓ No PRs found for {repo_name} in date range")
                stats['repos_processed'] += 1
                time.sleep(DELAY_BETWEEN_REPOS)
                continue

            logger.info(f"Found {len(prs)} PRs in {repo_name}")
            stats['total_prs_found'] += len(prs)
            stats['repos_with_prs'] += 1

            # Process PRs in batches
            for batch_start in range(0, len(prs), BATCH_SIZE):
                batch = prs[batch_start:batch_start + BATCH_SIZE]
                batch_num = (batch_start // BATCH_SIZE) + 1
                total_batches = (len(prs) + BATCH_SIZE - 1) // BATCH_SIZE

                logger.info(f"  Processing batch {batch_num}/{total_batches} ({len(batch)} PRs)...")

                # Ingest batch into vector database
                ingested_count = vector_service.ingest_github_prs(
                    prs=batch,
                    repo_name=repo_name
                )

                stats['total_prs_ingested'] += ingested_count
                logger.info(f"  ✓ Ingested {ingested_count}/{len(batch)} PRs from batch {batch_num}")

                # Rate limiting between batches
                if batch_start + BATCH_SIZE < len(prs):
                    time.sleep(DELAY_BETWEEN_BATCHES)

            stats['repos_processed'] += 1
            logger.info(f"✓ Completed {repo_name}: {len(prs)} PRs processed")

            # Rate limiting between repositories
            if idx < len(repo_list):
                logger.info(f"Waiting {DELAY_BETWEEN_REPOS}s before next repo...")
                time.sleep(DELAY_BETWEEN_REPOS)

        except Exception as e:
            error_msg = f"Error processing repository {repo_name}: {str(e)}"
            logger.error(error_msg)
            stats['errors'].append(error_msg)
            stats['repos_processed'] += 1
            continue

    # Calculate final statistics
    elapsed_time = time.time() - start_time
    stats['elapsed_time'] = elapsed_time
    stats['elapsed_time_formatted'] = f"{elapsed_time / 60:.1f} minutes"

    # Print summary
    logger.info("=" * 80)
    logger.info("GITHUB PR BACKFILL COMPLETE")
    logger.info("=" * 80)
    logger.info(f"Date range: {stats['date_range']}")
    logger.info(f"Repositories processed: {stats['repos_processed']}/{len(repo_list)}")
    logger.info(f"Repositories with PRs: {stats['repos_with_prs']}")
    logger.info(f"Total PRs found: {stats['total_prs_found']}")
    logger.info(f"Total PRs ingested: {stats['total_prs_ingested']}")
    logger.info(f"Elapsed time: {stats['elapsed_time_formatted']}")

    if stats['errors']:
        logger.warning(f"\n⚠️  Errors encountered: {len(stats['errors'])}")
        for error in stats['errors'][:5]:  # Show first 5 errors
            logger.warning(f"  - {error}")
    else:
        logger.info("\n✅ No errors encountered")

    logger.info("=" * 80)

    return stats


def main():
    """Main entry point for CLI execution."""
    parser = argparse.ArgumentParser(
        description='Backfill GitHub pull requests into Pinecone vector database'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=730,
        help='Number of days to look back (default: 730 = 2 years)'
    )
    parser.add_argument(
        '--from-date',
        type=str,
        help='Start date in YYYY-MM-DD format (overrides --days)'
    )
    parser.add_argument(
        '--to-date',
        type=str,
        help='End date in YYYY-MM-DD format (defaults to today)'
    )
    parser.add_argument(
        '--repos',
        type=str,
        nargs='+',
        help='Specific repositories to process (format: owner/repo). If not provided, processes all accessible repos'
    )

    args = parser.parse_args()

    # Validate date arguments
    if args.from_date and not args.to_date:
        parser.error('--to-date is required when using --from-date')

    # Run backfill
    import asyncio
    stats = asyncio.run(backfill_github_prs(
        days_back=args.days,
        from_date=args.from_date,
        to_date=args.to_date,
        repos=args.repos
    ))

    # Exit with appropriate code
    if stats['success'] and not stats['errors']:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()
