"""add unique active lock key

Revision ID: 7f3d2a91c8e4
Revises: 4138c14a08de
Create Date: 2026-06-26 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op


revision: str = "7f3d2a91c8e4"
down_revision: str | Sequence[str] | None = "4138c14a08de"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        IF EXISTS (
            SELECT lock_key
            FROM locks
            WHERE active = 1
              AND released_at IS NULL
            GROUP BY lock_key
            HAVING COUNT(*) > 1
        )
        BEGIN
            THROW 51001, 'Existem locks ativos duplicados. Limpe os locks inconsistentes antes de aplicar esta migration.', 1;
        END
        """
    )

    op.execute(
        """
        IF NOT EXISTS (
            SELECT 1
            FROM sys.indexes
            WHERE name = 'uq_locks_active_lock_key'
              AND object_id = OBJECT_ID('locks')
        )
        BEGIN
            CREATE UNIQUE INDEX uq_locks_active_lock_key
            ON locks (lock_key)
            WHERE active = 1
              AND released_at IS NULL;
        END
        """
    )


def downgrade() -> None:
    op.execute(
        """
        IF EXISTS (
            SELECT 1
            FROM sys.indexes
            WHERE name = 'uq_locks_active_lock_key'
              AND object_id = OBJECT_ID('locks')
        )
        BEGIN
            DROP INDEX uq_locks_active_lock_key ON locks;
        END
        """
    )
