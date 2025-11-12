"""add_epic_budgets_and_project_dates

Revision ID: 8e244eaab655
Revises: 4ea73a1de7f0
Create Date: 2025-11-09 10:13:26.072330

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8e244eaab655"
down_revision: Union[str, Sequence[str], None] = "4ea73a1de7f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Get existing tables and columns
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    # Add columns to projects table only if they don't exist
    if "projects" in existing_tables:
        columns = [col["name"] for col in inspector.get_columns("projects")]

        if "start_date" not in columns:
            op.add_column("projects", sa.Column("start_date", sa.Date(), nullable=True))

        if "launch_date" not in columns:
            op.add_column(
                "projects", sa.Column("launch_date", sa.Date(), nullable=True)
            )

        if "show_budget_tab" not in columns:
            op.add_column(
                "projects",
                sa.Column(
                    "show_budget_tab",
                    sa.Boolean(),
                    nullable=True,
                    server_default="true",
                ),
            )

    # Create epic_budgets table only if it doesn't exist
    if "epic_budgets" not in existing_tables:
        op.create_table(
            "epic_budgets",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("project_key", sa.String(length=50), nullable=False),
            sa.Column("epic_key", sa.String(length=50), nullable=False),
            sa.Column("epic_summary", sa.String(length=500), nullable=True),
            sa.Column(
                "estimated_hours", sa.Numeric(precision=10, scale=2), nullable=False
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=True,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=True,
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "project_key", "epic_key", name="uq_epic_budgets_project_epic"
            ),
        )
        op.create_index(
            op.f("ix_epic_budgets_project_key"),
            "epic_budgets",
            ["project_key"],
            unique=False,
        )
        op.create_index(
            op.f("ix_epic_budgets_epic_key"), "epic_budgets", ["epic_key"], unique=False
        )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes and table
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "epic_budgets" in existing_tables:
        op.drop_index(op.f("ix_epic_budgets_epic_key"), table_name="epic_budgets")
        op.drop_index(op.f("ix_epic_budgets_project_key"), table_name="epic_budgets")
        op.drop_table("epic_budgets")

    # Drop columns from projects table
    if "projects" in existing_tables:
        columns = [col["name"] for col in inspector.get_columns("projects")]

        if "show_budget_tab" in columns:
            op.drop_column("projects", "show_budget_tab")

        if "launch_date" in columns:
            op.drop_column("projects", "launch_date")

        if "start_date" in columns:
            op.drop_column("projects", "start_date")
