"""Notion MCP integration for database and page access."""

import logging
import json
import subprocess
import tempfile
import os
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class NotionClient:
    """Client for interacting with Notion via MCP server."""

    def __init__(self, api_key: str):
        """
        Initialize Notion client with user's API key.

        Args:
            api_key: Notion Integration API key
        """
        if not api_key or not api_key.strip():
            raise ValueError("Notion API key is required")

        self.api_key = api_key.strip()

    def _create_mcp_config(self) -> str:
        """Create temporary MCP config file with user credentials."""
        config = {
            "mcpServers": {
                "notion": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-notion"],
                    "env": {
                        "NOTION_API_KEY": self.api_key
                    }
                }
            }
        }

        # Create temp file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json.dump(config, f)
            return f.name

    def _call_mcp_tool(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call an MCP tool with the given parameters.

        Args:
            tool_name: Name of the MCP tool to call
            params: Parameters to pass to the tool

        Returns:
            Response from the MCP tool
        """
        config_file = self._create_mcp_config()

        try:
            # Create command to call MCP tool
            # Note: This is a simplified example. In production, you'd use the MCP SDK
            # to properly interact with the MCP server
            cmd = [
                'npx',
                '-y',
                '@modelcontextprotocol/inspector',
                '--config', config_file,
                '--server', 'notion',
                '--tool', tool_name,
                '--params', json.dumps(params)
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                logger.error(f"MCP tool call failed: {result.stderr}")
                raise RuntimeError(f"MCP tool call failed: {result.stderr}")

            return json.loads(result.stdout)
        finally:
            # Clean up temp config file
            try:
                os.unlink(config_file)
            except Exception as e:
                logger.warning(f"Failed to delete temp config file: {e}")

    def search_pages(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search for pages in Notion.

        Args:
            query: Search query string
            limit: Maximum number of results

        Returns:
            List of matching pages
        """
        params = {
            'query': query,
            'limit': limit
        }

        try:
            result = self._call_mcp_tool('search_pages', params)
            return result.get('results', [])
        except Exception as e:
            logger.error(f"Failed to search pages: {e}")
            raise

    def get_page(self, page_id: str) -> Dict[str, Any]:
        """
        Get a Notion page by ID.

        Args:
            page_id: ID of the page

        Returns:
            Page content and metadata
        """
        params = {
            'page_id': page_id
        }

        try:
            result = self._call_mcp_tool('get_page', params)
            return result
        except Exception as e:
            logger.error(f"Failed to get page {page_id}: {e}")
            raise

    def create_page(
        self,
        parent_id: str,
        title: str,
        content: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new Notion page.

        Args:
            parent_id: ID of parent page or database
            title: Page title
            content: Page content blocks (Notion block format)

        Returns:
            Created page metadata
        """
        params = {
            'parent_id': parent_id,
            'title': title
        }

        if content:
            params['content'] = content

        try:
            result = self._call_mcp_tool('create_page', params)
            return result
        except Exception as e:
            logger.error(f"Failed to create page: {e}")
            raise

    def update_page(
        self,
        page_id: str,
        title: str = None,
        content: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Update a Notion page.

        Args:
            page_id: ID of the page to update
            title: New title (optional)
            content: New content blocks (optional)

        Returns:
            Updated page metadata
        """
        params = {
            'page_id': page_id
        }

        if title:
            params['title'] = title
        if content:
            params['content'] = content

        try:
            result = self._call_mcp_tool('update_page', params)
            return result
        except Exception as e:
            logger.error(f"Failed to update page {page_id}: {e}")
            raise

    def list_databases(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        List Notion databases.

        Args:
            limit: Maximum number of databases to return

        Returns:
            List of database metadata
        """
        params = {
            'limit': limit
        }

        try:
            result = self._call_mcp_tool('list_databases', params)
            return result.get('results', [])
        except Exception as e:
            logger.error(f"Failed to list databases: {e}")
            raise

    def query_database(
        self,
        database_id: str,
        filter_params: Dict[str, Any] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Query a Notion database.

        Args:
            database_id: ID of the database
            filter_params: Filter parameters (Notion filter format)
            limit: Maximum number of results

        Returns:
            List of database entries
        """
        params = {
            'database_id': database_id,
            'limit': limit
        }

        if filter_params:
            params['filter'] = filter_params

        try:
            result = self._call_mcp_tool('query_database', params)
            return result.get('results', [])
        except Exception as e:
            logger.error(f"Failed to query database {database_id}: {e}")
            raise

    def create_database_entry(
        self,
        database_id: str,
        properties: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a new entry in a Notion database.

        Args:
            database_id: ID of the database
            properties: Entry properties (Notion property format)

        Returns:
            Created entry metadata
        """
        params = {
            'database_id': database_id,
            'properties': properties
        }

        try:
            result = self._call_mcp_tool('create_database_entry', params)
            return result
        except Exception as e:
            logger.error(f"Failed to create database entry: {e}")
            raise

    def update_database_entry(
        self,
        page_id: str,
        properties: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update an entry in a Notion database.

        Args:
            page_id: ID of the database entry (page)
            properties: Updated properties (Notion property format)

        Returns:
            Updated entry metadata
        """
        params = {
            'page_id': page_id,
            'properties': properties
        }

        try:
            result = self._call_mcp_tool('update_database_entry', params)
            return result
        except Exception as e:
            logger.error(f"Failed to update database entry {page_id}: {e}")
            raise

    def append_block_children(
        self,
        block_id: str,
        children: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Append blocks to a page or block.

        Args:
            block_id: ID of the parent block or page
            children: List of blocks to append (Notion block format)

        Returns:
            Response with appended blocks
        """
        params = {
            'block_id': block_id,
            'children': children
        }

        try:
            result = self._call_mcp_tool('append_block_children', params)
            return result
        except Exception as e:
            logger.error(f"Failed to append blocks to {block_id}: {e}")
            raise

    @staticmethod
    def validate_api_key(api_key: str) -> bool:
        """
        Validate Notion API key by attempting to use it.

        Args:
            api_key: Notion API key to validate

        Returns:
            True if key is valid
        """
        if not api_key or not api_key.strip():
            return False

        try:
            client = NotionClient(api_key)
            # Try to list databases as a validation check
            client.list_databases(limit=1)
            return True
        except Exception as e:
            logger.info(f"API key validation failed: {e}")
            return False
