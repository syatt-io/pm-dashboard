"""rename_insight_metadata_to_metadata_json

Revision ID: 0c8e7c36384c
Revises: 3b36763ff547
Create Date: 2025-11-04 23:52:40.567553

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0c8e7c36384c"
down_revision: Union[str, Sequence[str], None] = "3b36763ff547"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename insight_metadata column to metadata_json in proactive_insights table."""
    # Rename column from insight_metadata to metadata_json
    op.alter_column(
        "proactive_insights",
        "insight_metadata",
        new_column_name="metadata_json",
        existing_type=sa.JSON(),
        existing_nullable=True,
    )


def downgrade() -> None:
    """Revert metadata_json column back to insight_metadata."""
    # Rename column from metadata_json back to insight_metadata
    op.alter_column(
        "proactive_insights",
        "metadata_json",
        new_column_name="insight_metadata",
        existing_type=sa.JSON(),
        existing_nullable=True,
    )
