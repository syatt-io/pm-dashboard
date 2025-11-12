"""Add project_keywords table

Revision ID: 9391760ed2b5
Revises: 93848da7ee69
Create Date: 2025-11-09 23:35:13.543352

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9391760ed2b5"
down_revision: Union[str, Sequence[str], None] = "93848da7ee69"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create project_keywords table
    op.create_table(
        "project_keywords",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_key", sa.String(50), nullable=False, index=True),
        sa.Column("keyword", sa.String(255), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")
        ),
        sa.ForeignKeyConstraint(["project_key"], ["projects.key"], ondelete="CASCADE"),
        sa.UniqueConstraint("project_key", "keyword", name="uq_project_keyword"),
    )

    # Add source column to todo_items (nullable to avoid breaking existing data)
    op.add_column("todo_items", sa.Column("source", sa.String(100), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove source column from todo_items
    op.drop_column("todo_items", "source")

    # Drop project_keywords table
    op.drop_table("project_keywords")
