"""add unique open task guards

Revision ID: 2c8e1f4a6b90
Revises: 9b1a6c4f2d10
Create Date: 2026-06-26 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op


revision: str = "2c8e1f4a6b90"
down_revision: str | Sequence[str] | None = "9b1a6c4f2d10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


OPEN_STATUSES = "'waiting', 'scheduled', 'ready', 'running', 'stop_requested'"


def upgrade() -> None:
    op.execute(
        f"""
        IF EXISTS (
            SELECT 1
            FROM tasks
            WHERE status IN ({OPEN_STATUSES})
            GROUP BY automation_id
            HAVING COUNT(*) > 1
        )
        BEGIN
            THROW 51000, 'Existem automacoes com mais de uma task aberta. Limpe a fila antes desta migration.', 1;
        END
        """
    )

    op.execute(
        f"""
        IF EXISTS (
            SELECT 1
            FROM tasks
            WHERE runner_id IS NOT NULL
              AND status IN ({OPEN_STATUSES})
            GROUP BY runner_id
            HAVING COUNT(*) > 1
        )
        BEGIN
            THROW 51000, 'Existem runners com mais de uma task aberta vinculada. Limpe a fila antes desta migration.', 1;
        END
        """
    )

    op.execute(
        f"""
        IF NOT EXISTS (
            SELECT 1
            FROM sys.indexes
            WHERE name = 'uq_tasks_one_open_per_automation'
              AND object_id = OBJECT_ID('tasks')
        )
        BEGIN
            CREATE UNIQUE INDEX uq_tasks_one_open_per_automation
            ON tasks (automation_id)
            WHERE status IN ({OPEN_STATUSES});
        END
        """
    )

    op.execute(
        f"""
        IF NOT EXISTS (
            SELECT 1
            FROM sys.indexes
            WHERE name = 'uq_tasks_one_open_per_runner'
              AND object_id = OBJECT_ID('tasks')
        )
        BEGIN
            CREATE UNIQUE INDEX uq_tasks_one_open_per_runner
            ON tasks (runner_id)
            WHERE runner_id IS NOT NULL
              AND status IN ({OPEN_STATUSES});
        END
        """
    )


def downgrade() -> None:
    op.execute(
        """
        IF EXISTS (
            SELECT 1
            FROM sys.indexes
            WHERE name = 'uq_tasks_one_open_per_runner'
              AND object_id = OBJECT_ID('tasks')
        )
        BEGIN
            DROP INDEX uq_tasks_one_open_per_runner ON tasks;
        END
        """
    )
    op.execute(
        """
        IF EXISTS (
            SELECT 1
            FROM sys.indexes
            WHERE name = 'uq_tasks_one_open_per_automation'
              AND object_id = OBJECT_ID('tasks')
        )
        BEGIN
            DROP INDEX uq_tasks_one_open_per_automation ON tasks;
        END
        """
    )
