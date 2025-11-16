"""Script to seed Jira templates from CSV file."""

import csv
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.database import get_session
from src.models import TemplateEpic, TemplateTicket
from src.utils.epic_color_mapper import get_epic_color_hex


def parse_csv_and_seed(csv_path: str, clear_existing: bool = False):
    """
    Parse CSV file and seed template_epics and template_tickets tables.

    CSV Format:
    Epic Name,Epic Link,Issue Type,Summary,Description,Epic Color

    Args:
        csv_path: Path to CSV file
        clear_existing: If True, delete all existing templates before seeding
    """
    session = get_session()

    try:
        # Clear existing data if requested
        if clear_existing:
            print("Clearing existing template data...")
            session.query(TemplateTicket).delete()
            session.query(TemplateEpic).delete()
            session.commit()
            print("✓ Existing data cleared")

        # Read CSV
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            epic_map = {}  # Map epic names to epic IDs
            epic_count = 0
            ticket_count = 0

            for row_num, row in enumerate(reader, start=1):
                epic_name = row.get("Epic Name", "").strip()
                epic_link = row.get("Epic Link", "").strip()
                issue_type = row.get("Issue Type", "").strip()
                summary = row.get("Summary", "").strip()
                description = row.get("Description", "").strip()
                epic_color = row.get("Epic Color", "").strip()

                # Row is an epic definition
                if epic_name and issue_type == "Epic":
                    # Create epic
                    color_hex = get_epic_color_hex(epic_color)

                    epic = TemplateEpic(
                        epic_name=epic_name,
                        summary=summary or epic_name,
                        description=description,
                        epic_color=color_hex,
                        epic_category=None,  # Will be set via UI later
                        sort_order=epic_count,
                    )

                    session.add(epic)
                    session.flush()  # Get ID without committing

                    epic_map[epic_name] = epic.id
                    epic_count += 1

                    print(f"✓ Epic: {epic_name} (color: {color_hex})")

                # Row is a ticket definition
                elif epic_link and issue_type and summary:
                    # Find parent epic
                    parent_epic_id = epic_map.get(epic_link)

                    if not parent_epic_id:
                        print(
                            f"⚠ Warning (row {row_num}): Epic '{epic_link}' not found for ticket '{summary}'"
                        )
                        continue

                    ticket = TemplateTicket(
                        template_epic_id=parent_epic_id,
                        issue_type=issue_type,
                        summary=summary,
                        description=description,
                        sort_order=ticket_count,
                    )

                    session.add(ticket)
                    ticket_count += 1

                    print(f"  └─ {issue_type}: {summary}")

        # Commit all changes
        session.commit()

        print("\n" + "=" * 60)
        print(f"✓ Seeding complete!")
        print(f"  • {epic_count} epics created")
        print(f"  • {ticket_count} tickets created")
        print("=" * 60)

    except Exception as e:
        session.rollback()
        print(f"\n✗ Error: {e}")
        raise

    finally:
        session.close()


if __name__ == "__main__":
    # Default CSV path
    csv_path = (
        Path(__file__).parent.parent
        / "docs"
        / "Jira Ticket Import (SPCZ Suggestions) - New Build _ Wyatt (1).csv"
    )

    # Check if CSV exists
    if not csv_path.exists():
        print(f"✗ CSV file not found: {csv_path}")
        sys.exit(1)

    # Parse and seed
    print(f"Seeding templates from: {csv_path}\n")
    parse_csv_and_seed(str(csv_path), clear_existing=True)
