#!/usr/bin/env python3
"""Batched Tempo backfill script - runs 12 monthly chunks sequentially.

This script breaks the full 365-day backfill into 12 monthly chunks to avoid:
- Memory exhaustion
- Task timeouts
- Silent failures

Each chunk is tracked with checkpointing, so you can resume if interrupted.

Usage:
    python scripts/batched_tempo_backfill.py
"""

import requests
import time
import sys
from datetime import datetime, timedelta
from typing import List, Tuple

# Configuration
API_URL = "https://agent-pm-tsbbb.ondigitalocean.app"
ADMIN_API_KEY = "bc2233d757d98984b806514c36535e5b4cb7908d3283ddbddbbbe052217e31fa"


def generate_monthly_chunks(days_back: int = 365) -> List[Tuple[str, str, str]]:
    """Generate monthly date range chunks for backfill.

    Args:
        days_back: Total days to backfill (default 365)

    Returns:
        List of (from_date, to_date, batch_id) tuples
    """
    chunks = []
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)

    current_date = start_date
    chunk_num = 1

    while current_date < end_date:
        # Calculate chunk end date (30 days forward or end_date, whichever is earlier)
        chunk_end = min(current_date + timedelta(days=30), end_date)

        from_str = current_date.strftime("%Y-%m-%d")
        to_str = chunk_end.strftime("%Y-%m-%d")
        batch_id = f"tempo-chunk-{chunk_num:02d}-{from_str}_to_{to_str}"

        chunks.append((from_str, to_str, batch_id))

        current_date = chunk_end + timedelta(days=1)  # Start next chunk day after
        chunk_num += 1

    return chunks


def trigger_backfill_chunk(from_date: str, to_date: str, batch_id: str) -> dict:
    """Trigger a single backfill chunk via API.

    Args:
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)
        batch_id: Batch identifier

    Returns:
        API response dict
    """
    url = f"{API_URL}/api/backfill/tempo"
    params = {
        "from_date": from_date,
        "to_date": to_date,
        "batch_id": batch_id
    }
    headers = {
        "X-Admin-Key": ADMIN_API_KEY,
        "Content-Type": "application/json"
    }

    print(f"🚀 Triggering backfill: {batch_id}")
    print(f"   Date range: {from_date} to {to_date}")

    try:
        response = requests.post(url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ Error triggering backfill: {e}")
        return {"success": False, "error": str(e)}


def main():
    """Main execution function."""
    print("=" * 80)
    print("Batched Tempo Backfill Script")
    print("=" * 80)
    print()

    # Generate monthly chunks
    chunks = generate_monthly_chunks(days_back=365)
    print(f"📋 Generated {len(chunks)} monthly chunks")
    print()

    # Process each chunk
    successful_chunks = 0
    failed_chunks = []

    for idx, (from_date, to_date, batch_id) in enumerate(chunks, 1):
        print(f"[{idx}/{len(chunks)}] Processing chunk: {batch_id}")

        # Trigger backfill
        result = trigger_backfill_chunk(from_date, to_date, batch_id)

        if result.get("success"):
            if result.get("already_completed"):
                print(f"✅ Chunk already completed - skipping")
                successful_chunks += 1
            else:
                task_id = result.get("task_id")
                print(f"✅ Chunk triggered successfully")
                print(f"   Task ID: {task_id}")

                # Wait 3 minutes between chunks to avoid overwhelming the worker
                if idx < len(chunks):
                    print(f"⏳ Waiting 180 seconds before next chunk...")
                    print()
                    time.sleep(180)

                successful_chunks += 1
        else:
            error = result.get("error", "Unknown error")
            print(f"❌ Chunk failed: {error}")
            failed_chunks.append((batch_id, error))

        print()

    # Summary
    print("=" * 80)
    print("Backfill Summary")
    print("=" * 80)
    print(f"✅ Successful chunks: {successful_chunks}/{len(chunks)}")
    print(f"❌ Failed chunks: {len(failed_chunks)}/{len(chunks)}")

    if failed_chunks:
        print()
        print("Failed chunks:")
        for batch_id, error in failed_chunks:
            print(f"  - {batch_id}: {error}")
        sys.exit(1)
    else:
        print()
        print("🎉 All chunks completed successfully!")
        sys.exit(0)


if __name__ == "__main__":
    main()
