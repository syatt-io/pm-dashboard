"""Add project_forecasting_config table for date-bounded forecasting

Revision ID: 2fc716c492ed
Revises: 4bd5844fce28
Create Date: 2025-11-12 17:08:27.392164

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2fc716c492ed"
down_revision: Union[str, Sequence[str], None] = "4bd5844fce28"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "project_forecasting_config",
        sa.Column("project_key", sa.String(length=50), nullable=False),
        sa.Column("forecasting_start_date", sa.Date(), nullable=False),
        sa.Column("forecasting_end_date", sa.Date(), nullable=False),
        sa.Column(
            "include_in_forecasting",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("project_type", sa.String(length=50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("project_key"),
    )
    op.create_index(
        op.f("ix_project_forecasting_config_include_in_forecasting"),
        "project_forecasting_config",
        ["include_in_forecasting"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_project_forecasting_config_include_in_forecasting"),
        table_name="project_forecasting_config",
    )
    op.drop_table("project_forecasting_config")
