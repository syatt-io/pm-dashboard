"""add_include_context_to_digest_cache

Revision ID: 39ec1875570b
Revises: f8fed84667ca
Create Date: 2025-10-29 14:52:37.211085

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "39ec1875570b"
down_revision: Union[str, Sequence[str], None] = "f8fed84667ca"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add include_context field to project_digest_cache for A/B testing."""
    # Add the include_context column with default False
    op.add_column(
        "project_digest_cache",
        sa.Column("include_context", sa.Boolean(), nullable=False, server_default="0"),
    )

    # Create a composite index for efficient cache lookups
    # This replaces the need for a separate index on just (project_key, days, created_at)
    op.create_index(
        "idx_digest_cache_composite",
        "project_digest_cache",
        ["project_key", "days", "include_context", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Remove include_context field from project_digest_cache."""
    # Drop the composite index
    op.drop_index("idx_digest_cache_composite", table_name="project_digest_cache")

    # Drop the include_context column
    op.drop_column("project_digest_cache", "include_context")
