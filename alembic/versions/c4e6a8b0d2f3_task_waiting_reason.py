"""Fila com explicação: motivo de espera da task

Revision ID: c4e6a8b0d2f3
Revises: b3d5f7a9c1e2
Create Date: 2026-10-27 23:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4e6a8b0d2f3"
down_revision: Union[str, Sequence[str], None] = "b3d5f7a9c1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Só uma coluna opcional, preenchida pelo dispatcher: nada existente muda de comportamento.
    # (execution_mode "trigger" cabe no varchar(9) atual e a coluna não tem CHECK: sem alteração.)
    with op.batch_alter_table("tasks") as batch:
        batch.add_column(sa.Column("waiting_reason", sa.String(length=300), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("tasks") as batch:
        batch.drop_column("waiting_reason")
