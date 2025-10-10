"""Vector ingestion service for Pinecone - handles embedding and upserting content from all sources."""

import logging
import hashlib
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class VectorDocument:
    """A document to be ingested into the vector database."""
    id: str  # Unique identifier
    source: str  # slack, fireflies, jira, notion
    title: str
    content: str
    metadata: Dict[str, Any]  # Source-specific metadata including permissions
    embedding: Optional[List[float]] = None


class VectorIngestService:
    """Service for ingesting content into Pinecone vector database."""

    def __init__(self):
        """Initialize the vector ingestion service."""
        from config.settings import settings
        from openai import OpenAI

        self.settings = settings
        self.openai_client = OpenAI(api_key=settings.ai.api_key)
        self.pinecone_index = None
        self._init_pinecone()

    def _init_pinecone(self):
        """Initialize Pinecone client and index."""
        try:
            from pinecone import Pinecone, ServerlessSpec

            if not self.settings.pinecone.api_key:
                logger.warning("Pinecone API key not configured - vector search disabled")
                return

            # Initialize Pinecone
            pc = Pinecone(api_key=self.settings.pinecone.api_key)

            index_name = self.settings.pinecone.index_name

            # Check if index exists, create if not
            existing_indexes = pc.list_indexes()
            index_exists = any(idx['name'] == index_name for idx in existing_indexes)

            if not index_exists:
                logger.info(f"Creating Pinecone index: {index_name}")
                pc.create_index(
                    name=index_name,
                    dimension=self.settings.pinecone.dimension,
                    metric=self.settings.pinecone.metric,
                    spec=ServerlessSpec(
                        cloud='aws',
                        region=self.settings.pinecone.environment
                    )
                )

            # Connect to index
            self.pinecone_index = pc.Index(index_name)
            logger.info(f"✅ Connected to Pinecone index: {index_name}")

        except Exception as e:
            logger.error(f"Failed to initialize Pinecone: {e}")
            self.pinecone_index = None

    def get_embedding(self, text: str) -> Optional[List[float]]:
        """Get OpenAI embedding for text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector or None if error
        """
        if not text or not text.strip():
            return None

        # Truncate to ~8000 chars (OpenAI limit is ~8191 tokens)
        text = text[:8000]

        try:
            response = self.openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=text
            )
            return response.data[0].embedding

        except Exception as e:
            logger.error(f"Error getting embedding: {e}")
            return None

    def upsert_documents(self, documents: List[VectorDocument], batch_size: int = 100) -> int:
        """Upsert documents into Pinecone in batches.

        Args:
            documents: List of documents to upsert
            batch_size: Number of documents per batch

        Returns:
            Number of successfully upserted documents
        """
        if not self.pinecone_index:
            logger.error("Pinecone index not initialized")
            return 0

        # Generate embeddings for documents that don't have them
        for doc in documents:
            if not doc.embedding:
                doc.embedding = self.get_embedding(doc.content)
                if not doc.embedding:
                    logger.warning(f"Skipping document {doc.id} - failed to generate embedding")

        # Filter out documents without embeddings
        valid_docs = [doc for doc in documents if doc.embedding]

        if not valid_docs:
            logger.warning("No valid documents to upsert (all failed embedding generation)")
            return 0

        # Upsert in batches
        upserted = 0
        for i in range(0, len(valid_docs), batch_size):
            batch = valid_docs[i:i + batch_size]

            try:
                # Format for Pinecone
                vectors = []
                for doc in batch:
                    vectors.append({
                        "id": doc.id,
                        "values": doc.embedding,
                        "metadata": {
                            **doc.metadata,
                            "source": doc.source,
                            "title": doc.title[:500],  # Truncate title
                            "content_preview": doc.content[:1000]  # Store preview for display
                        }
                    })

                # Upsert to Pinecone
                self.pinecone_index.upsert(vectors=vectors)
                upserted += len(vectors)
                logger.info(f"✅ Upserted batch of {len(vectors)} vectors ({upserted}/{len(valid_docs)} total)")

            except Exception as e:
                logger.error(f"Error upserting batch: {e}")
                continue

        logger.info(f"✅ Successfully upserted {upserted}/{len(documents)} documents to Pinecone")
        return upserted

    def ingest_slack_messages(
        self,
        messages: List[Dict[str, Any]],
        channel_id: str,
        channel_name: str,
        is_private: bool = False
    ) -> int:
        """Ingest Slack messages into vector database.

        Per requirements: No permissions needed for Slack - all content accessible to all users.

        Args:
            messages: List of Slack message dicts
            channel_id: Slack channel ID
            channel_name: Channel name
            is_private: Whether the channel is private

        Returns:
            Number of successfully ingested messages
        """
        documents = []

        for msg in messages:
            try:
                # Generate unique ID
                ts = msg.get('ts', '')
                doc_id = f"slack-{channel_id}-{ts}"

                # Parse timestamp
                msg_ts = float(ts) if ts else datetime.now().timestamp()
                msg_date = datetime.fromtimestamp(msg_ts)

                # Get message text
                text = msg.get('text', '')
                if not text:
                    continue

                # Create document
                doc = VectorDocument(
                    id=doc_id,
                    source='slack',
                    title=f"#{channel_name}",
                    content=text,
                    metadata={
                        'channel_id': channel_id,
                        'channel_name': channel_name,
                        'is_private': is_private,
                        'user_id': msg.get('user', 'unknown'),
                        'timestamp': msg_date.isoformat(),
                        'timestamp_epoch': int(msg_date.timestamp()),  # Numeric for filtering
                        'date': msg_date.strftime('%Y-%m-%d'),
                        'permalink': msg.get('permalink', ''),
                        # No access_list needed - all users can see all Slack content
                        'access_type': 'all'
                    }
                )

                documents.append(doc)

            except Exception as e:
                logger.error(f"Error processing Slack message {msg.get('ts')}: {e}")
                continue

        if not documents:
            logger.warning(f"No valid Slack messages to ingest from #{channel_name}")
            return 0

        return self.upsert_documents(documents)

    def ingest_jira_issues(
        self,
        issues: List[Dict[str, Any]],
        project_key: str
    ) -> int:
        """Ingest Jira issues into vector database.

        Per requirements: All Jira content accessible to all users - no permissions needed.

        Args:
            issues: List of Jira issue dicts
            project_key: Jira project key

        Returns:
            Number of successfully ingested issues
        """
        documents = []

        for issue in issues:
            try:
                issue_key = issue.get('key', '')
                fields = issue.get('fields')

                # Skip issues without fields (API error or deleted issue)
                if not fields:
                    logger.warning(f"Skipping Jira issue {issue_key} - missing fields")
                    continue

                # Generate unique ID
                doc_id = f"jira-{issue_key}"

                # Get issue metadata
                summary = fields.get('summary', '')
                description = fields.get('description', '')

                # Handle ADF format for description
                if isinstance(description, dict):
                    description = self._extract_text_from_adf(description)

                # Check for parent/epic information to enrich child tickets
                parent_info = ""
                parent = fields.get('parent')
                if parent:
                    # This is a sub-task with a parent issue
                    parent_key = parent.get('key', '')
                    parent_fields = parent.get('fields', {})
                    parent_summary = parent_fields.get('summary', '')
                    if parent_key and parent_summary:
                        parent_info = f"\n\nParent Issue: {parent_key} - {parent_summary}"
                        logger.debug(f"Adding parent info to {issue_key}: {parent_key}")

                # Also check for epic link (can be in various fields depending on Jira config)
                epic_info = ""
                # Try the newer 'epic' field first
                epic = fields.get('epic')
                if epic and isinstance(epic, dict):
                    epic_key = epic.get('key', '')
                    epic_summary = epic.get('summary', '') or epic.get('name', '')
                    if epic_key and epic_summary:
                        epic_info = f"\n\nEpic: {epic_key} - {epic_summary}"
                        logger.debug(f"Adding epic info to {issue_key}: {epic_key}")
                else:
                    # Fall back to checking common epic link custom field
                    # Epic links are often in customfield_10008, but can vary
                    for field_name, field_value in fields.items():
                        if field_name.startswith('customfield_') and isinstance(field_value, dict):
                            # Check if this looks like an epic reference
                            if field_value.get('key') and ('epic' in field_name.lower() or field_value.get('type') == 'Epic'):
                                epic_key = field_value.get('key', '')
                                epic_summary = field_value.get('summary', '') or field_value.get('name', '')
                                if epic_key and epic_summary:
                                    epic_info = f"\n\nEpic: {epic_key} - {epic_summary}"
                                    logger.debug(f"Adding epic info to {issue_key}: {epic_key} (from {field_name})")
                                    break

                # Combine summary + description + parent info + epic info
                content = f"{summary}\n\n{description or ''}{parent_info}{epic_info}"

                # Parse date
                updated = fields.get('updated', '')
                issue_date = datetime.fromisoformat(updated.replace('Z', '+00:00')) if updated else datetime.now()

                # Create document with safe None checks
                doc = VectorDocument(
                    id=doc_id,
                    source='jira',
                    title=f"{issue_key}: {summary}",
                    content=content,
                    metadata={
                        'issue_key': issue_key,
                        'project_key': project_key,
                        'issue_type': (fields.get('issuetype') or {}).get('name', 'Unknown'),
                        'status': (fields.get('status') or {}).get('name', 'Unknown'),
                        'priority': (fields.get('priority') or {}).get('name', 'Medium'),
                        'assignee': (fields.get('assignee') or {}).get('displayName', 'Unassigned'),
                        'reporter': (fields.get('reporter') or {}).get('displayName', 'Unknown'),
                        'timestamp': issue_date.isoformat(),
                        'timestamp_epoch': int(issue_date.timestamp()),  # Numeric for filtering
                        'date': issue_date.strftime('%Y-%m-%d'),
                        'url': f"{self.settings.jira.url}/browse/{issue_key}",
                        # No access control needed - all users can see all Jira content
                        'access_type': 'all'
                    }
                )

                documents.append(doc)

            except Exception as e:
                logger.error(f"Error processing Jira issue {issue.get('key')}: {e}")
                continue

        if not documents:
            logger.warning(f"No valid Jira issues to ingest for {project_key}")
            return 0

        return self.upsert_documents(documents)

    def ingest_fireflies_transcripts(
        self,
        transcripts: List[Dict[str, Any]],
        user_id: Optional[int] = None
    ) -> int:
        """Ingest Fireflies meeting transcripts into vector database.

        Per requirements: Base access on sharing settings, not just meeting attendees.
        If a user is not in the meeting but the meeting is shared with them, they should have access.

        Args:
            transcripts: List of Fireflies transcript dicts (with sharing_settings if available)
            user_id: User ID for permission checks (optional)

        Returns:
            Number of successfully ingested transcripts
        """
        documents = []

        for transcript in transcripts:
            try:
                meeting_id = transcript.get('id', '')
                title = transcript.get('title', 'Untitled Meeting')

                # Generate unique ID
                doc_id = f"fireflies-{meeting_id}"

                # Get transcript text
                transcript_text = transcript.get('transcript', '')
                if not transcript_text:
                    continue

                # Parse date
                date_value = transcript.get('date')
                if isinstance(date_value, (int, float)) and date_value > 1000000000000:
                    meeting_date = datetime.fromtimestamp(date_value / 1000)
                else:
                    meeting_date = datetime.fromisoformat(str(date_value)) if date_value else datetime.now()

                # Get attendees
                attendees = transcript.get('attendees', [])
                attendee_emails = [a.get('email', '') for a in attendees if isinstance(a, dict)]
                attendee_names = [a.get('name', a) for a in attendees] if attendees else []

                # Get sharing settings (new!)
                sharing_settings = transcript.get('sharing_settings', {})
                shared_with_emails = sharing_settings.get('shared_with', [])
                is_public = sharing_settings.get('is_public', False)

                # Build access list: attendees + people it's shared with
                access_list = list(set(attendee_emails + shared_with_emails))

                # Create document
                doc = VectorDocument(
                    id=doc_id,
                    source='fireflies',
                    title=title,
                    content=f"{title}\n\n{transcript_text}",
                    metadata={
                        'meeting_id': meeting_id,
                        'title': title,
                        'attendees': attendee_names,
                        'attendee_emails': attendee_emails,
                        'duration': transcript.get('duration', 0),
                        'timestamp': meeting_date.isoformat(),
                        'timestamp_epoch': int(meeting_date.timestamp()),  # Numeric for filtering
                        'date': meeting_date.strftime('%Y-%m-%d'),
                        # Access control based on sharing settings
                        'access_type': 'public' if is_public else 'shared',
                        'access_list': access_list,  # Attendees + shared users
                        'shared_with': shared_with_emails,  # Explicitly shared
                        'is_public': is_public
                    }
                )

                documents.append(doc)

            except Exception as e:
                logger.error(f"Error processing Fireflies transcript {transcript.get('id')}: {e}")
                continue

        if not documents:
            logger.warning("No valid Fireflies transcripts to ingest")
            return 0

        return self.upsert_documents(documents)

    def ingest_notion_pages(
        self,
        pages: List[Dict[str, Any]],
        full_content_map: Dict[str, str]
    ) -> int:
        """Ingest Notion pages into vector database.

        Args:
            pages: List of Notion page metadata dicts
            full_content_map: Dict mapping page_id to full page content text

        Returns:
            Number of successfully ingested pages
        """
        documents = []

        for page in pages:
            try:
                page_id = page.get('id', '')

                # Get page title
                properties = page.get('properties', {})
                title = "Untitled"
                for prop_name, prop_data in properties.items():
                    if prop_data.get('type') == 'title':
                        title_arr = prop_data.get('title', [])
                        if title_arr:
                            title = title_arr[0].get('plain_text', 'Untitled')
                            break

                # Get full content from map
                content = full_content_map.get(page_id, '')

                # Parse dates
                created_time = page.get('created_time', '')
                last_edited_time = page.get('last_edited_time', '')

                page_date = datetime.now()
                if last_edited_time:
                    try:
                        page_date = datetime.fromisoformat(last_edited_time.replace('Z', '+00:00'))
                    except:
                        pass

                # Generate unique ID
                doc_id = f"notion-{page_id}"

                # Create document
                doc = VectorDocument(
                    id=doc_id,
                    source='notion',
                    title=title,
                    content=content,
                    metadata={
                        'page_id': page_id,
                        'url': page.get('url', ''),
                        'created_time': created_time,
                        'last_edited_time': last_edited_time,
                        'timestamp': page_date.isoformat(),
                        'timestamp_epoch': int(page_date.timestamp()),
                        'date': page_date.strftime('%Y-%m-%d'),
                        # All Notion pages accessible to all users (no per-user permissions)
                        'access_type': 'all'
                    }
                )

                documents.append(doc)

            except Exception as e:
                logger.error(f"Error processing Notion page {page.get('id')}: {e}")
                continue

        if not documents:
            logger.warning("No valid Notion pages to ingest")
            return 0

        return self.upsert_documents(documents)

    def _extract_text_from_adf(self, adf_content: Dict[str, Any]) -> str:
        """Extract plain text from Atlassian Document Format (ADF) JSON."""
        if not isinstance(adf_content, dict):
            return str(adf_content)

        text_parts = []

        # Handle different ADF node types
        node_type = adf_content.get('type', '')

        if node_type == 'text':
            text_parts.append(adf_content.get('text', ''))

        # Recurse into content array
        if 'content' in adf_content and isinstance(adf_content['content'], list):
            for child in adf_content['content']:
                text_parts.append(self._extract_text_from_adf(child))

        return ' '.join(filter(None, text_parts)).strip()

    def get_last_sync_timestamp(self, source: str) -> Optional[datetime]:
        """Get the last sync timestamp for a source from metadata.

        Args:
            source: Source name (slack, jira, fireflies, notion)

        Returns:
            Last sync timestamp or None
        """
        # For now, store in Pinecone metadata namespace or local DB
        # This is a placeholder - implement with your preferred storage
        try:
            from src.utils.database import get_engine
            from sqlalchemy import text

            engine = get_engine()
            with engine.connect() as conn:
                result = conn.execute(
                    text("SELECT last_sync FROM vector_sync_status WHERE source = :source"),
                    {"source": source}
                )
                row = result.fetchone()
                if row:
                    return datetime.fromisoformat(row[0])

            return None

        except Exception as e:
            logger.warning(f"Could not get last sync timestamp for {source}: {e}")
            return None

    def update_last_sync_timestamp(self, source: str, timestamp: datetime) -> None:
        """Update the last sync timestamp for a source.

        Args:
            source: Source name
            timestamp: Sync timestamp
        """
        try:
            from src.utils.database import get_engine
            from sqlalchemy import text

            engine = get_engine()
            with engine.connect() as conn:
                # Upsert sync status
                conn.execute(
                    text("""
                        INSERT INTO vector_sync_status (source, last_sync)
                        VALUES (:source, :timestamp)
                        ON CONFLICT (source) DO UPDATE SET last_sync = :timestamp
                    """),
                    {"source": source, "timestamp": timestamp.isoformat()}
                )
                conn.commit()

            logger.info(f"✅ Updated last sync for {source}: {timestamp}")

        except Exception as e:
            logger.error(f"Failed to update last sync for {source}: {e}")
