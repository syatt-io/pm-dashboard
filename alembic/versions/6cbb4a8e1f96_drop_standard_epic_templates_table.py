"""Drop standard_epic_templates table

Revision ID: 6cbb4a8e1f96
Revises: 7a2ca1bc7707
Create Date: 2025-11-20 13:16:39.797644

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6cbb4a8e1f96"
down_revision: Union[str, Sequence[str], None] = "7a2ca1bc7707"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Drop the standard_epic_templates table if it exists
    op.execute("DROP TABLE IF EXISTS standard_epic_templates CASCADE")


def downgrade() -> None:
    """Downgrade schema."""
    # Recreate the standard_epic_templates table
    op.create_table(
        "standard_epic_templates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("typical_hours_min", sa.Integer(), nullable=True),
        sa.Column("typical_hours_max", sa.Integer(), nullable=True),
        sa.Column("order", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(
        "ix_standard_epic_templates_name",
        "standard_epic_templates",
        ["name"],
        unique=False,
    )
