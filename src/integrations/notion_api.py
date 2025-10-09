"""Simple Notion API client for vector ingestion (no MCP dependency)."""

import logging
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class NotionAPIClient:
    """Direct Notion API client for fetching pages and databases."""

    def __init__(self, api_key: str):
        """Initialize Notion API client.

        Args:
            api_key: Notion Integration token (starts with 'secret_')
        """
        if not api_key or not api_key.strip():
            raise ValueError("Notion API key is required")

        self.api_key = api_key.strip()
        self.base_url = "https://api.notion.com/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28"
        }

    def _make_request(self, method: str, endpoint: str, data: Dict = None) -> Dict[str, Any]:
        """Make HTTP request to Notion API."""
        url = f"{self.base_url}/{endpoint}"

        try:
            if method == "GET":
                response = requests.get(url, headers=self.headers, params=data)
            elif method == "POST":
                response = requests.post(url, headers=self.headers, json=data)
            else:
                raise ValueError(f"Unsupported method: {method}")

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"Notion API request failed: {e}")
            raise

    def search(
        self,
        query: str = "",
        filter_type: str = None,
        page_size: int = 100,
        start_cursor: str = None
    ) -> Dict[str, Any]:
        """Search Notion workspace.

        Args:
            query: Search query (optional)
            filter_type: Filter by 'page' or 'database'
            page_size: Number of results per page (max 100)
            start_cursor: Pagination cursor

        Returns:
            Search results with pages/databases
        """
        data = {
            "page_size": min(page_size, 100)
        }

        if query:
            data["query"] = query

        if filter_type:
            data["filter"] = {"property": "object", "value": filter_type}

        if start_cursor:
            data["start_cursor"] = start_cursor

        return self._make_request("POST", "search", data)

    def get_all_pages(self, days_back: int = 90) -> List[Dict[str, Any]]:
        """Fetch all pages updated in the last N days with pagination.

        Args:
            days_back: Number of days to look back

        Returns:
            List of all pages
        """
        all_pages = []
        has_more = True
        start_cursor = None
        # Make cutoff_date timezone-aware to match Notion API timestamps
        from datetime import timezone
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)

        while has_more:
            result = self.search(
                filter_type="page",
                page_size=100,
                start_cursor=start_cursor
            )

            pages = result.get("results", [])

            # Filter by last_edited_time
            for page in pages:
                try:
                    last_edited = page.get("last_edited_time", "")
                    if last_edited:
                        edited_date = datetime.fromisoformat(last_edited.replace("Z", "+00:00"))
                        if edited_date >= cutoff_date:
                            all_pages.append(page)
                except Exception as e:
                    logger.warning(f"Error parsing page date: {e}")
                    all_pages.append(page)  # Include if we can't parse date

            has_more = result.get("has_more", False)
            start_cursor = result.get("next_cursor")

        logger.info(f"Found {len(all_pages)} Notion pages updated in last {days_back} days")
        return all_pages

    def get_page(self, page_id: str) -> Dict[str, Any]:
        """Get page metadata by ID."""
        return self._make_request("GET", f"pages/{page_id}")

    def get_page_blocks(
        self,
        page_id: str,
        page_size: int = 100,
        start_cursor: str = None
    ) -> Dict[str, Any]:
        """Get page content blocks.

        Args:
            page_id: Page ID
            page_size: Number of blocks per page
            start_cursor: Pagination cursor

        Returns:
            Page blocks
        """
        params = {"page_size": min(page_size, 100)}
        if start_cursor:
            params["start_cursor"] = start_cursor

        return self._make_request("GET", f"blocks/{page_id}/children", params)

    def get_full_page_content(self, page_id: str) -> str:
        """Get full page content as text.

        Args:
            page_id: Page ID

        Returns:
            Page content as plain text
        """
        content_parts = []
        has_more = True
        start_cursor = None

        while has_more:
            result = self.get_page_blocks(page_id, start_cursor=start_cursor)
            blocks = result.get("results", [])

            for block in blocks:
                block_text = self._extract_block_text(block)
                if block_text:
                    content_parts.append(block_text)

            has_more = result.get("has_more", False)
            start_cursor = result.get("next_cursor")

        return "\n\n".join(content_parts)

    def _extract_block_text(self, block: Dict[str, Any]) -> str:
        """Extract text from a Notion block."""
        block_type = block.get("type", "")
        block_data = block.get(block_type, {})

        # Handle rich text arrays
        if "rich_text" in block_data:
            text_parts = []
            for text_obj in block_data["rich_text"]:
                text_parts.append(text_obj.get("plain_text", ""))
            return "".join(text_parts)

        # Handle other block types
        if block_type == "child_page":
            return f"[Child Page: {block_data.get('title', '')}]"

        return ""

    def get_page_title(self, page: Dict[str, Any]) -> str:
        """Extract title from page metadata."""
        properties = page.get("properties", {})

        # Try to find title property
        for prop_name, prop_data in properties.items():
            if prop_data.get("type") == "title":
                title_arr = prop_data.get("title", [])
                if title_arr:
                    return title_arr[0].get("plain_text", "Untitled")

        return "Untitled"
