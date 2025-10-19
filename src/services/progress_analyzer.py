"""Progress analysis service to extract progress signals from search results."""

import logging
import re
from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ProgressSignal:
    """A single progress signal extracted from a result."""
    type: str  # 'jira_status', 'github_activity', 'blocker', 'stale', 'recent_activity'
    entity: str  # Jira ticket, PR number, commit SHA, etc.
    status: str  # Current status or description
    date: datetime
    source: str  # Where this signal came from
    details: Optional[str] = None  # Additional context


@dataclass
class ProgressAnalysis:
    """Comprehensive progress analysis across all sources."""
    jira_status: Dict[str, Any]  # Ticket statuses and transitions
    github_activity: Dict[str, Any]  # PR and commit activity
    blockers: List[Dict[str, str]]  # Detected blockers
    recent_activity: List[Dict[str, str]]  # Recent progress (last 7 days)
    stale_items: List[Dict[str, str]]  # Work with no updates in 14+ days
    timeline: List[Dict[str, str]]  # Chronological progress timeline
    progress_summary: str  # High-level progress description


class ProgressAnalyzer:
    """Analyzes progress signals across all data sources."""

    def __init__(self):
        """Initialize progress analyzer."""
        self.logger = logging.getLogger(__name__)

        # Blocker keywords to detect
        self.blocker_keywords = {
            'blocked on', 'blocked by', 'waiting for', 'waiting on',
            'dependency on', 'needs', 'requires', 'can\'t proceed',
            'stuck', 'issue with', 'problem with', 'pending'
        }

        # Jira status categories
        self.status_categories = {
            'todo': {'to do', 'open', 'backlog', 'new'},
            'in_progress': {'in progress', 'in development', 'in review', 'code review'},
            'done': {'done', 'closed', 'resolved', 'completed', 'merged'},
            'blocked': {'blocked', 'on hold', 'waiting'}
        }

    async def analyze_progress(
        self,
        results: List[Any],  # List of SearchResult objects
        entity_links: Dict[str, Any]
    ) -> ProgressAnalysis:
        """Extract progress insights from search results.

        Args:
            results: List of SearchResult objects
            entity_links: Entity cross-references from context search

        Returns:
            ProgressAnalysis with comprehensive progress insights
        """
        # Extract progress signals from each result
        signals = []
        for idx, result in enumerate(results):
            extracted = self._extract_signals_from_result(result, idx)
            signals.extend(extracted)

        # Analyze Jira ticket status
        jira_status = self._analyze_jira_status(results, entity_links, signals)

        # Analyze GitHub activity
        github_activity = self._analyze_github_activity(results, signals)

        # Detect blockers
        blockers = self._detect_blockers(results, signals)

        # Find recent activity (last 7 days)
        recent_activity = self._find_recent_activity(results, signals)

        # Find stale items (no updates in 14+ days)
        stale_items = self._find_stale_items(results, jira_status, github_activity)

        # Build chronological timeline
        timeline = self._build_timeline(signals)

        # Generate progress summary
        progress_summary = self._generate_progress_summary(
            jira_status, github_activity, blockers, recent_activity, stale_items
        )

        return ProgressAnalysis(
            jira_status=jira_status,
            github_activity=github_activity,
            blockers=blockers,
            recent_activity=recent_activity,
            stale_items=stale_items,
            timeline=timeline,
            progress_summary=progress_summary
        )

    def _extract_signals_from_result(self, result: Any, idx: int) -> List[ProgressSignal]:
        """Extract progress signals from a single search result.

        Args:
            result: SearchResult object
            idx: Result index

        Returns:
            List of ProgressSignal objects
        """
        signals = []
        combined_text = f"{result.title} {result.content}"

        # Extract Jira ticket status signals
        if result.source == 'jira':
            # Parse status from content (format: "[Status] [Type] Assignee: ...")
            status_match = re.search(r'\[([^\]]+)\]', result.content)
            if status_match:
                status = status_match.group(1)

                # Extract ticket key from title (format: "KEY-123: Summary")
                ticket_match = re.search(r'^([A-Z]{2,6}-\d+):', result.title)
                if ticket_match:
                    ticket_key = ticket_match.group(1)

                    signals.append(ProgressSignal(
                        type='jira_status',
                        entity=ticket_key,
                        status=status,
                        date=result.date,
                        source=result.source,
                        details=result.content[:200]
                    ))

        # Extract GitHub PR/commit activity signals
        elif result.source == 'github':
            # PR signals
            pr_match = re.search(r'PR #(\d+):', result.title)
            if pr_match:
                pr_number = pr_match.group(1)

                # Parse state from content (format: "[State] PR #123 ...")
                state_match = re.search(r'\[(Merged|Open|Closed)\]', result.content)
                if state_match:
                    state = state_match.group(1)

                    signals.append(ProgressSignal(
                        type='github_pr',
                        entity=f"#{pr_number}",
                        status=state,
                        date=result.date,
                        source=result.source,
                        details=result.title
                    ))

            # Commit signals
            elif 'Commit:' in result.title:
                commit_match = re.search(r'Commit ([a-f0-9]{7})', result.content)
                if commit_match:
                    commit_sha = commit_match.group(1)

                    signals.append(ProgressSignal(
                        type='github_commit',
                        entity=commit_sha,
                        status='committed',
                        date=result.date,
                        source=result.source,
                        details=result.title
                    ))

        # Detect blocker signals in any source
        blocker_text = self._extract_blocker_text(combined_text)
        if blocker_text:
            # Try to extract entity (Jira ticket, PR, etc.)
            entity = self._extract_entity_from_text(result.title)

            signals.append(ProgressSignal(
                type='blocker',
                entity=entity or 'general',
                status='blocked',
                date=result.date,
                source=result.source,
                details=blocker_text
            ))

        return signals

    def _extract_blocker_text(self, text: str) -> Optional[str]:
        """Extract blocker description from text.

        Args:
            text: Text to search for blocker keywords

        Returns:
            Blocker description or None if not found
        """
        text_lower = text.lower()

        for keyword in self.blocker_keywords:
            pos = text_lower.find(keyword)
            if pos != -1:
                # Extract sentence containing the blocker keyword
                # Find sentence boundaries (., !, ?) or newlines
                start = max(0, text_lower.rfind('.', 0, pos) + 1)
                end = text_lower.find('.', pos)
                if end == -1:
                    end = text_lower.find('\n', pos)
                if end == -1:
                    end = min(len(text), pos + 200)

                blocker_text = text[start:end].strip()
                return blocker_text[:300]  # Limit length

        return None

    def _extract_entity_from_text(self, text: str) -> Optional[str]:
        """Extract entity (Jira ticket, PR number) from text.

        Args:
            text: Text to search

        Returns:
            Entity identifier or None
        """
        # Try Jira ticket first
        jira_match = re.search(r'\b([A-Z]{2,6}-\d+)\b', text)
        if jira_match:
            return jira_match.group(1)

        # Try PR number
        pr_match = re.search(r'PR #?(\d+)', text, re.IGNORECASE)
        if pr_match:
            return f"#{pr_match.group(1)}"

        return None

    def _analyze_jira_status(
        self,
        results: List[Any],
        entity_links: Dict[str, Any],
        signals: List[ProgressSignal]
    ) -> Dict[str, Any]:
        """Analyze Jira ticket statuses and transitions.

        Returns:
            Dict with status breakdown and recent changes
        """
        jira_tickets = {}  # ticket_key -> status info

        # Extract status from signals
        for signal in signals:
            if signal.type == 'jira_status':
                ticket = signal.entity
                if ticket not in jira_tickets:
                    jira_tickets[ticket] = {
                        'ticket': ticket,
                        'status': signal.status,
                        'last_updated': signal.date,
                        'source_count': 1,
                        'details': signal.details
                    }
                else:
                    # Update with most recent status
                    if signal.date > jira_tickets[ticket]['last_updated']:
                        jira_tickets[ticket]['status'] = signal.status
                        jira_tickets[ticket]['last_updated'] = signal.date
                    jira_tickets[ticket]['source_count'] += 1

        # Categorize tickets by status
        status_breakdown = {
            'todo': [],
            'in_progress': [],
            'done': [],
            'blocked': []
        }

        for ticket_info in jira_tickets.values():
            status_lower = ticket_info['status'].lower()

            # Categorize based on status
            categorized = False
            for category, statuses in self.status_categories.items():
                if status_lower in statuses:
                    status_breakdown[category].append(ticket_info)
                    categorized = True
                    break

            # Default to in_progress if unknown status
            if not categorized:
                status_breakdown['in_progress'].append(ticket_info)

        # Find recently updated tickets (last 7 days)
        recent_updates = []
        cutoff = datetime.now() - timedelta(days=7)
        for ticket_info in jira_tickets.values():
            if ticket_info['last_updated'] >= cutoff:
                recent_updates.append(ticket_info)

        # Sort by date descending
        recent_updates.sort(key=lambda x: x['last_updated'], reverse=True)

        return {
            'tickets': jira_tickets,
            'breakdown': status_breakdown,
            'recent_updates': recent_updates[:10],  # Top 10 most recent
            'total_count': len(jira_tickets)
        }

    def _analyze_github_activity(
        self,
        results: List[Any],
        signals: List[ProgressSignal]
    ) -> Dict[str, Any]:
        """Analyze GitHub PR and commit activity.

        Returns:
            Dict with PR and commit activity breakdown
        """
        prs = {}  # pr_number -> pr info
        commits = []  # List of commit info

        # Extract from signals
        for signal in signals:
            if signal.type == 'github_pr':
                pr_num = signal.entity
                if pr_num not in prs:
                    prs[pr_num] = {
                        'pr': pr_num,
                        'status': signal.status,
                        'date': signal.date,
                        'title': signal.details
                    }
                else:
                    # Update with most recent info
                    if signal.date > prs[pr_num]['date']:
                        prs[pr_num]['status'] = signal.status
                        prs[pr_num]['date'] = signal.date

            elif signal.type == 'github_commit':
                commits.append({
                    'sha': signal.entity,
                    'date': signal.date,
                    'message': signal.details
                })

        # Categorize PRs by status
        pr_breakdown = {
            'merged': [],
            'open': [],
            'closed': []
        }

        for pr_info in prs.values():
            status = pr_info['status'].lower()
            if status in pr_breakdown:
                pr_breakdown[status].append(pr_info)

        # Find recent activity (last 7 days)
        cutoff = datetime.now() - timedelta(days=7)
        recent_prs = [pr for pr in prs.values() if pr['date'] >= cutoff]
        recent_commits = [c for c in commits if c['date'] >= cutoff]

        # Sort by date descending
        recent_prs.sort(key=lambda x: x['date'], reverse=True)
        recent_commits.sort(key=lambda x: x['date'], reverse=True)

        return {
            'prs': prs,
            'commits': commits,
            'pr_breakdown': pr_breakdown,
            'recent_prs': recent_prs[:10],
            'recent_commits': recent_commits[:10],
            'total_pr_count': len(prs),
            'total_commit_count': len(commits)
        }

    def _detect_blockers(
        self,
        results: List[Any],
        signals: List[ProgressSignal]
    ) -> List[Dict[str, str]]:
        """Detect and extract blocker information.

        Returns:
            List of blocker dicts with entity, description, source, date
        """
        blockers = []

        # Extract from blocker signals
        for signal in signals:
            if signal.type == 'blocker':
                blockers.append({
                    'entity': signal.entity,
                    'description': signal.details or 'Blocker detected',
                    'source': signal.source,
                    'date': signal.date.strftime('%Y-%m-%d'),
                    'days_ago': (datetime.now() - signal.date).days
                })

        # Sort by recency (most recent first)
        blockers.sort(key=lambda x: x['days_ago'])

        return blockers[:10]  # Limit to 10 most recent blockers

    def _find_recent_activity(
        self,
        results: List[Any],
        signals: List[ProgressSignal]
    ) -> List[Dict[str, str]]:
        """Find activity from the last 7 days.

        Returns:
            List of recent activity items
        """
        cutoff = datetime.now() - timedelta(days=7)
        recent = []

        for signal in signals:
            if signal.date >= cutoff and signal.type != 'blocker':
                recent.append({
                    'type': signal.type,
                    'entity': signal.entity,
                    'status': signal.status,
                    'date': signal.date.strftime('%Y-%m-%d'),
                    'days_ago': (datetime.now() - signal.date).days,
                    'source': signal.source,
                    'details': signal.details[:100] if signal.details else ''
                })

        # Sort by recency
        recent.sort(key=lambda x: x['days_ago'])

        return recent[:15]  # Limit to 15 most recent

    def _find_stale_items(
        self,
        results: List[Any],
        jira_status: Dict[str, Any],
        github_activity: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """Find work items with no updates in 14+ days.

        Returns:
            List of stale items
        """
        cutoff = datetime.now() - timedelta(days=14)
        stale = []

        # Check Jira tickets
        for ticket_info in jira_status['tickets'].values():
            if ticket_info['last_updated'] < cutoff:
                # Only flag non-Done tickets as stale
                if ticket_info['status'].lower() not in self.status_categories['done']:
                    stale.append({
                        'type': 'jira',
                        'entity': ticket_info['ticket'],
                        'status': ticket_info['status'],
                        'last_updated': ticket_info['last_updated'].strftime('%Y-%m-%d'),
                        'days_ago': (datetime.now() - ticket_info['last_updated']).days
                    })

        # Check GitHub PRs (only open PRs)
        for pr_info in github_activity['prs'].values():
            if pr_info['date'] < cutoff and pr_info['status'].lower() == 'open':
                stale.append({
                    'type': 'github_pr',
                    'entity': pr_info['pr'],
                    'status': pr_info['status'],
                    'last_updated': pr_info['date'].strftime('%Y-%m-%d'),
                    'days_ago': (datetime.now() - pr_info['date']).days
                })

        # Sort by staleness (oldest first)
        stale.sort(key=lambda x: x['days_ago'], reverse=True)

        return stale[:10]  # Limit to 10 stalest items

    def _build_timeline(self, signals: List[ProgressSignal]) -> List[Dict[str, str]]:
        """Build chronological progress timeline from signals.

        Returns:
            List of timeline events sorted by date
        """
        timeline = []

        for signal in signals:
            # Skip blocker signals in timeline (they're shown separately)
            if signal.type == 'blocker':
                continue

            event_desc = self._format_signal_for_timeline(signal)
            if event_desc:
                timeline.append({
                    'date': signal.date.strftime('%Y-%m-%d'),
                    'event': event_desc,
                    'type': signal.type
                })

        # Sort by date descending (most recent first)
        timeline.sort(key=lambda x: x['date'], reverse=True)

        # Deduplicate similar events on same date
        seen = set()
        deduped = []
        for item in timeline:
            key = (item['date'], item['event'][:50])  # Use first 50 chars as key
            if key not in seen:
                seen.add(key)
                deduped.append(item)

        return deduped[:20]  # Limit to 20 most recent events

    def _format_signal_for_timeline(self, signal: ProgressSignal) -> Optional[str]:
        """Format a progress signal as a timeline event.

        Args:
            signal: ProgressSignal object

        Returns:
            Formatted event string or None
        """
        if signal.type == 'jira_status':
            return f"{signal.entity} → {signal.status}"
        elif signal.type == 'github_pr':
            return f"PR {signal.entity} {signal.status}"
        elif signal.type == 'github_commit':
            return f"Commit {signal.entity}: {signal.details[:50]}"
        else:
            return f"{signal.entity}: {signal.status}"

    def _generate_progress_summary(
        self,
        jira_status: Dict[str, Any],
        github_activity: Dict[str, Any],
        blockers: List[Dict[str, str]],
        recent_activity: List[Dict[str, str]],
        stale_items: List[Dict[str, str]]
    ) -> str:
        """Generate high-level progress summary.

        Returns:
            Human-readable progress summary string
        """
        parts = []

        # Jira summary
        jira_total = jira_status['total_count']
        if jira_total > 0:
            breakdown = jira_status['breakdown']
            parts.append(
                f"{jira_total} Jira tickets tracked: "
                f"{len(breakdown['done'])} done, "
                f"{len(breakdown['in_progress'])} in progress, "
                f"{len(breakdown['todo'])} to do, "
                f"{len(breakdown['blocked'])} blocked"
            )

        # GitHub summary
        pr_total = github_activity['total_pr_count']
        commit_total = github_activity['total_commit_count']
        if pr_total > 0 or commit_total > 0:
            pr_breakdown = github_activity['pr_breakdown']
            parts.append(
                f"{pr_total} PRs ({len(pr_breakdown['merged'])} merged, "
                f"{len(pr_breakdown['open'])} open), "
                f"{commit_total} commits"
            )

        # Recent activity
        if recent_activity:
            parts.append(f"{len(recent_activity)} updates in last 7 days")

        # Blockers
        if blockers:
            parts.append(f"{len(blockers)} active blockers")

        # Stale items
        if stale_items:
            parts.append(f"{len(stale_items)} stale items (14+ days no update)")

        return "; ".join(parts) if parts else "No progress data available"
