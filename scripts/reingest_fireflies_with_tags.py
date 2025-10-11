#!/usr/bin/env python3
"""Re-ingest all Fireflies meetings to add project_tags metadata.

This script re-processes all Fireflies meetings that have already been ingested
to add the new project_tags field based on keyword matching.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.integrations.fireflies import FirefliesClient
from src.services.vector_ingest import VectorIngestService
from config.settings import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def reingest_fireflies():
    """Re-ingest all Fireflies meetings to add project tags."""

    logger.info("🔄 Starting Fireflies re-ingestion to add project tags...")

    try:
        # Initialize services
        ingest_service = VectorIngestService()
        fireflies_client = FirefliesClient(api_key=settings.fireflies.api_key)

        # Fetch all meetings from last year (adjust days_back as needed)
        days_back = 365
        logger.info(f"📥 Fetching meetings from last {days_back} days...")
        meetings = fireflies_client.get_recent_meetings(days_back=days_back, limit=1000)

        if not meetings:
            logger.warning("⚠️  No meetings found")
            return

        logger.info(f"✅ Found {len(meetings)} meetings")

        # Fetch full transcripts
        logger.info("📝 Fetching full transcripts...")
        transcripts = []
        for i, meeting in enumerate(meetings, 1):
            try:
                if i % 10 == 0:
                    logger.info(f"   Progress: {i}/{len(meetings)} transcripts fetched...")

                transcript = fireflies_client.get_meeting_transcript(meeting['id'])
                if transcript:
                    transcript_dict = {
                        'id': transcript.id,
                        'title': transcript.title,
                        'date': transcript.date.timestamp() * 1000,
                        'duration': transcript.duration,
                        'attendees': [{'name': name} for name in transcript.attendees],
                        'transcript': transcript.transcript,
                        'sharing_settings': {
                            'shared_with': [],
                            'is_public': False
                        }
                    }
                    transcripts.append(transcript_dict)

            except Exception as e:
                logger.error(f"Error fetching transcript {meeting['id']}: {e}")
                continue

        if not transcripts:
            logger.warning("⚠️  No transcripts to ingest")
            return

        logger.info(f"✅ Fetched {len(transcripts)} transcripts")

        # Re-ingest with new project_tags field
        logger.info("📊 Re-ingesting into Pinecone with project tags...")
        total_ingested = ingest_service.ingest_fireflies_transcripts(transcripts=transcripts)

        logger.info(f"✅ Successfully re-ingested {total_ingested} transcripts with project tags!")

    except Exception as e:
        logger.error(f"Re-ingestion failed: {e}")
        raise

if __name__ == "__main__":
    reingest_fireflies()
