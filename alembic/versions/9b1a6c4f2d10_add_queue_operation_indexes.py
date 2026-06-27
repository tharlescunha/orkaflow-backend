"""add queue operation indexes

Revision ID: 9b1a6c4f2d10
Revises: 7f3d2a91c8e4
Create Date: 2026-06-26 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op


revision: str = "9b1a6c4f2d10"
down_revision: str | Sequence[str] | None = "7f3d2a91c8e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


INDEXES = {
    "ix_tasks_queue_dispatch": """
        CREATE INDEX ix_tasks_queue_dispatch
        ON tasks (status, runner_id, requested_start_at, priority DESC, id)
        INCLUDE (automation_id, bot_version_id, dispatch_attempts)
    """,
    "ix_tasks_runner_open": """
        CREATE INDEX ix_tasks_runner_open
        ON tasks (runner_id, status, id)
        INCLUDE (automation_id, last_update_at, runner_claimed_at)
    """,
    "ix_tasks_watchdog_running": """
        CREATE INDEX ix_tasks_watchdog_running
        ON tasks (status, started_at, last_update_at)
        INCLUDE (runner_id, timeout_seconds, stop_requested)
    """,
    "ix_runners_dispatch_available": """
        CREATE INDEX ix_runners_dispatch_available
        ON runners (enabled, status, last_heartbeat, id)
    """,
    "ix_locks_active_lookup": """
        CREATE INDEX ix_locks_active_lookup
        ON locks (active, released_at, lock_key)
        INCLUDE (owner_task_id, runner_id, expires_at)
    """,
    "ix_task_logs_task_sequence": """
        CREATE INDEX ix_task_logs_task_sequence
        ON task_logs (task_id, sequence_number, id)
        INCLUDE (level, source, created_at)
    """,
}


def upgrade() -> None:
    for name, statement in INDEXES.items():
        op.execute(
            f"""
            IF NOT EXISTS (
                SELECT 1
                FROM sys.indexes
                WHERE name = '{name}'
                  AND object_id = OBJECT_ID('{_table_name_from_index(name)}')
            )
            BEGIN
                {statement};
            END
            """
        )


def downgrade() -> None:
    for name in reversed(INDEXES):
        table_name = _table_name_from_index(name)
        op.execute(
            f"""
            IF EXISTS (
                SELECT 1
                FROM sys.indexes
                WHERE name = '{name}'
                  AND object_id = OBJECT_ID('{table_name}')
            )
            BEGIN
                DROP INDEX {name} ON {table_name};
            END
            """
        )


def _table_name_from_index(index_name: str) -> str:
    if index_name.startswith("ix_tasks_"):
        return "tasks"
    if index_name.startswith("ix_runners_"):
        return "runners"
    if index_name.startswith("ix_locks_"):
        return "locks"
    if index_name.startswith("ix_task_logs_"):
        return "task_logs"
    raise ValueError(f"Indice sem tabela mapeada: {index_name}")
