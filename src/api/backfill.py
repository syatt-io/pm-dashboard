"""
Backfill API endpoints for vector database synchronization.

This module provides REST API endpoints for triggering incremental backfills
of various data sources (Jira, Slack, Notion, Fireflies, GitHub, Tempo) into
the Pinecone vector database.

All backfill operations are executed asynchronously via Celery tasks.
"""

import logging
from flask import Blueprint, request, jsonify
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Create Blueprint
backfill_bp = Blueprint('backfill', __name__, url_prefix='/api/backfill')


def verify_admin_key() -> bool:
    """Verify X-Admin-Key header for security."""
    import os

    admin_key = request.headers.get('X-Admin-Key')
    expected_key = os.getenv('ADMIN_API_KEY')

    if not expected_key:
        logger.error("ADMIN_API_KEY environment variable not set")
        return False

    if not admin_key or admin_key != expected_key:
        return False
    return True


@backfill_bp.route('/jira', methods=['POST'])
def backfill_jira():
    """
    Trigger Jira issues backfill.

    Query Parameters:
        days (int): Number of days to backfill (default: 1)
        active_only (bool): Only backfill active projects (default: true)
        projects (str): Comma-separated project keys to backfill (optional)

    Returns:
        JSON response with task ID and status
    """
    if not verify_admin_key():
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        days = int(request.args.get('days', 1))
        active_only = request.args.get('active_only', 'true').lower() == 'true'
        projects = request.args.get('projects')  # Comma-separated

        # Import here to avoid circular dependency
        from src.tasks.backfill_tasks import backfill_jira_task

        # Queue Celery task
        task = backfill_jira_task.delay(
            days_back=days,
            active_only=active_only,
            project_filter=projects.split(',') if projects else None
        )

        logger.info(f"✅ Jira backfill task queued: {task.id} (days={days}, active_only={active_only})")

        return jsonify({
            'success': True,
            'task_id': task.id,
            'source': 'jira',
            'params': {
                'days': days,
                'active_only': active_only,
                'projects': projects
            },
            'message': f'Jira backfill queued for last {days} days'
        }), 202

    except Exception as e:
        logger.error(f"❌ Error queueing Jira backfill: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@backfill_bp.route('/slack', methods=['POST'])
def backfill_slack():
    """
    Trigger Slack messages backfill.

    Query Parameters:
        days (int): Number of days to backfill (default: 1)
        channels (str): Comma-separated channel IDs (optional, all if not specified)

    Returns:
        JSON response with task ID and status
    """
    if not verify_admin_key():
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        days = int(request.args.get('days', 1))
        channels = request.args.get('channels')

        from src.tasks.backfill_tasks import backfill_slack_task

        task = backfill_slack_task.delay(
            days_back=days,
            channel_filter=channels.split(',') if channels else None
        )

        logger.info(f"✅ Slack backfill task queued: {task.id} (days={days})")

        return jsonify({
            'success': True,
            'task_id': task.id,
            'source': 'slack',
            'params': {
                'days': days,
                'channels': channels
            },
            'message': f'Slack backfill queued for last {days} days'
        }), 202

    except Exception as e:
        logger.error(f"❌ Error queueing Slack backfill: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@backfill_bp.route('/notion', methods=['POST'])
def backfill_notion():
    """
    Trigger Notion pages backfill.

    Query Parameters:
        days (int): Number of days to backfill (default: 1)

    Returns:
        JSON response with task ID and status
    """
    if not verify_admin_key():
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        days = int(request.args.get('days', 1))

        from src.tasks.backfill_tasks import backfill_notion_task

        task = backfill_notion_task.delay(days_back=days)

        logger.info(f"✅ Notion backfill task queued: {task.id} (days={days})")

        return jsonify({
            'success': True,
            'task_id': task.id,
            'source': 'notion',
            'params': {'days': days},
            'message': f'Notion backfill queued for last {days} days'
        }), 202

    except Exception as e:
        logger.error(f"❌ Error queueing Notion backfill: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@backfill_bp.route('/fireflies', methods=['POST'])
def backfill_fireflies():
    """
    Trigger Fireflies transcripts backfill.

    Query Parameters:
        days (int): Number of days to backfill (default: 1)
        limit (int): Max transcripts to fetch (default: 100)

    Returns:
        JSON response with task ID and status
    """
    if not verify_admin_key():
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        days = int(request.args.get('days', 1))
        limit = int(request.args.get('limit', 100))

        from src.tasks.backfill_tasks import backfill_fireflies_task

        task = backfill_fireflies_task.delay(
            days_back=days,
            limit=limit
        )

        logger.info(f"✅ Fireflies backfill task queued: {task.id} (days={days}, limit={limit})")

        return jsonify({
            'success': True,
            'task_id': task.id,
            'source': 'fireflies',
            'params': {
                'days': days,
                'limit': limit
            },
            'message': f'Fireflies backfill queued for last {days} days'
        }), 202

    except Exception as e:
        logger.error(f"❌ Error queueing Fireflies backfill: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@backfill_bp.route('/github', methods=['POST'])
def backfill_github():
    """
    Trigger GitHub data backfill (PRs, issues, commits).

    Query Parameters:
        days (int): Number of days to backfill (default: 1)
        repos (str): Comma-separated repo names (optional, all if not specified)

    Returns:
        JSON response with task ID and status
    """
    if not verify_admin_key():
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        days = int(request.args.get('days', 1))
        repos = request.args.get('repos')

        from src.tasks.backfill_tasks import backfill_github_task

        task = backfill_github_task.delay(
            days_back=days,
            repo_filter=repos.split(',') if repos else None
        )

        logger.info(f"✅ GitHub backfill task queued: {task.id} (days={days})")

        return jsonify({
            'success': True,
            'task_id': task.id,
            'source': 'github',
            'params': {
                'days': days,
                'repos': repos
            },
            'message': f'GitHub backfill queued for last {days} days'
        }), 202

    except Exception as e:
        logger.error(f"❌ Error queueing GitHub backfill: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@backfill_bp.route('/tempo', methods=['POST'])
def backfill_tempo():
    """
    Trigger Tempo worklogs backfill.

    Query Parameters:
        days (int): Number of days to backfill (default: 1)

    Returns:
        JSON response with task ID and status
    """
    if not verify_admin_key():
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        days = int(request.args.get('days', 1))

        from src.tasks.backfill_tasks import backfill_tempo_task

        task = backfill_tempo_task.delay(days_back=days)

        logger.info(f"✅ Tempo backfill task queued: {task.id} (days={days})")

        return jsonify({
            'success': True,
            'task_id': task.id,
            'source': 'tempo',
            'params': {'days': days},
            'message': f'Tempo backfill queued for last {days} days'
        }), 202

    except Exception as e:
        logger.error(f"❌ Error queueing Tempo backfill: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@backfill_bp.route('/status/<task_id>', methods=['GET'])
def backfill_status(task_id: str):
    """
    Check status of a backfill task.

    Path Parameters:
        task_id (str): Celery task ID

    Returns:
        JSON response with task status and result
    """
    if not verify_admin_key():
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        from celery.result import AsyncResult

        task = AsyncResult(task_id)

        response = {
            'task_id': task_id,
            'status': task.state,
            'ready': task.ready()
        }

        if task.ready():
            if task.successful():
                response['result'] = task.result
            elif task.failed():
                response['error'] = str(task.info)
        else:
            # Task is pending or running
            if task.info:
                response['info'] = str(task.info)

        return jsonify(response), 200

    except Exception as e:
        logger.error(f"❌ Error checking task status: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@backfill_bp.route('/sync-status', methods=['GET'])
def sync_status():
    """
    Get overall sync status for all data sources.

    Returns:
        JSON response with vector counts and last sync times
    """
    if not verify_admin_key():
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        from src.services.vector_ingest import VectorIngestService

        service = VectorIngestService()
        stats = service.pinecone_index.describe_index_stats()

        return jsonify({
            'success': True,
            'total_vectors': stats.total_vector_count,
            'namespaces': dict(stats.namespaces) if hasattr(stats, 'namespaces') else {},
            'timestamp': stats.dimension if hasattr(stats, 'dimension') else None
        }), 200

    except Exception as e:
        logger.error(f"❌ Error getting sync status: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
