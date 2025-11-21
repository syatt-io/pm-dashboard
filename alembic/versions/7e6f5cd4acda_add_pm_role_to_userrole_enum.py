"""Add PM role to UserRole enum

Revision ID: 7e6f5cd4acda
Revises: 6cbb4a8e1f96
Create Date: 2025-11-20 14:34:42.818419

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7e6f5cd4acda"
down_revision: Union[str, Sequence[str], None] = "6cbb4a8e1f96"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add 'pm' value to userrole enum
    # PostgreSQL requires ALTER TYPE for enum additions
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'pm'")


def downgrade() -> None:
    """Downgrade schema."""
    # Note: PostgreSQL doesn't support removing enum values directly
    # This would require recreating the enum type, which is complex
    # For now, we'll leave the value in place (it won't break anything)
    pass
