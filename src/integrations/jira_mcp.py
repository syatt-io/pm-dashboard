"""Jira integration using Model Context Protocol (MCP)."""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import asyncio
import httpx
from dataclasses import dataclass, asdict


logger = logging.getLogger(__name__)


@dataclass
class JiraTicket:
    """Jira ticket structure."""
    summary: str
    description: str
    issue_type: str = "Task"
    priority: str = "Medium"
    project_key: Optional[str] = None
    assignee: Optional[str] = None
    due_date: Optional[str] = None
    labels: Optional[List[str]] = None
    components: Optional[List[str]] = None
    story_points: Optional[int] = None


class JiraMCPClient:
    """Client for interacting with Jira through MCP server."""

    def __init__(self, mcp_server_url: str = "http://localhost:3000",
                 jira_url: str = None, username: str = None, api_token: str = None):
        """Initialize Jira MCP client.

        Args:
            mcp_server_url: URL of the MCP server (running in Docker)
            jira_url: Jira instance URL (for direct API calls if needed)
            username: Jira username
            api_token: Jira API token
        """
        self.mcp_server_url = mcp_server_url
        self.jira_url = jira_url
        self.username = username
        self.api_token = api_token
        self.client = httpx.AsyncClient(timeout=30.0)

    async def create_ticket(self, ticket: JiraTicket) -> Dict[str, Any]:
        """Create a new Jira ticket via MCP."""
        try:
            # MCP request format
            mcp_request = {
                "method": "jira/createIssue",
                "params": {
                    "project": ticket.project_key,
                    "summary": ticket.summary,
                    "description": ticket.description,
                    "issueType": ticket.issue_type,
                    "priority": ticket.priority,
                    "assignee": ticket.assignee,
                    "dueDate": ticket.due_date,
                    "labels": ticket.labels or [],
                    "components": ticket.components or []
                }
            }

            response = await self.client.post(
                f"{self.mcp_server_url}/mcp",
                json=mcp_request,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()

            result = response.json()
            if result.get("success"):
                logger.info(f"Created Jira ticket: {result.get('key')}")
                return result
            else:
                logger.error(f"Failed to create ticket: {result.get('error')}")
                return {"success": False, "error": result.get("error")}

        except Exception as e:
            logger.error(f"Error creating Jira ticket: {e}")
            return {"success": False, "error": str(e)}

    async def update_ticket(self, ticket_key: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing Jira ticket."""
        try:
            mcp_request = {
                "method": "jira/updateIssue",
                "params": {
                    "issueKey": ticket_key,
                    "updates": updates
                }
            }

            response = await self.client.post(
                f"{self.mcp_server_url}/mcp",
                json=mcp_request,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()

            result = response.json()
            if result.get("success"):
                logger.info(f"Updated Jira ticket: {ticket_key}")
            return result

        except Exception as e:
            logger.error(f"Error updating ticket {ticket_key}: {e}")
            return {"success": False, "error": str(e)}

    async def get_ticket(self, ticket_key: str) -> Dict[str, Any]:
        """Get ticket details."""
        try:
            mcp_request = {
                "method": "jira/getIssue",
                "params": {
                    "issueKey": ticket_key
                }
            }

            response = await self.client.post(
                f"{self.mcp_server_url}/mcp",
                json=mcp_request,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error(f"Error fetching ticket {ticket_key}: {e}")
            return {"success": False, "error": str(e)}

    async def search_tickets(self, jql: str, max_results: int = 50, expand_comments: bool = False, start_at: int = 0) -> List[Dict[str, Any]]:
        """Search tickets using JQL.

        Args:
            jql: JQL query string
            max_results: Maximum number of results to return
            expand_comments: If True, fetch and include comments for each issue
            start_at: Starting index for pagination (0-based)

        Returns:
            List of issue dictionaries (with comments in fields if expand_comments=True)
        """
        try:
            # Try direct Jira API call first (multi-word keywords filtered out at JQL build time)
            if self.jira_url and self.username and self.api_token:
                import base64
                auth_string = base64.b64encode(f"{self.username}:{self.api_token}".encode()).decode()

                # Build params for /search/jql endpoint
                # This endpoint returns minimal data, so we need to fetch full issue details after
                params = {
                    "jql": jql,
                    "maxResults": max_results,
                    "startAt": start_at
                }

                # Step 1: Get issue IDs using /search/jql endpoint
                response = await self.client.get(
                    f"{self.jira_url}/rest/api/3/search/jql",
                    params=params,
                    headers={
                        "Authorization": f"Basic {auth_string}",
                        "Accept": "application/json"
                    }
                )
                response.raise_for_status()

                search_result = response.json()
                issue_ids = [issue.get('id') for issue in search_result.get('issues', [])]

                if not issue_ids:
                    return []

                # Step 2: Fetch full issue details for each ID using /issue endpoint
                # IMPORTANT: Increased rate limit delays and better error handling
                import asyncio

                failed_issues = []  # Track failed fetches

                async def fetch_issue(issue_id: str, index: int, total: int):
                    try:
                        # Add delay between requests (0.1s = 10 requests/second to be safer)
                        if index > 0:
                            await asyncio.sleep(0.1)

                        issue_response = await self.client.get(
                            f"{self.jira_url}/rest/api/3/issue/{issue_id}",
                            params={
                                "fields": "summary,description,status,priority,assignee,reporter,created,updated,issuetype,project,key,parent"
                            },
                            headers={
                                "Authorization": f"Basic {auth_string}",
                                "Accept": "application/json"
                            }
                        )
                        issue_response.raise_for_status()
                        return issue_response.json()
                    except Exception as e:
                        logger.error(f"Failed to fetch issue {issue_id}: {e}")
                        failed_issues.append(issue_id)
                        return None

                # Fetch issues with rate limiting - process in smaller batches
                issues = []
                batch_size = 5  # Reduced to 5 issues at a time to avoid rate limiting
                for i in range(0, len(issue_ids), batch_size):
                    batch_ids = issue_ids[i:i+batch_size]
                    batch_results = await asyncio.gather(*[
                        fetch_issue(issue_id, idx, len(issue_ids))
                        for idx, issue_id in enumerate(batch_ids)
                    ])
                    issues.extend([issue for issue in batch_results if issue is not None])

                    # Add longer delay between batches
                    if i + batch_size < len(issue_ids):
                        await asyncio.sleep(1.0)

                # Log if any issues failed
                if failed_issues:
                    logger.warning(f"Failed to fetch {len(failed_issues)}/{len(issue_ids)} issues. IDs: {failed_issues[:10]}")

                # Create result dict that matches the original structure
                result = {"issues": issues}

                # If comments requested, fetch them separately (Jira API requires separate calls)
                issues = result.get("issues", [])
                if expand_comments and issues:
                    # Fetch comments for each issue
                    for issue in issues:
                        issue_key = issue.get("key")
                        try:
                            comments_response = await self.client.get(
                                f"{self.jira_url}/rest/api/3/issue/{issue_key}/comment",
                                headers={
                                    "Authorization": f"Basic {auth_string}",
                                    "Accept": "application/json"
                                }
                            )
                            comments_response.raise_for_status()
                            comments_data = comments_response.json()

                            # Add comments to issue fields
                            if "fields" not in issue:
                                issue["fields"] = {}
                            issue["fields"]["comments"] = comments_data.get("comments", [])
                        except Exception as e:
                            logger.warning(f"Error fetching comments for {issue_key}: {e}")
                            if "fields" not in issue:
                                issue["fields"] = {}
                            issue["fields"]["comments"] = []

                logger.info(f"Retrieved {len(issues)} tickets via direct API for JQL: {jql}{' with comments' if expand_comments else ''}")
                return issues

            # Fallback to MCP
            mcp_request = {
                "method": "jira/searchIssues",
                "params": {
                    "jql": jql,
                    "maxResults": max_results
                }
            }

            response = await self.client.post(
                f"{self.mcp_server_url}/mcp",
                json=mcp_request,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()

            result = response.json()
            return result.get("issues", [])

        except Exception as e:
            logger.error(f"Error searching tickets: {e}")
            return []

    async def search_issues(self, jql: str, max_results: int = 50, expand_comments: bool = False, start_at: int = 0) -> Dict[str, Any]:
        """Alias for search_tickets that returns result in dict format with 'issues' key.

        This maintains backward compatibility with existing code.
        """
        issues = await self.search_tickets(jql, max_results, expand_comments, start_at)
        return {"issues": issues}

    async def add_comment(self, ticket_key: str, comment: str) -> Dict[str, Any]:
        """Add a comment to a ticket."""
        try:
            mcp_request = {
                "method": "jira/addComment",
                "params": {
                    "issueKey": ticket_key,
                    "body": comment
                }
            }

            response = await self.client.post(
                f"{self.mcp_server_url}/mcp",
                json=mcp_request,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error(f"Error adding comment to {ticket_key}: {e}")
            return {"success": False, "error": str(e)}

    async def transition_ticket(self, ticket_key: str, transition_name: str) -> Dict[str, Any]:
        """Transition a ticket to a new status."""
        try:
            mcp_request = {
                "method": "jira/transitionIssue",
                "params": {
                    "issueKey": ticket_key,
                    "transitionName": transition_name
                }
            }

            response = await self.client.post(
                f"{self.mcp_server_url}/mcp",
                json=mcp_request,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error(f"Error transitioning ticket {ticket_key}: {e}")
            return {"success": False, "error": str(e)}

    async def get_overdue_tickets(self, project_key: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get overdue tickets."""
        jql = f"duedate < now() AND status not in (Done, Closed, Resolved)"
        if project_key:
            jql = f"project = {project_key} AND {jql}"

        return await self.search_tickets(jql)

    async def get_tickets_due_soon(self, days: int = 3, project_key: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get tickets due within specified days."""
        jql = f"duedate >= now() AND duedate <= {days}d AND status not in (Done, Closed, Resolved)"
        if project_key:
            jql = f"project = {project_key} AND {jql}"

        return await self.search_tickets(jql)

    async def create_tickets_batch(self, tickets: List[JiraTicket]) -> List[Dict[str, Any]]:
        """Create multiple tickets in batch."""
        results = []
        for ticket in tickets:
            result = await self.create_ticket(ticket)
            results.append(result)
            # Small delay to avoid rate limiting
            await asyncio.sleep(0.5)
        return results

    async def get_projects(self) -> List[Dict[str, Any]]:
        """Get all accessible Jira projects."""
        try:
            # Try direct Jira API call first
            if self.jira_url and self.username and self.api_token:
                import base64
                logger.info(f"Attempting to fetch projects from Jira API: {self.jira_url}")
                logger.info(f"Using username: {self.username}")

                auth_string = base64.b64encode(f"{self.username}:{self.api_token}".encode()).decode()

                response = await self.client.get(
                    f"{self.jira_url}/rest/api/3/project",
                    headers={
                        "Authorization": f"Basic {auth_string}",
                        "Accept": "application/json"
                    }
                )

                logger.info(f"Jira API response status: {response.status_code}")
                response.raise_for_status()

                projects = response.json()
                logger.info(f"Retrieved {len(projects)} Jira projects via direct API")
                return projects

            # Fallback to MCP
            logger.warning("Jira credentials not configured for direct API, trying MCP fallback")
            mcp_request = {
                "method": "jira/getProjects",
                "params": {}
            }

            response = await self.client.post(
                f"{self.mcp_server_url}/mcp",
                json=mcp_request,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()

            result = response.json()
            if result.get("success"):
                projects = result.get("projects", [])
                logger.info(f"Retrieved {len(projects)} Jira projects via MCP")
                return projects
            else:
                logger.error(f"Failed to get projects via MCP: {result.get('error')}")
                return []

        except Exception as e:
            import traceback
            logger.error(f"Error fetching Jira projects: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return []

    async def get_issue_types(self, project_key: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get available issue types for a project."""
        try:
            # Try direct Jira API call first
            if self.jira_url and self.username and self.api_token:
                import base64
                auth_string = base64.b64encode(f"{self.username}:{self.api_token}".encode()).decode()

                url = f"{self.jira_url}/rest/api/3/issuetype"
                # Note: For now, return all issue types regardless of project
                # Project-specific filtering can be done on the frontend if needed

                response = await self.client.get(
                    url,
                    headers={
                        "Authorization": f"Basic {auth_string}",
                        "Accept": "application/json"
                    }
                )
                response.raise_for_status()

                issue_types = response.json()
                logger.info(f"Retrieved {len(issue_types)} issue types via direct API")
                return issue_types

            # Fallback to MCP
            mcp_request = {
                "method": "jira/getIssueTypes",
                "params": {}
            }

            if project_key:
                mcp_request["params"]["projectKey"] = project_key

            response = await self.client.post(
                f"{self.mcp_server_url}/mcp",
                json=mcp_request,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()

            result = response.json()
            if result.get("success"):
                issue_types = result.get("issueTypes", [])
                logger.info(f"Retrieved {len(issue_types)} issue types via MCP")
                return issue_types
            else:
                logger.error(f"Failed to get issue types: {result.get('error')}")
                return []

        except Exception as e:
            logger.error(f"Error fetching issue types: {e}")
            return []

    async def get_users(self, project_key: Optional[str] = None, max_results: int = 200) -> List[Dict[str, Any]]:
        """Get users that can be assigned to issues."""
        try:
            # Try direct Jira API call first
            if self.jira_url and self.username and self.api_token:
                import base64
                auth_string = base64.b64encode(f"{self.username}:{self.api_token}".encode()).decode()

                if project_key:
                    # For project-specific users, use the multiProjectSearch endpoint
                    url = f"{self.jira_url}/rest/api/3/user/assignable/multiProjectSearch?projectKeys={project_key}&maxResults={max_results}"
                else:
                    # For all users, try the people search endpoint with a minimal query
                    url = f"{self.jira_url}/rest/api/3/user/search?query=.&maxResults={max_results}"

                response = await self.client.get(
                    url,
                    headers={
                        "Authorization": f"Basic {auth_string}",
                        "Accept": "application/json"
                    }
                )
                response.raise_for_status()

                users = response.json()
                # Sort users by display name
                users.sort(key=lambda u: (u.get('displayName') or u.get('name') or u.get('emailAddress') or '').lower())
                logger.info(f"Retrieved {len(users)} assignable users via direct API")
                return users

            # Fallback to MCP
            mcp_request = {
                "method": "jira/getAssignableUsers",
                "params": {
                    "maxResults": max_results
                }
            }

            if project_key:
                mcp_request["params"]["projectKey"] = project_key

            response = await self.client.post(
                f"{self.mcp_server_url}/mcp",
                json=mcp_request,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()

            result = response.json()
            if result.get("success"):
                users = result.get("users", [])
                logger.info(f"Retrieved {len(users)} assignable users via MCP")
                return users
            else:
                logger.error(f"Failed to get users: {result.get('error')}")
                return []

        except Exception as e:
            logger.error(f"Error fetching assignable users: {e}")
            return []

    async def search_users(self, query: str, project_key: Optional[str] = None, max_results: int = 20) -> List[Dict[str, Any]]:
        """Search users by query string for autocomplete."""
        try:
            # Try direct Jira API call first
            if self.jira_url and self.username and self.api_token:
                import base64
                auth_string = base64.b64encode(f"{self.username}:{self.api_token}".encode()).decode()

                if project_key:
                    # For project-specific users, use the multiProjectSearch endpoint
                    url = f"{self.jira_url}/rest/api/3/user/assignable/multiProjectSearch?projectKeys={project_key}&query={query}&maxResults={max_results}"
                else:
                    # For all users, use the search endpoint with the query
                    url = f"{self.jira_url}/rest/api/3/user/search?query={query}&maxResults={max_results}"

                response = await self.client.get(
                    url,
                    headers={
                        "Authorization": f"Basic {auth_string}",
                        "Accept": "application/json"
                    }
                )
                response.raise_for_status()

                users = response.json()
                # Sort users by display name
                users.sort(key=lambda u: (u.get('displayName') or u.get('name') or u.get('emailAddress') or '').lower())
                logger.info(f"Retrieved {len(users)} users for query '{query}' via direct API")
                return users

            # Fallback to MCP
            mcp_request = {
                "method": "jira/searchUsers",
                "params": {
                    "query": query,
                    "maxResults": max_results
                }
            }

            if project_key:
                mcp_request["params"]["projectKey"] = project_key

            response = await self.client.post(
                f"{self.mcp_server_url}/mcp",
                json=mcp_request,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()

            result = response.json()
            if result.get("success"):
                users = result.get("users", [])
                logger.info(f"Retrieved {len(users)} users for query '{query}' via MCP")
                return users
            else:
                logger.error(f"Failed to search users: {result.get('error')}")
                return []

        except Exception as e:
            logger.error(f"Error searching users: {e}")
            return []

    async def get_priorities(self) -> List[Dict[str, Any]]:
        """Get available priorities."""
        try:
            # Try direct Jira API call first
            if self.jira_url and self.username and self.api_token:
                import base64
                auth_string = base64.b64encode(f"{self.username}:{self.api_token}".encode()).decode()

                response = await self.client.get(
                    f"{self.jira_url}/rest/api/3/priority",
                    headers={
                        "Authorization": f"Basic {auth_string}",
                        "Accept": "application/json"
                    }
                )
                response.raise_for_status()

                priorities = response.json()
                logger.info(f"Retrieved {len(priorities)} priorities via direct API")
                return priorities

            # Fallback to MCP
            mcp_request = {
                "method": "jira/getPriorities",
                "params": {}
            }

            response = await self.client.post(
                f"{self.mcp_server_url}/mcp",
                json=mcp_request,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()

            result = response.json()
            if result.get("success"):
                priorities = result.get("priorities", [])
                logger.info(f"Retrieved {len(priorities)} priorities via MCP")
                return priorities
            else:
                logger.error(f"Failed to get priorities: {result.get('error')}")
                return []

        except Exception as e:
            logger.error(f"Error fetching priorities: {e}")
            return []

    async def get_project_metadata(self, project_key: str) -> Dict[str, Any]:
        """Get comprehensive project metadata including users, issue types, etc."""
        try:
            # Fetch all metadata in parallel
            projects_task = self.get_projects()
            issue_types_task = self.get_issue_types(project_key)
            users_task = self.get_users(project_key)
            priorities_task = self.get_priorities()

            projects, issue_types, users, priorities = await asyncio.gather(
                projects_task, issue_types_task, users_task, priorities_task,
                return_exceptions=True
            )

            # Find the specific project
            project = None
            if isinstance(projects, list):
                project = next((p for p in projects if p.get("key") == project_key), None)

            metadata = {
                "project": project,
                "issue_types": issue_types if isinstance(issue_types, list) else [],
                "users": users if isinstance(users, list) else [],
                "priorities": priorities if isinstance(priorities, list) else []
            }

            logger.info(f"Retrieved metadata for project {project_key}")
            return metadata

        except Exception as e:
            logger.error(f"Error fetching project metadata: {e}")
            return {
                "project": None,
                "issue_types": [],
                "users": [],
                "priorities": []
            }

    async def get_ticket_with_changelog(self, ticket_key: str) -> Optional[Dict[str, Any]]:
        """Get a ticket with its change history."""
        try:
            # Try direct Jira API call first
            if self.jira_url and self.username and self.api_token:
                import base64
                auth_string = base64.b64encode(f"{self.username}:{self.api_token}".encode()).decode()

                response = await self.client.get(
                    f"{self.jira_url}/rest/api/3/issue/{ticket_key}?expand=changelog",
                    headers={
                        "Authorization": f"Basic {auth_string}",
                        "Accept": "application/json"
                    }
                )
                response.raise_for_status()

                ticket = response.json()
                logger.debug(f"Retrieved ticket {ticket_key} with changelog via direct API")
                return ticket

            # Fallback to MCP
            mcp_request = {
                "method": "jira/getIssue",
                "params": {
                    "issueKey": ticket_key,
                    "expand": ["changelog"]
                }
            }

            response = await self.client.post(
                f"{self.mcp_server_url}/mcp",
                json=mcp_request,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()

            result = response.json()
            if result.get("success"):
                ticket = result.get("issue")
                logger.debug(f"Retrieved ticket {ticket_key} with changelog via MCP")
                return ticket
            else:
                logger.error(f"Failed to get ticket with changelog: {result.get('error')}")
                return None

        except Exception as e:
            logger.error(f"Error fetching ticket {ticket_key} with changelog: {e}")
            return None

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.aclose()