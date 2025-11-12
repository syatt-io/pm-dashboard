"""remove_deprecated_slack_channel_column

Revision ID: 4246ddc8b889
Revises: 2f3e386f9b02
Create Date: 2025-10-22 19:11:12.675496

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4246ddc8b889"
down_revision: Union[str, Sequence[str], None] = "2f3e386f9b02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - remove deprecated slack_channel column."""
    # Drop the deprecated slack_channel column from projects table
    # The new slack_channel_ids field in resource_mappings table replaces this
    op.drop_column("projects", "slack_channel")


def downgrade() -> None:
    """Downgrade schema - restore slack_channel column."""
    # Re-add the column if we need to rollback
    op.add_column(
        "projects", sa.Column("slack_channel", sa.String(length=255), nullable=True)
    )
