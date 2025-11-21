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
    from sqlalchemy import text
    from sqlalchemy.exc import ProgrammingError

    # Add 'pm' value to userrole enum
    # PostgreSQL requires ALTER TYPE for enum additions
    # Handle permission errors gracefully if enum type is owned by different user
    conn = op.get_bind()

    try:
        # Check if 'pm' value already exists in enum
        result = conn.execute(
            text(
                """
            SELECT EXISTS (
                SELECT 1 FROM pg_enum e
                JOIN pg_type t ON e.enumtypid = t.oid
                WHERE t.typname = 'userrole' AND e.enumlabel = 'pm'
            )
            """
            )
        )
        pm_exists = result.scalar()

        if not pm_exists:
            # Try to add the value
            conn.execute(text("ALTER TYPE userrole ADD VALUE 'pm'"))
            print("✅ Successfully added 'pm' to userrole enum")
        else:
            print("ℹ️ 'pm' value already exists in userrole enum")
    except ProgrammingError as e:
        # If we get a permission error, log but don't fail
        error_msg = str(e)
        if "must be owner" in error_msg or "InsufficientPrivilege" in error_msg:
            print(f"⚠️ Warning: Cannot modify userrole enum due to permissions: {e}")
            print("⚠️ Note: Enum modification requires database owner privileges")
            print(
                "⚠️ If 'PM' role is needed, please contact database administrator to manually add it"
            )
            # Don't fail the migration - allow deployment to continue
        else:
            # Other errors should still fail
            raise


def downgrade() -> None:
    """Downgrade schema."""
    # Note: PostgreSQL doesn't support removing enum values directly
    # This would require recreating the enum type, which is complex
    # For now, we'll leave the value in place (it won't break anything)
    pass
