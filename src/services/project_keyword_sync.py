"""Auto-sync Jira project names to keywords for intelligent search project detection."""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
import re

logger = logging.getLogger(__name__)


class ProjectKeywordSync:
    """Syncs Jira project information to build keyword mappings for search."""

    def __init__(self):
        """Initialize the sync service."""
        pass

    async def sync_jira_projects(self) -> Dict[str, Any]:
        """Fetch all Jira projects and populate project_keywords table.

        This enables automatic project detection in queries like:
        - "beauchamp cart issue" -> detects Beauchamp project (BC or BCHP)
        - "subscriptions bug" -> detects Subscriptions project (SUBS)

        Returns:
            Dict with sync stats
        """
        from src.integrations.jira_mcp import JiraMCPClient
        from config.settings import settings
        from src.utils.database import get_engine
        from sqlalchemy import text

        try:
            # Initialize Jira client
            jira_client = JiraMCPClient(
                jira_url=settings.jira.url,
                username=settings.jira.username,
                api_token=settings.jira.api_token
            )

            # Fetch all projects
            logger.info("Fetching Jira projects for keyword mapping...")
            projects_response = await jira_client.get_projects()
            projects = projects_response.get('projects', [])

            if not projects:
                logger.warning("No Jira projects found")
                return {"success": False, "error": "No projects found"}

            logger.info(f"Found {len(projects)} Jira projects")

            # Build keyword mappings
            keywords_to_insert = []

            for project in projects:
                project_key = project.get('key', '')
                project_name = project.get('name', '')

                if not project_key:
                    continue

                # Extract keywords from project name
                # Example: "Beauchamp's Baby Store" -> ["beauchamp", "baby", "store"]
                keywords = self._extract_keywords_from_name(project_name)

                # Add the project key itself as a keyword (e.g., "BC" or "SUBS")
                keywords.add(project_key.lower())

                # Add each keyword
                for keyword in keywords:
                    keywords_to_insert.append({
                        'project_key': project_key,
                        'keyword': keyword.lower(),
                        'source': 'jira'
                    })

            logger.info(f"Extracted {len(keywords_to_insert)} keyword mappings from {len(projects)} projects")

            # Insert into database
            engine = get_engine()
            with engine.connect() as conn:
                # Clear existing Jira-sourced keywords (to handle renamed/deleted projects)
                conn.execute(text("DELETE FROM project_keywords WHERE source = 'jira'"))

                # Insert new keywords
                for kw_data in keywords_to_insert:
                    try:
                        conn.execute(
                            text("""
                                INSERT OR IGNORE INTO project_keywords (project_key, keyword, source)
                                VALUES (:project_key, :keyword, :source)
                            """),
                            kw_data
                        )
                    except Exception as e:
                        logger.error(f"Error inserting keyword {kw_data}: {e}")

                # Update sync timestamp
                conn.execute(
                    text("""
                        INSERT OR REPLACE INTO project_keywords_sync (id, last_synced)
                        VALUES (1, :timestamp)
                    """),
                    {"timestamp": datetime.now().isoformat()}
                )

                conn.commit()

            logger.info(f"✅ Successfully synced {len(keywords_to_insert)} keywords from {len(projects)} Jira projects")

            return {
                "success": True,
                "projects_synced": len(projects),
                "keywords_created": len(keywords_to_insert),
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error syncing Jira projects: {e}")
            return {"success": False, "error": str(e)}

    def _extract_keywords_from_name(self, project_name: str) -> set:
        """Extract meaningful keywords from project name.

        Args:
            project_name: Project name like "Beauchamp's Baby Store"

        Returns:
            Set of keywords like {"beauchamp", "baby", "store"}
        """
        # Remove possessive apostrophes and special chars
        cleaned = re.sub(r"['']s\b", "", project_name)  # "Beauchamp's" -> "Beauchamp"
        cleaned = re.sub(r"[^\w\s]", " ", cleaned)  # Remove punctuation

        # Split into words and filter
        words = cleaned.lower().split()

        # Filter out common words
        stop_words = {
            'the', 'and', 'or', 'for', 'from', 'with', 'about', 'at', 'by',
            'in', 'on', 'to', 'of', 'a', 'an', 'as', 'is', 'was', 'are',
            'project', 'app', 'application', 'system'
        }

        # Keep words that are at least 3 chars and not stop words
        keywords = {
            word for word in words
            if len(word) >= 3 and word not in stop_words
        }

        return keywords

    async def should_sync(self) -> bool:
        """Check if we should re-sync (once per day).

        Returns:
            True if sync is needed (never synced or > 24 hours old)
        """
        from src.utils.database import get_engine
        from sqlalchemy import text

        try:
            engine = get_engine()
            with engine.connect() as conn:
                result = conn.execute(
                    text("SELECT last_synced FROM project_keywords_sync WHERE id = 1")
                )
                row = result.fetchone()

                if not row or not row[0]:
                    logger.info("No previous sync found - sync needed")
                    return True

                last_synced = datetime.fromisoformat(row[0])
                age = datetime.now() - last_synced

                if age > timedelta(hours=24):
                    logger.info(f"Last sync was {age.total_seconds() / 3600:.1f} hours ago - sync needed")
                    return True

                logger.info(f"Last sync was {age.total_seconds() / 3600:.1f} hours ago - no sync needed")
                return False

        except Exception as e:
            logger.error(f"Error checking sync status: {e}")
            return True  # Sync on error to be safe

    async def sync_if_needed(self) -> Dict[str, Any]:
        """Sync projects only if needed (daily).

        Returns:
            Dict with sync results or skip reason
        """
        if await self.should_sync():
            return await self.sync_jira_projects()
        else:
            return {
                "success": True,
                "skipped": True,
                "reason": "Already synced within 24 hours"
            }
