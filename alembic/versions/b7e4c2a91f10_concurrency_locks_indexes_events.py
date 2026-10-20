"""concurrency: N tasks por runner, runtime event extra, schedule last_error/last_skipped

Revision ID: b7e4c2a91f10
Revises: a3f2e8b1c4d5
Create Date: 2026-10-20 12:00:00.000000

Reparentada sobre a revisão de produção a3f2e8b1c4d5 (auto_update em bots).

O que NÃO está aqui de propósito (já existe nas migrations de junho/2026 aplicadas em produção):
- índice único de lock ativo por chave: 7f3d2a91c8e4 (uq_locks_active_lock_key). Aquela migration
  aborta (THROW) se existirem locks ativos duplicados, então a limpeza de duplicados não é
  necessária e nenhum UPDATE/DELETE de dados é feito aqui.
- índices de fila/runner/status em tasks: 9b1a6c4f2d10 (ix_tasks_queue_dispatch, ix_tasks_runner_open ...)
  e 9d4b7c2e1a30.

O que faz (aditivo e seguro para dados existentes):
1) Remove o índice único uq_tasks_one_open_per_runner (2c8e1f4a6b90), que limitava a 1 task aberta
   por runner e é incompatível com N tasks BACKGROUND + 1 FOREGROUND por runner. Só remove um índice
   (nenhum dado é alterado). O índice único por automação (uq_tasks_one_open_per_automation) é MANTIDO.
   A consulta por runner continua coberta por ix_tasks_runner_open (não único).
2) worker_runtime_events.extra_json (TEXT NULL).
3) schedules.last_error, last_skipped_reason (TEXT NULL) e last_skipped_at (DATETIMEOFFSET NULL).
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "b7e4c2a91f10"
down_revision: str | Sequence[str] | None = "a3f2e8b1c4d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


OPEN_STATUSES = "'waiting', 'scheduled', 'ready', 'running', 'stop_requested'"


def upgrade() -> None:
    # 1) Regra nova: várias tasks abertas por runner (capacidade controlada pela aplicação).
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

    # 2) Eventos de runtime: dados extras livres.
    op.add_column("worker_runtime_events", sa.Column("extra_json", sa.Text(), nullable=True))

    # 3) Schedules: motivo de erro/descarte sem mudar o status para ERROR.
    op.add_column("schedules", sa.Column("last_error", sa.Text(), nullable=True))
    op.add_column("schedules", sa.Column("last_skipped_reason", sa.Text(), nullable=True))
    op.add_column("schedules", sa.Column("last_skipped_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("schedules", "last_skipped_at")
    op.drop_column("schedules", "last_skipped_reason")
    op.drop_column("schedules", "last_error")
    op.drop_column("worker_runtime_events", "extra_json")

    # Recria a regra antiga (1 task aberta por runner). Falha se já houver mais de uma
    # task aberta por runner (o CREATE UNIQUE INDEX acusa o dado conflitante).
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
