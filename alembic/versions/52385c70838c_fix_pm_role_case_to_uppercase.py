"""Fix PM role case to uppercase

Revision ID: 52385c70838c
Revises: 7e6f5cd4acda
Create Date: 2025-11-20 16:04:23.344770

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "52385c70838c"
down_revision: Union[str, Sequence[str], None] = "7e6f5cd4acda"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Fix PM role to uppercase to match existing enum pattern
    # PostgreSQL doesn't support renaming enum values, so we need to:
    # 1. Create a new enum type with correct values
    # 2. Drop the default constraint (can't auto-cast during type change)
    # 3. Alter the column to use the new type
    # 4. Re-add the default constraint
    # 5. Drop the old type

    # Create new enum type with correct values
    op.execute(
        """
        CREATE TYPE userrole_new AS ENUM ('NO_ACCESS', 'MEMBER', 'PM', 'ADMIN');
    """
    )

    # Drop the default constraint temporarily (can't auto-cast)
    op.execute(
        """
        ALTER TABLE users ALTER COLUMN role DROP DEFAULT;
    """
    )

    # Alter the users table to use the new enum type
    op.execute(
        """
        ALTER TABLE users
        ALTER COLUMN role TYPE userrole_new
        USING (
            CASE role::text
                WHEN 'pm' THEN 'PM'::userrole_new
                ELSE role::text::userrole_new
            END
        );
    """
    )

    # Re-add the default constraint with the new type
    op.execute(
        """
        ALTER TABLE users ALTER COLUMN role SET DEFAULT 'MEMBER'::userrole_new;
    """
    )

    # Drop old enum type and rename new one
    op.execute("DROP TYPE userrole;")
    op.execute("ALTER TYPE userrole_new RENAME TO userrole;")


def downgrade() -> None:
    """Downgrade schema."""
    pass
