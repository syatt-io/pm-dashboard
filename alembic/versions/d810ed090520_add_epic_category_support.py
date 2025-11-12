"""Add epic category support

Revision ID: d810ed090520
Revises: cf14025f87ec
Create Date: 2025-11-11 09:33:34.947920

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d810ed090520"
down_revision: Union[str, Sequence[str], None] = "cf14025f87ec"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add epic_category column to epic_hours table (nullable for existing records)
    op.add_column(
        "epic_hours", sa.Column("epic_category", sa.String(100), nullable=True)
    )

    # Add index on epic_category for filtering performance
    op.create_index("ix_epic_hours_category", "epic_hours", ["epic_category"])

    # Create epic_category_mappings table
    op.create_table(
        "epic_category_mappings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("epic_key", sa.String(100), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("epic_key", name="uq_epic_category_mapping_epic_key"),
    )

    # Add index on epic_key for lookups during sync
    op.create_index(
        "ix_epic_category_mappings_epic_key", "epic_category_mappings", ["epic_key"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop epic_category_mappings table and its indexes
    op.drop_index(
        "ix_epic_category_mappings_epic_key", table_name="epic_category_mappings"
    )
    op.drop_table("epic_category_mappings")

    # Drop epic_category column and its index from epic_hours
    op.drop_index("ix_epic_hours_category", table_name="epic_hours")
    op.drop_column("epic_hours", "epic_category")
