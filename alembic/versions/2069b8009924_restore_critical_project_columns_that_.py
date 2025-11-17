"""Restore critical project columns that were incorrectly dropped

Revision ID: 2069b8009924
Revises: 2d04705c7c32
Create Date: 2025-11-16 13:20:29.956556

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2069b8009924"
down_revision: Union[str, Sequence[str], None] = "2d04705c7c32"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Restore columns that were incorrectly dropped from projects table."""
    # Add back all the columns that were dropped
    op.execute(
        """
        DO $$
        BEGIN
            -- project_work_type
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'projects' AND column_name = 'project_work_type'
            ) THEN
                ALTER TABLE projects ADD COLUMN project_work_type VARCHAR(50) DEFAULT 'project-based';
            END IF;

            -- total_hours
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'projects' AND column_name = 'total_hours'
            ) THEN
                ALTER TABLE projects ADD COLUMN total_hours DOUBLE PRECISION DEFAULT 0;
            END IF;

            -- cumulative_hours
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'projects' AND column_name = 'cumulative_hours'
            ) THEN
                ALTER TABLE projects ADD COLUMN cumulative_hours DOUBLE PRECISION DEFAULT 0;
            END IF;

            -- weekly_meeting_day
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'projects' AND column_name = 'weekly_meeting_day'
            ) THEN
                ALTER TABLE projects ADD COLUMN weekly_meeting_day VARCHAR(20);
            END IF;

            -- retainer_hours
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'projects' AND column_name = 'retainer_hours'
            ) THEN
                ALTER TABLE projects ADD COLUMN retainer_hours DOUBLE PRECISION DEFAULT 0;
            END IF;

            -- send_meeting_emails
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'projects' AND column_name = 'send_meeting_emails'
            ) THEN
                ALTER TABLE projects ADD COLUMN send_meeting_emails BOOLEAN DEFAULT false;
            END IF;

            -- start_date
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'projects' AND column_name = 'start_date'
            ) THEN
                ALTER TABLE projects ADD COLUMN start_date DATE;
            END IF;

            -- launch_date
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'projects' AND column_name = 'launch_date'
            ) THEN
                ALTER TABLE projects ADD COLUMN launch_date DATE;
            END IF;

            -- description
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'projects' AND column_name = 'description'
            ) THEN
                ALTER TABLE projects ADD COLUMN description TEXT;
            END IF;

            -- lead
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'projects' AND column_name = 'lead'
            ) THEN
                ALTER TABLE projects ADD COLUMN lead VARCHAR(255);
            END IF;

            -- show_budget_tab
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'projects' AND column_name = 'show_budget_tab'
            ) THEN
                ALTER TABLE projects ADD COLUMN show_budget_tab BOOLEAN DEFAULT true;
            END IF;

            -- todo_items.source (also dropped by same migration)
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'todo_items' AND column_name = 'source'
            ) THEN
                ALTER TABLE todo_items ADD COLUMN source VARCHAR(100);
            END IF;
        END $$;
    """
    )

    # Recreate indexes
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_projects_project_work_type ON projects(project_work_type);
    """
    )


def downgrade() -> None:
    """Remove the restored columns (NOT RECOMMENDED - data loss!)."""
    op.drop_column("todo_items", "source")
    op.drop_index("idx_projects_project_work_type", table_name="projects")
    op.drop_column("projects", "show_budget_tab")
    op.drop_column("projects", "lead")
    op.drop_column("projects", "description")
    op.drop_column("projects", "launch_date")
    op.drop_column("projects", "start_date")
    op.drop_column("projects", "send_meeting_emails")
    op.drop_column("projects", "retainer_hours")
    op.drop_column("projects", "weekly_meeting_day")
    op.drop_column("projects", "cumulative_hours")
    op.drop_column("projects", "total_hours")
    op.drop_column("projects", "project_work_type")
