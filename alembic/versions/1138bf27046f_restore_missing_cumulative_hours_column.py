"""restore_missing_cumulative_hours_column

Revision ID: 1138bf27046f
Revises: 52385c70838c
Create Date: 2025-11-21 14:29:29.481821

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "1138bf27046f"
down_revision: Union[str, Sequence[str], None] = "52385c70838c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
