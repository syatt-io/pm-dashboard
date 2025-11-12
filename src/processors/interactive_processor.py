"""Interactive processor for reviewing and confirming action items."""

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import json
from rich.console import Console
from rich.table import Table
from rich.prompt import Confirm, Prompt
from rich.panel import Panel
from rich.syntax import Syntax
from rich.markdown import Markdown

from src.processors.transcript_analyzer import ActionItem, MeetingAnalysis


logger = logging.getLogger(__name__)


@dataclass
class ReviewedItem:
    """An action item that has been reviewed and categorized."""

    original: ActionItem
    destination: str  # 'jira', 'todo', 'skip'
    modified_title: Optional[str] = None
    modified_assignee: Optional[str] = None
    modified_priority: Optional[str] = None
    modified_due_date: Optional[str] = None
    jira_project: Optional[str] = None
    jira_issue_type: Optional[str] = "Task"


class InteractiveProcessor:
    """Interactive processor for reviewing meeting outcomes."""

    def __init__(self):
        self.console = Console()

    def review_meeting_analysis(
        self,
        meeting_title: str,
        analysis: MeetingAnalysis,
        default_jira_project: str = None,
    ) -> Tuple[List[ReviewedItem], bool]:
        """
        Interactively review meeting analysis and get user confirmation.

        Returns:
            Tuple of (reviewed_items, should_proceed)
        """
        self.console.clear()

        # Display meeting summary
        self._display_meeting_summary(meeting_title, analysis)

        # Review action items
        reviewed_items = self._review_action_items(
            analysis.action_items, default_jira_project
        )

        # Display final summary and get confirmation
        if reviewed_items:
            should_proceed = self._confirm_actions(reviewed_items)
        else:
            self.console.print("\n[yellow]No action items to process.[/yellow]")
            should_proceed = False

        return reviewed_items, should_proceed

    def _display_meeting_summary(self, meeting_title: str, analysis: MeetingAnalysis):
        """Display the meeting summary."""
        self.console.print(
            Panel.fit(
                f"[bold cyan]{meeting_title}[/bold cyan]", title="Meeting Analysis"
            )
        )

        # Executive Summary
        if analysis.executive_summary:
            self.console.print("\n[bold]Executive Summary:[/bold]")
            self.console.print(Markdown(analysis.executive_summary))

        # Outcomes
        if analysis.outcomes:
            self.console.print("\n[bold]Outcomes:[/bold]")
            for outcome in analysis.outcomes:
                self.console.print(f"  • {outcome}")

        # Blockers & Constraints
        if analysis.blockers_and_constraints:
            self.console.print("\n[bold red]Blockers & Constraints:[/bold red]")
            for blocker in analysis.blockers_and_constraints:
                self.console.print(f"  ⚠️  {blocker}")

        # Timeline & Milestones
        if analysis.timeline_and_milestones:
            self.console.print("\n[bold]Timeline & Milestones:[/bold]")
            for milestone in analysis.timeline_and_milestones:
                self.console.print(f"  📅 {milestone}")

        # Key Discussions
        if analysis.key_discussions:
            self.console.print("\n[bold]Key Discussions:[/bold]")
            for discussion in analysis.key_discussions:
                self.console.print(f"  💬 {discussion}")

        self.console.print("\n" + "=" * 60 + "\n")

    def _review_action_items(
        self, action_items: List[ActionItem], default_jira_project: str = None
    ) -> List[ReviewedItem]:
        """Review each action item and categorize it."""
        reviewed_items = []

        self.console.print(
            "[bold]Found {} action items to review:[/bold]\n".format(len(action_items))
        )

        for i, item in enumerate(action_items, 1):
            self.console.print(
                f"[bold cyan]Action Item {i}/{len(action_items)}:[/bold cyan]"
            )

            # Display item details
            table = Table(show_header=False, box=None)
            table.add_column(style="bold", width=15)
            table.add_column()

            table.add_row("Title:", item.title)
            table.add_row(
                "Description:",
                (
                    item.description[:200] + "..."
                    if len(item.description) > 200
                    else item.description
                ),
            )
            table.add_row("Assignee:", item.assignee or "Unassigned")
            table.add_row("Due Date:", item.due_date or "No due date")
            table.add_row("Priority:", item.priority)
            table.add_row(
                "Context:",
                item.context[:150] + "..." if len(item.context) > 150 else item.context,
            )

            self.console.print(table)
            self.console.print()

            # Ask user what to do with this item
            destination = self._get_item_destination()

            if destination == "skip":
                self.console.print("[yellow]Skipping this item.[/yellow]\n")
                continue

            # Allow editing if needed
            reviewed_item = ReviewedItem(original=item, destination=destination)

            if Confirm.ask("Would you like to modify this item?"):
                reviewed_item = self._modify_item(reviewed_item, default_jira_project)
            elif destination == "jira":
                reviewed_item.jira_project = default_jira_project

            reviewed_items.append(reviewed_item)
            self.console.print("[green]✓ Item categorized[/green]\n")
            self.console.print("-" * 40 + "\n")

        return reviewed_items

    def _get_item_destination(self) -> str:
        """Ask user where to send this action item."""
        choices = {
            "1": "jira",
            "2": "todo",
            "3": "skip",
            "j": "jira",
            "t": "todo",
            "s": "skip",
        }

        self.console.print("Where should this item go?")
        self.console.print("  [1] Create Jira ticket (j)")
        self.console.print("  [2] Add to TODO list (t)")
        self.console.print("  [3] Skip this item (s)")

        while True:
            choice = Prompt.ask("Choice", choices=list(choices.keys()), default="1")
            return choices[choice.lower()]

    def _modify_item(
        self, reviewed_item: ReviewedItem, default_jira_project: str = None
    ) -> ReviewedItem:
        """Allow user to modify item details."""
        item = reviewed_item.original

        # Title
        new_title = Prompt.ask("Title", default=item.title)
        if new_title != item.title:
            reviewed_item.modified_title = new_title

        # Assignee
        new_assignee = Prompt.ask("Assignee", default=item.assignee or "")
        if new_assignee and new_assignee != item.assignee:
            reviewed_item.modified_assignee = new_assignee

        # Priority
        priorities = ["High", "Medium", "Low"]
        self.console.print(f"Priority options: {', '.join(priorities)}")
        new_priority = Prompt.ask("Priority", default=item.priority, choices=priorities)
        if new_priority != item.priority:
            reviewed_item.modified_priority = new_priority

        # Due date
        new_due = Prompt.ask("Due date (YYYY-MM-DD)", default=item.due_date or "")
        if new_due and new_due != item.due_date:
            reviewed_item.modified_due_date = new_due

        # Jira-specific fields
        if reviewed_item.destination == "jira":
            reviewed_item.jira_project = Prompt.ask(
                "Jira Project", default=default_jira_project or "PM"
            )
            issue_types = ["Task", "Bug", "Story", "Epic"]
            self.console.print(f"Issue types: {', '.join(issue_types)}")
            reviewed_item.jira_issue_type = Prompt.ask(
                "Issue Type", default="Task", choices=issue_types
            )

        return reviewed_item

    def _confirm_actions(self, reviewed_items: List[ReviewedItem]) -> bool:
        """Display final summary and get confirmation."""
        self.console.print("\n" + "=" * 60)
        self.console.print("[bold]Final Summary:[/bold]\n")

        # Separate by destination
        jira_items = [r for r in reviewed_items if r.destination == "jira"]
        todo_items = [r for r in reviewed_items if r.destination == "todo"]

        if jira_items:
            self.console.print(
                f"[bold green]Jira Tickets to Create ({len(jira_items)}):[/bold green]"
            )
            for item in jira_items:
                title = item.modified_title or item.original.title
                assignee = (
                    item.modified_assignee or item.original.assignee or "Unassigned"
                )
                project = item.jira_project
                self.console.print(f"  • [{project}] {title} → {assignee}")

        if todo_items:
            self.console.print(
                f"\n[bold blue]TODO Items to Add ({len(todo_items)}):[/bold blue]"
            )
            for item in todo_items:
                title = item.modified_title or item.original.title
                due = item.modified_due_date or item.original.due_date or "No due date"
                self.console.print(f"  • {title} (Due: {due})")

        self.console.print("\n" + "=" * 60 + "\n")

        return Confirm.ask(
            f"Proceed with creating {len(jira_items)} Jira tickets and {len(todo_items)} TODO items?",
            default=True,
        )

    def display_processing_results(self, results: Dict[str, Any]):
        """Display the results of processing."""
        self.console.print("\n[bold]Processing Results:[/bold]\n")

        if results.get("jira_created"):
            self.console.print("[green]✅ Jira Tickets Created:[/green]")
            for ticket_key in results["jira_created"]:
                self.console.print(f"  • {ticket_key}")

        if results.get("todos_created"):
            self.console.print("\n[blue]✅ TODO Items Added:[/blue]")
            for todo in results["todos_created"]:
                self.console.print(f"  • {todo}")

        if results.get("errors"):
            self.console.print("\n[red]❌ Errors:[/red]")
            for error in results["errors"]:
                self.console.print(f"  • {error}")

        self.console.print("\n[bold green]Processing complete![/bold green]")
