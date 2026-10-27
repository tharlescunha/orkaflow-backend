"""Saúde das credenciais: status na credencial e motivo da pausa no agendamento

Revision ID: e4a7c9d1b3f5
Revises: d3f5b7c9e1a2
Create Date: 2026-10-27 15:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e4a7c9d1b3f5"
down_revision: Union[str, Sequence[str], None] = "d3f5b7c9e1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Só colunas novas com valor padrão: nada existente muda de comportamento.
    with op.batch_alter_table("credentials") as batch:
        batch.add_column(
            sa.Column("status", sa.String(length=30), nullable=False, server_default="nao_verificada")
        )
        batch.add_column(sa.Column("status_reason", sa.String(length=300), nullable=True))
        batch.add_column(sa.Column("status_updated_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("status_task_id", sa.Integer(), nullable=True))

    with op.batch_alter_table("schedules") as batch:
        batch.add_column(sa.Column("paused_reason", sa.String(length=60), nullable=True))
        batch.add_column(sa.Column("paused_credential_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("schedules") as batch:
        batch.drop_column("paused_credential_id")
        batch.drop_column("paused_reason")

    with op.batch_alter_table("credentials") as batch:
        batch.drop_column("status_task_id")
        batch.drop_column("status_updated_at")
        batch.drop_column("status_reason")
        batch.drop_column("status")
