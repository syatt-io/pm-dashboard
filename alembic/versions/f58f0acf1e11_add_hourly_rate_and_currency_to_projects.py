"""Add hourly_rate and currency to projects

Revision ID: f58f0acf1e11
Revises: 1138bf27046f
Create Date: 2025-11-22 11:59:31.027114

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f58f0acf1e11"
down_revision: Union[str, Sequence[str], None] = "1138bf27046f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add billing configuration columns to projects table
    op.add_column("projects", sa.Column("hourly_rate", sa.Float(), nullable=True))
    op.add_column("projects", sa.Column("currency", sa.String(length=3), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove billing configuration columns from projects table
    op.drop_column("projects", "currency")
    op.drop_column("projects", "hourly_rate")
