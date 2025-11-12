"""Add notification preferences to users

Revision ID: d8101d785508
Revises: 9f21026006cc
Create Date: 2025-11-04 17:29:59.714357

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d8101d785508"
down_revision: Union[str, Sequence[str], None] = "9f21026006cc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add notification preference columns to users table with default values
    # Check if columns already exist to avoid errors
    connection = op.get_bind()
    inspector = sa.inspect(connection)

    # Get existing columns
    existing_columns = [col["name"] for col in inspector.get_columns("users")]

    # Add columns if they don't exist (PostgreSQL compatible)
    if "notify_daily_todo_digest" not in existing_columns:
        op.add_column(
            "users",
            sa.Column(
                "notify_daily_todo_digest",
                sa.Boolean(),
                nullable=False,
                server_default="true",
            ),
        )
    if "notify_project_hours_forecast" not in existing_columns:
        op.add_column(
            "users",
            sa.Column(
                "notify_project_hours_forecast",
                sa.Boolean(),
                nullable=False,
                server_default="true",
            ),
        )


def downgrade() -> None:
    """Downgrade schema."""
    # Remove notification preference columns from users table
    op.drop_column("users", "notify_project_hours_forecast")
    op.drop_column("users", "notify_daily_todo_digest")
