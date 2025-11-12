"""Google Workspace MCP integration for Docs and Sheets access."""

import logging
import json
import subprocess
import tempfile
import os
from typing import Optional, Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)


class GoogleWorkspaceClient:
    """Client for interacting with Google Workspace via MCP server."""

    def __init__(self, oauth_token: Dict[str, Any]):
        """
        Initialize Google Workspace client with user's OAuth token.

        Args:
            oauth_token: Dictionary containing access_token, refresh_token, and token_uri
        """
        self.oauth_token = oauth_token
        self.access_token = oauth_token.get("access_token")
        self.refresh_token = oauth_token.get("refresh_token")
        self.token_expiry = oauth_token.get("expiry")

        if not self.access_token:
            raise ValueError("OAuth token must contain 'access_token'")

    def _create_mcp_config(self) -> str:
        """Create temporary MCP config file with user credentials."""
        config = {
            "mcpServers": {
                "google-drive": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-gdrive"],
                    "env": {
                        "GOOGLE_ACCESS_TOKEN": self.access_token,
                        "GOOGLE_REFRESH_TOKEN": self.refresh_token or "",
                    },
                }
            }
        }

        # Create temp file
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
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
                "npx",
                "-y",
                "@modelcontextprotocol/inspector",
                "--config",
                config_file,
                "--server",
                "google-drive",
                "--tool",
                tool_name,
                "--params",
                json.dumps(params),
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

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

    def list_files(
        self, query: str = None, mime_type: str = None, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        List files from Google Drive.

        Args:
            query: Search query string
            mime_type: Filter by MIME type (e.g., 'application/vnd.google-apps.document')
            limit: Maximum number of files to return

        Returns:
            List of file metadata dictionaries
        """
        params = {"limit": limit}

        if query:
            params["query"] = query
        if mime_type:
            params["mimeType"] = mime_type

        try:
            result = self._call_mcp_tool("list_files", params)
            return result.get("files", [])
        except Exception as e:
            logger.error(f"Failed to list files: {e}")
            raise

    def read_document(self, document_id: str) -> Dict[str, Any]:
        """
        Read a Google Doc.

        Args:
            document_id: ID of the document to read

        Returns:
            Document content and metadata
        """
        params = {"document_id": document_id}

        try:
            result = self._call_mcp_tool("read_document", params)
            return result
        except Exception as e:
            logger.error(f"Failed to read document {document_id}: {e}")
            raise

    def read_sheet(self, spreadsheet_id: str, range_name: str = None) -> Dict[str, Any]:
        """
        Read a Google Sheet.

        Args:
            spreadsheet_id: ID of the spreadsheet
            range_name: Optional range in A1 notation (e.g., 'Sheet1!A1:D10')

        Returns:
            Sheet data and metadata
        """
        params = {"spreadsheet_id": spreadsheet_id}

        if range_name:
            params["range"] = range_name

        try:
            result = self._call_mcp_tool("read_sheet", params)
            return result
        except Exception as e:
            logger.error(f"Failed to read spreadsheet {spreadsheet_id}: {e}")
            raise

    def create_document(self, title: str, content: str = "") -> Dict[str, Any]:
        """
        Create a new Google Doc.

        Args:
            title: Title of the document
            content: Initial content (plain text)

        Returns:
            Created document metadata
        """
        params = {"title": title, "content": content}

        try:
            result = self._call_mcp_tool("create_document", params)
            return result
        except Exception as e:
            logger.error(f"Failed to create document: {e}")
            raise

    def update_document(self, document_id: str, content: str) -> Dict[str, Any]:
        """
        Update a Google Doc.

        Args:
            document_id: ID of the document to update
            content: New content (plain text)

        Returns:
            Updated document metadata
        """
        params = {"document_id": document_id, "content": content}

        try:
            result = self._call_mcp_tool("update_document", params)
            return result
        except Exception as e:
            logger.error(f"Failed to update document {document_id}: {e}")
            raise

    def create_sheet(self, title: str, data: List[List[Any]] = None) -> Dict[str, Any]:
        """
        Create a new Google Sheet.

        Args:
            title: Title of the spreadsheet
            data: Initial data as 2D array (rows and columns)

        Returns:
            Created spreadsheet metadata
        """
        params = {"title": title}

        if data:
            params["data"] = data

        try:
            result = self._call_mcp_tool("create_sheet", params)
            return result
        except Exception as e:
            logger.error(f"Failed to create spreadsheet: {e}")
            raise

    def update_sheet(
        self, spreadsheet_id: str, range_name: str, values: List[List[Any]]
    ) -> Dict[str, Any]:
        """
        Update a Google Sheet.

        Args:
            spreadsheet_id: ID of the spreadsheet
            range_name: Range in A1 notation (e.g., 'Sheet1!A1:D10')
            values: Data as 2D array (rows and columns)

        Returns:
            Update response
        """
        params = {
            "spreadsheet_id": spreadsheet_id,
            "range": range_name,
            "values": values,
        }

        try:
            result = self._call_mcp_tool("update_sheet", params)
            return result
        except Exception as e:
            logger.error(f"Failed to update spreadsheet {spreadsheet_id}: {e}")
            raise

    def search_files(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search for files in Google Drive.

        Args:
            query: Search query
            limit: Maximum number of results

        Returns:
            List of matching files
        """
        return self.list_files(query=query, limit=limit)

    @staticmethod
    def validate_oauth_token(token_data: Dict[str, Any]) -> bool:
        """
        Validate Google OAuth token by attempting to use it.

        Args:
            token_data: OAuth token dictionary

        Returns:
            True if token is valid
        """
        try:
            client = GoogleWorkspaceClient(token_data)
            # Try to list files as a validation check
            client.list_files(limit=1)
            return True
        except Exception as e:
            logger.info(f"OAuth token validation failed: {e}")
            return False
