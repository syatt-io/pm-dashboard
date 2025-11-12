"""restore_missing_tables_and_columns_post_incident

Revision ID: cf14025f87ec
Revises: def376e3c089
Create Date: 2025-11-10 08:24:34.889774

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "cf14025f87ec"
down_revision: Union[str, Sequence[str], None] = "def376e3c089"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Restore missing tables and columns after 2025-11-09 incident.

    This migration documents the manual fixes applied to restore:
    1. vector-sync-status table (dropped in incident)
    2. cumulative_hours column in projects table (missing in production)
    3. Various projects table columns (project_work_type, total_hours, etc.)

    NOTE: These changes were applied manually to both local and production
    databases on 2025-11-10. This migration serves as documentation and
    ensures consistency for new environments.
    """
    # Create vector-sync-status table if it doesn't exist
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS "vector-sync-status" (
            source TEXT NOT NULL PRIMARY KEY,
            last_sync TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # Add cumulative_hours to projects table if it doesn't exist
    # Using raw SQL with IF NOT EXISTS check
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'projects' AND column_name = 'cumulative_hours'
            ) THEN
                ALTER TABLE projects ADD COLUMN cumulative_hours NUMERIC(10, 2) DEFAULT 0;
            END IF;
        END $$;
    """
    )

    # Ensure other critical columns exist in projects table
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
                ALTER TABLE projects ADD COLUMN total_hours NUMERIC(10, 2) DEFAULT 0;
            END IF;

            -- retainer_hours
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'projects' AND column_name = 'retainer_hours'
            ) THEN
                ALTER TABLE projects ADD COLUMN retainer_hours NUMERIC(10, 2) DEFAULT 0;
            END IF;

            -- weekly_meeting_day
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'projects' AND column_name = 'weekly_meeting_day'
            ) THEN
                ALTER TABLE projects ADD COLUMN weekly_meeting_day TEXT;
            END IF;

            -- send_meeting_emails
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'projects' AND column_name = 'send_meeting_emails'
            ) THEN
                ALTER TABLE projects ADD COLUMN send_meeting_emails BOOLEAN DEFAULT FALSE;
            END IF;

            -- description
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'projects' AND column_name = 'description'
            ) THEN
                ALTER TABLE projects ADD COLUMN description TEXT;
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
        END $$;
    """
    )


def downgrade() -> None:
    """Downgrade schema.

    WARNING: This will drop the vector-sync-status table and remove columns
    from the projects table. Only use in development/testing environments.
    """
    # Drop vector-sync-status table
    op.execute('DROP TABLE IF EXISTS "vector-sync-status"')

    # Remove columns from projects table
    op.execute(
        """
        ALTER TABLE projects
        DROP COLUMN IF EXISTS cumulative_hours,
        DROP COLUMN IF EXISTS launch_date,
        DROP COLUMN IF EXISTS start_date,
        DROP COLUMN IF EXISTS description,
        DROP COLUMN IF EXISTS send_meeting_emails,
        DROP COLUMN IF EXISTS weekly_meeting_day,
        DROP COLUMN IF EXISTS retainer_hours,
        DROP COLUMN IF EXISTS total_hours,
        DROP COLUMN IF EXISTS project_work_type
    """
    )
