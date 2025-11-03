"""
Fireflies.ai Webhook Handler

Receives webhook notifications when meeting transcripts are ready.
Implements HMAC SHA-256 signature verification for security.
"""

import logging
import hmac
import hashlib
import os
from typing import Dict, Optional
from flask import request, jsonify
from datetime import datetime, timezone

from src.celery_app import celery_app
from src.integrations.fireflies import FirefliesClient
from src.processors.transcript_analyzer import TranscriptAnalyzer
from src.managers.notifications import NotificationManager
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import json
import uuid
import asyncio

logger = logging.getLogger(__name__)


def verify_fireflies_signature(payload_body: bytes, signature_header: str, webhook_secret: str) -> bool:
    """
    Verify the HMAC SHA-256 signature from Fireflies webhook.

    Args:
        payload_body: Raw request body as bytes
        signature_header: Value from x-hub-signature header (format: "sha256=...")
        webhook_secret: Fireflies webhook secret

    Returns:
        True if signature is valid, False otherwise
    """
    if not signature_header or not signature_header.startswith('sha256='):
        logger.warning("Invalid signature header format")
        return False

    # Extract signature from header (remove "sha256=" prefix)
    expected_signature = signature_header[7:]

    # Compute HMAC SHA-256
    computed_hmac = hmac.new(
        webhook_secret.encode('utf-8'),
        payload_body,
        hashlib.sha256
    )
    computed_signature = computed_hmac.hexdigest()

    # Constant-time comparison to prevent timing attacks
    return hmac.compare_digest(computed_signature, expected_signature)


