"""Maestro: progresso da task e campo "robô lê o arquivo da task por argumento" no bot

Revision ID: d5f7a9b1c3e4
Revises: c4e6a8b0d2f3
Create Date: 2026-10-28 09:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d5f7a9b1c3e4"
down_revision: Union[str, Sequence[str], None] = "c4e6a8b0d2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Só colunas novas. tasks.progress_* ficam nulas até o robô (via maestro) mandar etapa;
    # bots.reads_task_file_arg nasce TRUE para todos os bots atuais: o worker continua passando
    # o caminho do JSON por argumento exatamente como hoje.
    with op.batch_alter_table("tasks") as batch:
        batch.add_column(sa.Column("progress_current", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("progress_total", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("progress_text", sa.String(length=200), nullable=True))

    with op.batch_alter_table("bots") as batch:
        batch.add_column(
            sa.Column("reads_task_file_arg", sa.Boolean(), nullable=False, server_default=sa.text("1"))
        )


def downgrade() -> None:
    with op.batch_alter_table("bots") as batch:
        batch.drop_column("reads_task_file_arg")
    with op.batch_alter_table("tasks") as batch:
        batch.drop_column("progress_text")
        batch.drop_column("progress_total")
        batch.drop_column("progress_current")
