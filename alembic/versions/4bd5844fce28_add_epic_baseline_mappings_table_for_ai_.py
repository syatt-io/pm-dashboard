"""Add epic baseline mappings table for AI-powered epic grouping

Revision ID: 4bd5844fce28
Revises: 493d9ec0f6b3
Create Date: 2025-11-12 14:17:06.581753

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4bd5844fce28"
down_revision: Union[str, Sequence[str], None] = "493d9ec0f6b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - create epic_baseline_mappings table."""
    op.create_table(
        "epic_baseline_mappings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("epic_summary", sa.String(length=500), nullable=False),
        sa.Column("baseline_category", sa.String(length=200), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("created_by", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "epic_summary", name="uq_epic_baseline_mapping_epic_summary"
        ),
    )
    op.create_index(
        "ix_epic_baseline_mappings_epic_summary",
        "epic_baseline_mappings",
        ["epic_summary"],
        unique=False,
    )
    op.create_index(
        "ix_epic_baseline_mappings_baseline_category",
        "epic_baseline_mappings",
        ["baseline_category"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema - drop epic_baseline_mappings table."""
    op.drop_index(
        "ix_epic_baseline_mappings_baseline_category",
        table_name="epic_baseline_mappings",
    )
    op.drop_index(
        "ix_epic_baseline_mappings_epic_summary", table_name="epic_baseline_mappings"
    )
    op.drop_table("epic_baseline_mappings")
