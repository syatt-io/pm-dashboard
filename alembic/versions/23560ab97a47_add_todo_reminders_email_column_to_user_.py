"""Add todo_reminders_email column to user_notification_preferences

Revision ID: 23560ab97a47
Revises: 8d68a6f64245
Create Date: 2025-11-18 20:49:41.857174

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "23560ab97a47"
down_revision: Union[str, Sequence[str], None] = "8d68a6f64245"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add todo_reminders_email column to user_notification_preferences table
    op.add_column(
        "user_notification_preferences",
        sa.Column(
            "todo_reminders_email", sa.Boolean(), nullable=False, server_default="false"
        ),
    )
    # Remove server_default after column is created
    op.alter_column(
        "user_notification_preferences", "todo_reminders_email", server_default=None
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Remove todo_reminders_email column from user_notification_preferences table
    op.drop_column("user_notification_preferences", "todo_reminders_email")
