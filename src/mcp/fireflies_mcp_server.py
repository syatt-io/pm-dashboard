#!/usr/bin/env python3
"""Fireflies.ai MCP Server."""

import os
import json
import logging
from typing import Dict, Any, List
from datetime import datetime
import asyncio
from aiohttp import web
import aiohttp_cors

from src.integrations.fireflies import FirefliesClient


logger = logging.getLogger(__name__)


class FirefliesMCPServer:
    """MCP Server for Fireflies.ai integration."""

    def __init__(self):
        self.client = FirefliesClient(os.getenv('FIREFLIES_API_KEY'))
        self.app = web.Application()
        self.setup_routes()

    def setup_routes(self):
        """Setup HTTP routes for MCP endpoints."""
        self.app.router.add_post('/mcp', self.handle_mcp_request)
        self.app.router.add_get('/health', self.health_check)

        # Setup CORS
        cors = aiohttp_cors.setup(self.app, defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
                allow_methods="*"
            )
        })

        for route in list(self.app.router.routes()):
            cors.add(route)

    async def handle_mcp_request(self, request: web.Request) -> web.Response:
        """Handle MCP request."""
        try:
            data = await request.json()
            method = data.get('method')
            params = data.get('params', {})

            if method == 'fireflies/getRecentMeetings':
                result = await self._get_recent_meetings(params)
            elif method == 'fireflies/getTranscript':
                result = await self._get_transcript(params)
            elif method == 'fireflies/searchMeetings':
                result = await self._search_meetings(params)
            else:
                result = {
                    'success': False,
                    'error': f'Unknown method: {method}'
                }

            return web.json_response(result)

        except Exception as e:
            logger.error(f"Error handling MCP request: {e}")
            return web.json_response({
                'success': False,
                'error': str(e)
            }, status=500)

    async def _get_recent_meetings(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get recent meetings."""
        try:
            days_back = params.get('days_back', 7)
            meetings = self.client.get_recent_meetings(days_back)
            return {
                'success': True,
                'meetings': meetings
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    async def _get_transcript(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get meeting transcript."""
        try:
            meeting_id = params.get('meeting_id')
            if not meeting_id:
                return {
                    'success': False,
                    'error': 'meeting_id is required'
                }

            transcript = self.client.get_meeting_transcript(meeting_id)
            if transcript:
                return {
                    'success': True,
                    'transcript': {
                        'id': transcript.id,
                        'title': transcript.title,
                        'date': transcript.date.isoformat(),
                        'duration': transcript.duration,
                        'attendees': transcript.attendees,
                        'transcript': transcript.transcript,
                        'summary': transcript.summary,
                        'action_items': transcript.action_items,
                        'topics': transcript.topics
                    }
                }
            else:
                return {
                    'success': False,
                    'error': 'Transcript not found'
                }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    async def _search_meetings(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Search meetings."""
        try:
            query = params.get('query', '')
            limit = params.get('limit', 10)

            meetings = self.client.search_meetings(query, limit)
            return {
                'success': True,
                'meetings': meetings
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    async def health_check(self, request: web.Request) -> web.Response:
        """Health check endpoint."""
        try:
            # Simple health check - try to make a basic API call
            meetings = self.client.get_recent_meetings(1)
            return web.json_response({
                'status': 'healthy',
                'timestamp': datetime.now().isoformat(),
                'service': 'fireflies-mcp'
            })
        except Exception as e:
            return web.json_response({
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.now().isoformat(),
                'service': 'fireflies-mcp'
            }, status=503)


async def main():
    """Main entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    server = FirefliesMCPServer()
    port = int(os.getenv('MCP_SERVER_PORT', 3001))

    logger.info(f"Starting Fireflies MCP Server on port {port}")

    runner = web.AppRunner(server.app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

    logger.info("Fireflies MCP Server started successfully")

    # Keep the server running
    try:
        await asyncio.Future()  # Run forever
    except KeyboardInterrupt:
        logger.info("Shutting down Fireflies MCP Server...")
    finally:
        await runner.cleanup()


if __name__ == '__main__':
    asyncio.run(main())