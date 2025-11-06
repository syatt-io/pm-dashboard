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
                f"{first_keyword}s-store",  # "beauchamps-store"
                f"{first_keyword}-api",
                f"{first_keyword}-frontend"
            ])

            # Also try variants of all keywords, not just first one
            for kw in project_keywords[1:]:
                if len(kw) >= 4:  # Only consider meaningful keywords
                    candidates.extend([
                        kw,
                        f"{kw}-store",
                        f"{kw}s"
                    ])

        # Special case for "ethel" middleware repo (shared across projects)
        candidates.append("ethel")

        logger.info(f"GitHub repo candidates for {project_key}: {candidates[:5]}")

        # Return the first candidate as best guess
        # TODO: Could call GitHub API to validate repos exist and pick best match
        return candidates[0] if candidates else None

    async def list_accessible_repos(self) -> List[str]:
        """List all repositories accessible by the GitHub App with pagination.

        Returns:
            List of repository names (without org prefix)
        """
        headers = await self._get_auth_headers()
        all_repos = []
        page = 1
        per_page = 100  # Max allowed by GitHub API

        async with httpx.AsyncClient() as client:
            try:
                while True:
                    response = await client.get(
                        f"{self.base_url}/installation/repositories",
                        headers=headers,
                        params={"per_page": per_page, "page": page},
                        timeout=10.0
                    )

                    if response.status_code == 200:
                        data = response.json()
                        repos = data.get("repositories", [])

                        if not repos:
                            # No more repos, we're done
                            break

                        repo_names = [repo["name"] for repo in repos]
                        all_repos.extend(repo_names)

                        # Check if there are more pages
                        total_count = data.get("total_count", 0)
                        if len(all_repos) >= total_count:
                            break

                        page += 1
                    else:
                        logger.warning(f"Failed to list accessible repos: {response.status_code}")
                        break

                logger.info(f"GitHub App has access to {len(all_repos)} repositories")
                logger.info(f"All accessible repos: {sorted(all_repos)}")
                return all_repos

            except Exception as e:
                logger.error(f"Error listing accessible repos: {e}")
                return []

    async def get_prs_by_date_and_state(
        self,
        project_key: str,
        project_keywords: List[str],
        repo_name: Optional[str] = None,
        days_back: int = 7
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Get PRs organized by state (merged, in_review, open) for a project.

        Args:
            project_key: Project key for auto-detecting repo
            project_keywords: Keywords for repo detection
            repo_name: Optional specific repo name (auto-detected if not provided)
            days_back: Number of days to look back

        Returns:
            Dict with keys: 'merged', 'in_review', 'open', each containing list of PRs
        """
        # Check if authentication is configured
        if self.auth_mode == "token" and not self.api_token:
            logger.warning("GitHub authentication not configured - skipping PR fetch")
            return {"merged": [], "in_review": [], "open": []}
        elif self.auth_mode == "app" and not all([self.app_id, self.private_key, self.installation_id]):
            logger.warning("GitHub App authentication incomplete - skipping PR fetch")
            return {"merged": [], "in_review": [], "open": []}

        try:
            # Auto-detect repo if not provided
            if not repo_name:
                accessible_repos = await self.list_accessible_repos()
                detected_name = self.detect_repo_name(project_key, project_keywords)
                if detected_name in accessible_repos:
                    repo_name = detected_name
                    logger.info(f"Auto-detected repo '{repo_name}' for project {project_key}")
                else:
                    logger.warning(f"Could not find matching repo for project {project_key}")
                    # Fall back to org-wide search
                    repo_name = None

            # Calculate date range
            since_date = datetime.now() - timedelta(days=days_back)
            since_iso = since_date.strftime("%Y-%m-%d")

            # Fetch PRs by state
            merged_prs = await self._fetch_prs_by_query(
                repo_name=repo_name,
                since_date=since_iso,
                additional_filters="is:pr is:merged"
            )

            # In review: open PRs with review activity
            in_review_prs = await self._fetch_prs_by_query(
                repo_name=repo_name,
                since_date=since_iso,
                additional_filters="is:pr is:open review:approved,review:changes_requested"
            )

            # Open PRs without review activity
            open_prs = await self._fetch_prs_by_query(
                repo_name=repo_name,
                since_date=since_iso,
                additional_filters="is:pr is:open -review:approved -review:changes_requested"
            )

            logger.info(f"Found {len(merged_prs)} merged, {len(in_review_prs)} in review, {len(open_prs)} open PRs")

            return {
                "merged": merged_prs,
                "in_review": in_review_prs,
                "open": open_prs
            }

        except Exception as e:
            logger.error(f"Error fetching PRs by state: {e}")
            return {"merged": [], "in_review": [], "open": []}

    async def _fetch_prs_by_query(
        self,
        repo_name: Optional[str],
        since_date: str,
        additional_filters: str
    ) -> List[Dict[str, Any]]:
        """Fetch PRs with specific query filters.

        Args:
            repo_name: Repository name (None for org-wide search)
            since_date: ISO date string for created:>= filter
            additional_filters: Additional GitHub search filters (e.g., "is:pr is:merged")

        Returns:
            List of PR dictionaries
        """
        query_parts = []

        # Add repo or org filter
        if repo_name:
            repo_filter = f"repo:{self.organization}/{repo_name}" if self.organization else f"repo:{repo_name}"
            query_parts.append(repo_filter)
        elif self.organization:
            query_parts.append(f"org:{self.organization}")

        # Add date and state filters
        query_parts.append(f"created:>={since_date}")
        query_parts.append(additional_filters)

        search_query = " ".join(query_parts)

        # Get auth headers
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
                        "per_page": 50  # Get more results for weekly recap
                    },
                    timeout=15.0
                )

                if response.status_code == 200:
                    data = response.json()
                    items = data.get("items", [])

                    prs = []
                    for item in items:
                        pr_data = {
                            "number": item.get("number"),
                            "title": item.get("title"),
                            "body": item.get("body", "")[:200] if item.get("body") else "",  # Truncate body
                            "state": item.get("state"),
                            "url": item.get("html_url"),
                            "created_at": item.get("created_at"),
                            "updated_at": item.get("updated_at"),
                            "author": item.get("user", {}).get("login") if item.get("user") else None,
                            "repo": item.get("repository_url", "").split("/")[-1] if item.get("repository_url") else ""
                        }

                        # Add merged_at if available - check if pull_request exists and has merged_at
                        pull_request = item.get("pull_request")
                        if pull_request and pull_request.get("merged_at"):
                            pr_data["merged_at"] = pull_request["merged_at"]

                        prs.append(pr_data)

                    return prs
                else:
                    logger.warning(f"GitHub PR query returned status {response.status_code}: {search_query}")
                    return []

            except Exception as e:
                logger.error(f"Error querying GitHub PRs: {e}", exc_info=True)
                return []

    async def get_prs_by_date_range(
        self,
        repo_name: str,
        start_date: str,
        end_date: str,
        state: str = 'all'
    ) -> List[Dict[str, Any]]:
        """Get PRs for a specific repo within a date range.

        Args:
            repo_name: Repository name (without org prefix)
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            state: PR state ('open', 'closed', 'all')

        Returns:
            List of PR dictionaries
        """
        # Build query
        query_parts = []

        # Add repo filter
        if self.organization:
            query_parts.append(f"repo:{self.organization}/{repo_name}")
        else:
            query_parts.append(f"repo:{repo_name}")

        # Add date range filter
        query_parts.append(f"created:{start_date}..{end_date}")

        # Add PR type filter
        query_parts.append("is:pr")

        # Add state filter if not 'all'
        if state != 'all':
            query_parts.append(f"is:{state}")

        search_query = " ".join(query_parts)

        # Get auth headers
        headers = await self._get_auth_headers()

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/search/issues",
                    headers=headers,
                    params={
                        "q": search_query,
                        "sort": "created",
                        "order": "desc",
                        "per_page": 100  # Max allowed
                    },
                    timeout=15.0
                )

                if response.status_code == 200:
                    data = response.json()
                    items = data.get("items", [])

                    prs = []
                    for item in items:
                        pr_data = {
                            "number": item.get("number"),
                            "title": item.get("title"),
                            "body": item.get("body", ""),
                            "state": item.get("state"),
                            "url": item.get("html_url"),
                            "created_at": item.get("created_at"),
                            "updated_at": item.get("updated_at"),
                            "author": item.get("user", {}).get("login") if item.get("user") else None,
                            "repo": repo_name
                        }

                        # Add merged_at if available
                        pull_request = item.get("pull_request")
                        if pull_request and pull_request.get("merged_at"):
                            pr_data["merged_at"] = pull_request["merged_at"]

                        prs.append(pr_data)

                    return prs
                else:
                    logger.warning(f"GitHub PR search returned status {response.status_code}: {search_query}")
                    return []

            except Exception as e:
                logger.error(f"Error searching GitHub PRs: {e}", exc_info=True)
                return []
