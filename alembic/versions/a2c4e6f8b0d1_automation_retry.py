"""Retentativa automática por agendamento (quantas vezes, intervalo, em quais falhas)

Revision ID: a2c4e6f8b0d1
Revises: f1b3d5e7a9c2
Create Date: 2026-10-27 19:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a2c4e6f8b0d1"
down_revision: Union[str, Sequence[str], None] = "f1b3d5e7a9c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Só colunas novas com valor padrão (0 = sem retentativa): nada existente muda de comportamento.
    with op.batch_alter_table("schedules") as batch:
        batch.add_column(sa.Column("retry_max", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("retry_delay_seconds", sa.Integer(), nullable=False, server_default="300"))
        batch.add_column(sa.Column("retry_on_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("schedules") as batch:
        batch.drop_column("retry_on_json")
        batch.drop_column("retry_delay_seconds")
        batch.drop_column("retry_max")
