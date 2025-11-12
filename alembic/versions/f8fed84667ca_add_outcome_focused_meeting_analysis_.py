"""add_outcome_focused_meeting_analysis_fields

Revision ID: f8fed84667ca
Revises: 4246ddc8b889
Create Date: 2025-10-28 12:27:08.046566

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f8fed84667ca"
down_revision: Union[str, Sequence[str], None] = "4246ddc8b889"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add new outcome-focused meeting analysis fields to processed_meetings table."""
    # Add new structure columns
    op.add_column(
        "processed_meetings", sa.Column("executive_summary", sa.Text(), nullable=True)
    )
    op.add_column("processed_meetings", sa.Column("outcomes", sa.Text(), nullable=True))
    op.add_column(
        "processed_meetings",
        sa.Column("blockers_and_constraints", sa.Text(), nullable=True),
    )
    op.add_column(
        "processed_meetings",
        sa.Column("timeline_and_milestones", sa.Text(), nullable=True),
    )
    op.add_column(
        "processed_meetings", sa.Column("key_discussions", sa.Text(), nullable=True)
    )


def downgrade() -> None:
    """Remove outcome-focused meeting analysis fields from processed_meetings table."""
    # Remove new structure columns
    op.drop_column("processed_meetings", "key_discussions")
    op.drop_column("processed_meetings", "timeline_and_milestones")
    op.drop_column("processed_meetings", "blockers_and_constraints")
    op.drop_column("processed_meetings", "outcomes")
    op.drop_column("processed_meetings", "executive_summary")
