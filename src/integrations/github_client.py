"""GitHub API client for searching PRs and commits."""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import httpx
import jwt
import time

logger = logging.getLogger(__name__)


class GitHubClient:
    """Client for GitHub API v3 REST API with GitHub App support."""

    def __init__(
        self,
        api_token: str = "",
        organization: str = "",
        app_id: str = "",
        private_key: str = "",
        installation_id: str = ""
    ):
        """Initialize GitHub client.

        Supports two authentication modes:
        1. Personal Access Token (legacy):
           - api_token: GitHub personal access token
           - organization: Optional organization name

        2. GitHub App (recommended):
           - app_id: GitHub App ID
           - private_key: GitHub App private key (PEM format)
           - installation_id: Installation ID for the org
           - organization: Optional organization name

        Args:
            api_token: GitHub personal access token (if not using GitHub App)
            organization: Optional organization name to filter repos
            app_id: GitHub App ID (if using GitHub App auth)
            private_key: GitHub App private key in PEM format (if using GitHub App auth)
            installation_id: GitHub App installation ID (if using GitHub App auth)
        """
        self.organization = organization
        self.base_url = "https://api.github.com"

        # Determine auth mode
        self.auth_mode = "app" if app_id and private_key and installation_id else "token"

        if self.auth_mode == "app":
            logger.info("Using GitHub App authentication")
            self.app_id = app_id
            self.private_key = private_key
            self.installation_id = installation_id
            self.installation_token = None
            self.token_expires_at = 0
        else:
            logger.info("Using Personal Access Token authentication")
            self.api_token = api_token

        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }

    async def _get_installation_token(self) -> str:
        """Get or refresh GitHub App installation token.

        Returns:
            Installation access token
        """
        # Return cached token if still valid (with 5 min buffer)
        if self.installation_token and time.time() < (self.token_expires_at - 300):
            return self.installation_token

        # Generate JWT for GitHub App authentication
        now = int(time.time())
        payload = {
            "iat": now - 60,  # Issued at (60 seconds in the past to account for clock drift)
            "exp": now + 600,  # Expires in 10 minutes (max allowed)
            "iss": self.app_id  # GitHub App ID
        }

        # Sign JWT with private key
        jwt_token = jwt.encode(payload, self.private_key, algorithm="RS256")

        # Exchange JWT for installation access token
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/app/installations/{self.installation_id}/access_tokens",
                    headers={
                        "Authorization": f"Bearer {jwt_token}",
                        "Accept": "application/vnd.github.v3+json",
                        "X-GitHub-Api-Version": "2022-11-28"
                    },
                    timeout=10.0
                )

                if response.status_code == 201:
                    data = response.json()
                    self.installation_token = data["token"]
                    # Tokens expire in 1 hour
                    expires_at = datetime.fromisoformat(data["expires_at"].replace("Z", "+00:00"))
                    self.token_expires_at = expires_at.timestamp()
                    logger.info("Successfully obtained GitHub App installation token")
                    return self.installation_token
                else:
                    logger.error(f"Failed to get installation token: {response.status_code} - {response.text}")
                    raise Exception(f"GitHub App authentication failed: {response.status_code}")

            except Exception as e:
                logger.error(f"Error getting GitHub App installation token: {e}")
                raise

    async def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers based on auth mode.

        Returns:
            Headers dict with Authorization
        """
        headers = self.headers.copy()

        if self.auth_mode == "app":
            token = await self._get_installation_token()
            headers["Authorization"] = f"Bearer {token}"
        else:
            headers["Authorization"] = f"Bearer {self.api_token}"

        return headers

    async def search_prs_and_commits(
        self,
        query_keywords: List[str],
        repo_name: Optional[str] = None,
        days_back: int = 60
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Search for PRs and commits matching keywords.

        Args:
            query_keywords: Keywords to search for
            repo_name: Optional specific repo name (auto-detected if not provided)
            days_back: How many days back to search

        Returns:
            Dict with 'prs' and 'commits' lists
        """
        # Check if authentication is configured
        if self.auth_mode == "token" and not self.api_token:
            logger.warning("GitHub authentication not configured - skipping GitHub search")
            return {"prs": [], "commits": []}
        elif self.auth_mode == "app" and not all([self.app_id, self.private_key, self.installation_id]):
            logger.warning("GitHub App authentication incomplete - skipping GitHub search")
            return {"prs": [], "commits": []}

        # Calculate date range
        since_date = datetime.now() - timedelta(days=days_back)
        since_iso = since_date.strftime("%Y-%m-%d")

        results = {"prs": [], "commits": []}

        try:
            # Search for PRs
            prs = await self._search_pull_requests(query_keywords, repo_name, since_iso)
            results["prs"] = prs

            # Search for commits
            commits = await self._search_commits(query_keywords, repo_name, since_iso)
            results["commits"] = commits

            logger.info(f"Found {len(prs)} PRs and {len(commits)} commits from GitHub")
            return results

        except Exception as e:
            logger.error(f"Error searching GitHub: {e}")
            return {"prs": [], "commits": []}

    async def _search_pull_requests(
        self,
        query_keywords: List[str],
        repo_name: Optional[str],
        since_date: str
    ) -> List[Dict[str, Any]]:
        """Search for pull requests."""
        query_parts = []

        # Add keyword search (without OR - GitHub handles space-separated terms better)
        keyword_query = " ".join(query_keywords[:5])  # Limit to 5 keywords
        if keyword_query:
            query_parts.append(keyword_query)

        # Add repo filter
        if repo_name:
            query_parts.append(f"repo:{self.organization}/{repo_name}" if self.organization else f"repo:{repo_name}")
        elif self.organization:
            query_parts.append(f"org:{self.organization}")

        # Add type and date filters
        query_parts.append("is:pr")
        query_parts.append(f"created:>={since_date}")

        search_query = " ".join(query_parts)

        # Get auth headers (handles both token and GitHub App)
        headers = await self._get_auth_headers()

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/search/issues",
                    headers=headers,
                    params={
                        "q": search_query,
                        "sort": "updated",
                        "order": "desc",
                        "per_page": 30
                    },
                    timeout=10.0
                )

                if response.status_code == 200:
                    data = response.json()
                    items = data.get("items", [])

                    prs = []
                    for item in items:
                        prs.append({
                            "number": item.get("number"),
                            "title": item.get("title"),
                            "body": item.get("body", ""),
                            "state": item.get("state"),
                            "url": item.get("html_url"),
                            "created_at": item.get("created_at"),
                            "updated_at": item.get("updated_at"),
                            "user": item.get("user", {}).get("login"),
                            "repo": item.get("repository_url", "").split("/")[-1] if item.get("repository_url") else ""
                        })

                    return prs
                else:
                    logger.warning(f"GitHub PR search returned status {response.status_code}")
                    return []

            except Exception as e:
                logger.error(f"Error searching GitHub PRs: {e}")
                return []

    async def _search_commits(
        self,
        query_keywords: List[str],
        repo_name: Optional[str],
        since_date: str
    ) -> List[Dict[str, Any]]:
        """Search for commits."""
        query_parts = []

        # Add keyword search
        keyword_query = " ".join(query_keywords[:5])  # Limit to 5 keywords
        if keyword_query:
            query_parts.append(keyword_query)

        # Add repo filter
        if repo_name:
            query_parts.append(f"repo:{self.organization}/{repo_name}" if self.organization else f"repo:{repo_name}")
        elif self.organization:
            query_parts.append(f"org:{self.organization}")

        # Add date filter
        query_parts.append(f"committer-date:>={since_date}")

        search_query = " ".join(query_parts)

        # Get auth headers (handles both token and GitHub App)
        headers = await self._get_auth_headers()

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/search/commits",
                    headers=headers,
                    params={
                        "q": search_query,
                        "sort": "committer-date",
                        "order": "desc",
                        "per_page": 30
                    },
                    timeout=10.0
                )

                if response.status_code == 200:
                    data = response.json()
                    items = data.get("items", [])

                    commits = []
                    for item in items:
                        commit_data = item.get("commit", {})
                        commits.append({
                            "sha": item.get("sha"),
                            "message": commit_data.get("message", ""),
                            "author": commit_data.get("author", {}).get("name"),
                            "date": commit_data.get("author", {}).get("date"),
                            "url": item.get("html_url"),
                            "repo": item.get("repository", {}).get("name", "")
                        })

                    return commits
                else:
                    logger.warning(f"GitHub commit search returned status {response.status_code}")
                    return []

            except Exception as e:
                logger.error(f"Error searching GitHub commits: {e}")
                return []

    def detect_repo_name(self, project_key: str, project_keywords: List[str]) -> Optional[str]:
        """Auto-detect GitHub repo name from project keywords.

        Args:
            project_key: Jira project key (e.g., "BEAU")
            project_keywords: Project-related keywords (e.g., ["beauchamp", "baby", "store"])

        Returns:
            Detected repo name or None
        """
        # Common patterns:
        # - beauchamp -> beauchamp-store, beauchamps-baby-store
        # - BEAU -> beau, beauchamp
        # - subscriptions -> subscriptions, subs

        # Try project key variants
        candidates = [
            project_key.lower(),  # "beau"
            f"{project_key.lower()}-api",  # "beau-api"
            f"{project_key.lower()}-frontend",  # "beau-frontend"
        ]

        # Try first keyword variants
        if project_keywords:
            first_keyword = project_keywords[0]
            candidates.extend([
                first_keyword,  # "beauchamp"
                f"{first_keyword}-store",  # "beauchamp-store"
                f"{first_keyword}s",  # "beauchamps"
                f"{first_keyword}-api",
                f"{first_keyword}-frontend"
            ])

        # Special case for "ethel" middleware repo (shared across projects)
        candidates.append("ethel")

        logger.info(f"GitHub repo candidates for {project_key}: {candidates[:5]}")

        # For now, return the first keyword as best guess
        # In production, we could call GitHub API to validate repos exist
        return project_keywords[0] if project_keywords else project_key.lower()
