"""add epic auto update setting

Revision ID: 4ea73a1de7f0
Revises: 9e5bee700dff
Create Date: 2025-11-08 11:28:17.829053

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4ea73a1de7f0"
down_revision: Union[str, Sequence[str], None] = "9e5bee700dff"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add epic_auto_update_enabled column to system_settings table
    op.add_column(
        "system_settings",
        sa.Column(
            "epic_auto_update_enabled",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Remove epic_auto_update_enabled column
    op.drop_column("system_settings", "epic_auto_update_enabled")
