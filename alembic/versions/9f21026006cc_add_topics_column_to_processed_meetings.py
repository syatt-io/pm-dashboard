"""add_topics_column_to_processed_meetings

Revision ID: 9f21026006cc
Revises: a8873baa32a5
Create Date: 2025-11-01 20:59:18.348249

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9f21026006cc"
down_revision: Union[str, Sequence[str], None] = "a8873baa32a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add topics column to processed_meetings table."""
    op.add_column("processed_meetings", sa.Column("topics", sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove topics column from processed_meetings table."""
    op.drop_column("processed_meetings", "topics")
