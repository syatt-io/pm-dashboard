"""add_send_meeting_emails_to_projects

Revision ID: a8873baa32a5
Revises: 39ec1875570b
Create Date: 2025-10-29 19:05:51.116758

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a8873baa32a5"
down_revision: Union[str, Sequence[str], None] = "39ec1875570b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - add send_meeting_emails column to projects table."""
    # Add boolean column to enable/disable email notifications per project
    # Default to False (opt-in behavior)
    op.add_column(
        "projects",
        sa.Column(
            "send_meeting_emails", sa.Boolean(), nullable=False, server_default="0"
        ),
    )


def downgrade() -> None:
    """Downgrade schema - remove send_meeting_emails column."""
    # Remove the column if we need to rollback
    op.drop_column("projects", "send_meeting_emails")
