"""add_missing_source_column_to_todo_items

Revision ID: cd46b52e1b7a
Revises: 2069b8009924
Create Date: 2025-11-17 10:04:18.292866

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cd46b52e1b7a'
down_revision: Union[str, Sequence[str], None] = '2069b8009924'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add missing source column to todo_items table."""
    # Check if column exists before adding (idempotent)
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('todo_items')]

    if 'source' not in columns:
        op.add_column('todo_items', sa.Column('source', sa.String(length=100), nullable=True))
        print("✅ Added 'source' column to todo_items table")
    else:
        print("ℹ️  'source' column already exists in todo_items table")


def downgrade() -> None:
    """Remove source column from todo_items table."""
    # Check if column exists before dropping
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('todo_items')]

    if 'source' in columns:
        op.drop_column('todo_items', 'source')
        print("✅ Removed 'source' column from todo_items table")
    else:
        print("ℹ️  'source' column does not exist in todo_items table")
