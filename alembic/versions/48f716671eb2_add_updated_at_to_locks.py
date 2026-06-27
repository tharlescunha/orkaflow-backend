"""add updated_at to locks

Revision ID: 48f716671eb2
Revises: cd348b178bab
Create Date: 2026-04-22 14:07:23.205218

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '48f716671eb2'
down_revision: Union[str, Sequence[str], None] = 'cd348b178bab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column(
        "locks",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.execute(
        """
        UPDATE locks
        SET updated_at = created_at
        WHERE updated_at IS NULL
        """
    )

    op.alter_column(
        "locks",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )

    op.execute(
        """
        IF NOT EXISTS (
            SELECT 1
            FROM sys.default_constraints dc
            INNER JOIN sys.columns c
                ON c.default_object_id = dc.object_id
            INNER JOIN sys.tables t
                ON t.object_id = c.object_id
            WHERE t.name = 'locks'
              AND c.name = 'created_at'
        )
        BEGIN
            ALTER TABLE locks
            ADD CONSTRAINT DF_locks_created_at
            DEFAULT GETDATE() FOR created_at
        END
        """
    )

    op.execute(
        """
        IF NOT EXISTS (
            SELECT 1
            FROM sys.default_constraints dc
            INNER JOIN sys.columns c
                ON c.default_object_id = dc.object_id
            INNER JOIN sys.tables t
                ON t.object_id = c.object_id
            WHERE t.name = 'locks'
              AND c.name = 'updated_at'
        )
        BEGIN
            ALTER TABLE locks
            ADD CONSTRAINT DF_locks_updated_at
            DEFAULT GETDATE() FOR updated_at
        END
        """
    )


def downgrade():
    op.execute(
        """
        DECLARE @constraint_name NVARCHAR(200);

        SELECT @constraint_name = dc.name
        FROM sys.default_constraints dc
        INNER JOIN sys.columns c
            ON c.default_object_id = dc.object_id
        INNER JOIN sys.tables t
            ON t.object_id = c.object_id
        WHERE t.name = 'locks'
          AND c.name = 'updated_at';

        IF @constraint_name IS NOT NULL
        BEGIN
            EXEC('ALTER TABLE locks DROP CONSTRAINT ' + @constraint_name)
        END
        """
    )

    op.drop_column("locks", "updated_at")
    