def handle_fireflies_webhook():
    """
    Flask route handler for Fireflies webhooks.

    Validates signature, checks idempotency, and enqueues Celery task.
    Returns 200 OK immediately to avoid timeouts.
    """
    try:
        # Get webhook secret from environment
        webhook_secret = os.getenv('FIREFLIES_WEBHOOK_SECRET')
        if not webhook_secret:
            logger.error("FIREFLIES_WEBHOOK_SECRET not configured")
            return jsonify({"error": "Webhook not configured"}), 500

        # Get raw request body for signature verification
        payload_body = request.get_data()
        signature_header = request.headers.get('x-hub-signature', '')

        # Verify HMAC signature
        if not verify_fireflies_signature(payload_body, signature_header, webhook_secret):
            logger.warning(f"Invalid webhook signature from IP: {request.remote_addr}")
            return jsonify({"error": "Invalid signature"}), 401

        # Parse JSON payload
        try:
            payload = request.get_json()
        except Exception as e:
            logger.error(f"Failed to parse webhook payload: {e}")
            return jsonify({"error": "Invalid JSON"}), 400

        # Extract meeting ID and event type
        meeting_id = payload.get('meetingId')
        event_type = payload.get('event')

        if not meeting_id:
            logger.error(f"Webhook payload missing meetingId: {payload}")
            return jsonify({"error": "Missing meetingId"}), 400

        if event_type != 'transcript.completed':
            logger.info(f"Ignoring non-completion event: {event_type}")
            return jsonify({"status": "ignored", "reason": "not a completion event"}), 200

        logger.info(f"Received webhook for meeting {meeting_id}, event: {event_type}")

        # Check idempotency: has this meeting already been processed?
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            logger.error("DATABASE_URL not configured")
            return jsonify({"error": "Database not configured"}), 500

        engine = create_engine(database_url)
        Session = sessionmaker(bind=engine)
        session = Session()

        try:
            result = session.execute(
                text("SELECT id FROM processed_meetings WHERE fireflies_id = :fireflies_id"),
                {"fireflies_id": meeting_id}
            )
            existing_meeting = result.fetchone()

            if existing_meeting:
                logger.info(f"Meeting {meeting_id} already processed (idempotency check), skipping")
                return jsonify({
                    "status": "already_processed",
                    "meeting_id": meeting_id
                }), 200
        finally:
            session.close()

        # Enqueue Celery task for async processing
        # This returns immediately to avoid webhook timeout
        process_fireflies_meeting.delay(meeting_id)

        logger.info(f"Enqueued Celery task for meeting {meeting_id}")

        return jsonify({
            "status": "enqueued",
            "meeting_id": meeting_id
        }), 200

    except Exception as e:
        logger.error(f"Error handling Fireflies webhook: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@celery_app.task(name='webhooks.process_fireflies_meeting', bind=True, max_retries=3)
def process_fireflies_meeting(self, meeting_id: str):
    """
    Celery task to process a single meeting from Fireflies webhook.

    This task is enqueued by the webhook handler and runs asynchronously.
    Reuses the same logic as the nightly meeting analysis job.

    Args:
        meeting_id: Fireflies meeting ID
    """
    logger.info(f"Starting Celery task to process meeting {meeting_id}")

    try:
        # Initialize clients
        fireflies_api_key = os.getenv("FIREFLIES_SYSTEM_API_KEY") or os.getenv("FIREFLIES_API_KEY")
        if not fireflies_api_key:
            raise ValueError("FIREFLIES_API_KEY not configured")

        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL not configured")

        fireflies_client = FirefliesClient(api_key=fireflies_api_key)
        analyzer = TranscriptAnalyzer()

        # Initialize notification manager
        try:
            notification_manager = NotificationManager(None)
            logger.info("Notification manager initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize notification manager: {e}")
            notification_manager = None

        # Database connection
        engine = create_engine(database_url)
        Session = sessionmaker(bind=engine)
        session = Session()

        try:
            # Double-check idempotency in case of race condition
            result = session.execute(
                text("SELECT id FROM processed_meetings WHERE fireflies_id = :fireflies_id"),
                {"fireflies_id": meeting_id}
            )
            if result.fetchone():
                logger.info(f"Meeting {meeting_id} already processed (race condition check), skipping")
                return {"status": "already_processed", "meeting_id": meeting_id}

            # Fetch full transcript from Fireflies
            logger.info(f"Fetching transcript for meeting {meeting_id}")
            transcript_data = fireflies_client.get_meeting_transcript(meeting_id)

            if not transcript_data:
                logger.error(f"Failed to fetch transcript for meeting {meeting_id}")
                raise ValueError(f"Could not fetch transcript for meeting {meeting_id}")

            transcript_text = transcript_data.get("transcript", "")
            meeting_title = transcript_data.get("title", "Untitled Meeting")

            if not transcript_text or len(transcript_text) < 100:
                logger.warning(f"Transcript too short or empty for meeting {meeting_id}, skipping")
                return {"status": "skipped", "reason": "transcript too short", "meeting_id": meeting_id}

            # Convert date from milliseconds to datetime
            date_ms = transcript_data.get("date")
            if isinstance(date_ms, (int, float)) and date_ms > 1000000000000:
                meeting_date = datetime.fromtimestamp(date_ms / 1000)
            else:
                meeting_date = datetime.now()

            # Match meeting to active projects via keywords
            logger.info(f"Matching meeting '{meeting_title}' to active projects")

            # Get active projects with keywords
            result = session.execute(
                text("SELECT key, name FROM projects WHERE is_active = true")
            )
            projects = [{"key": row[0], "name": row[1]} for row in result]

            if not projects:
                logger.warning("No active projects found, skipping meeting")
                return {"status": "skipped", "reason": "no active projects", "meeting_id": meeting_id}

            # Get keywords for each project
            for project in projects:
                keyword_result = session.execute(
                    text("SELECT keyword FROM project_keywords WHERE project_key = :project_key"),
                    {"project_key": project["key"]}
                )
                project["keywords"] = [row[0].lower() for row in keyword_result]

            # Find matching project
            matched_project = None
            title_lower = meeting_title.lower()

            for project in projects:
                if not project.get("keywords"):
                    continue

                for keyword in project["keywords"]:
                    if keyword in title_lower:
                        matched_project = project
                        logger.info(
                            f"Matched meeting '{meeting_title}' to project {project['key']} "
                            f"via keyword '{keyword}'"
                        )
                        break

                if matched_project:
                    break

            if not matched_project:
                logger.info(f"Meeting '{meeting_title}' does not match any active project keywords, skipping")
                return {"status": "skipped", "reason": "no project match", "meeting_id": meeting_id}

            # Run AI analysis
            logger.info(f"Running AI analysis for meeting {meeting_id}")
            analysis = analyzer.analyze_transcript(
                transcript=transcript_text,
                meeting_title=meeting_title,
                meeting_date=meeting_date
            )

            # Prepare action items for storage
            action_items_data = []
            for item in analysis.action_items:
                action_items_data.append({
                    "title": item.title,
                    "description": item.description,
                    "assignee": item.assignee,
                    "due_date": item.due_date,
                    "priority": item.priority,
                    "context": item.context,
                    "dependencies": item.dependencies or []
                })

            # Prepare topics for storage
            topics_data = []
            for topic in analysis.topics:
                topics_data.append({
                    "title": topic.title,
                    "content_items": topic.content_items
                })

            # Store in database
            meeting_uuid = str(uuid.uuid4())
            now = datetime.now(timezone.utc)

            session.execute(
                text("""
                    INSERT INTO processed_meetings (
                        id, fireflies_id, title, date, duration,
                        topics, action_items,
                        analyzed_at, created_at, updated_at
                    ) VALUES (
                        :id, :fireflies_id, :title, :date, :duration,
                        :topics, :action_items,
                        :analyzed_at, :created_at, :updated_at
                    )
                """),
                {
                    "id": meeting_uuid,
                    "fireflies_id": meeting_id,
                    "title": meeting_title,
                    "date": meeting_date,
                    "duration": transcript_data.get("duration", 0),
                    "topics": json.dumps(topics_data),
                    "action_items": json.dumps(action_items_data),
                    "analyzed_at": now,
                    "created_at": now,
                    "updated_at": now
                }
            )

            session.commit()

            logger.info(
                f"Successfully analyzed meeting {meeting_id}: "
                f"{len(analysis.topics)} topics, "
                f"{len(analysis.action_items)} action items"
            )

            # Send email notifications if enabled
            try:
                result = session.execute(
                    text("SELECT send_meeting_emails FROM projects WHERE key = :key"),
                    {"key": matched_project["key"]}
                )
                row = result.fetchone()
                send_emails = row[0] if row else False

                if send_emails and notification_manager:
                    # Extract participant emails
                    attendees = transcript_data.get("attendees", [])
                    recipient_emails = [
                        attendee.get("email")
                        for attendee in attendees
                        if isinstance(attendee, dict) and attendee.get("email")
                    ]

                    if recipient_emails:
                        logger.info(
                            f"Sending meeting analysis email to {len(recipient_emails)} participants "
                            f"for project {matched_project['key']}"
                        )

                        email_result = asyncio.run(
                            notification_manager.send_meeting_analysis_email(
                                meeting_title=meeting_title,
                                meeting_date=meeting_date,
                                recipients=recipient_emails,
                                topics=topics_data,
                                action_items=action_items_data
                            )
                        )

                        if email_result.get("success"):
                            logger.info(f"✅ Meeting analysis email sent successfully")
                        else:
                            logger.error(f"Failed to send meeting analysis email: {email_result.get('error')}")
                    else:
                        logger.warning(f"No participant emails found for meeting {meeting_id}")
                elif not send_emails:
                    logger.debug(f"Email notifications disabled for project {matched_project['key']}")
                elif not notification_manager:
                    logger.warning("Notification manager not available for emails")

            except Exception as email_error:
                logger.error(f"Error sending meeting analysis email: {email_error}", exc_info=True)
                # Don't fail the whole task if email fails

            return {
                "status": "success",
                "meeting_id": meeting_id,
                "meeting_title": meeting_title,
                "project_key": matched_project["key"],
                "topics_count": len(analysis.topics),
                "action_items_count": len(analysis.action_items)
            }

        except Exception as e:
            session.rollback()
            logger.error(f"Error processing meeting {meeting_id}: {e}", exc_info=True)
            raise
        finally:
            session.close()

    except Exception as e:
        logger.error(f"Celery task failed for meeting {meeting_id}: {e}", exc_info=True)

        # Retry with exponential backoff (3 attempts total)
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
