"""Máquina: usuário de acesso (cadastrado) e usuário do Windows (informado pelo worker)

Revision ID: f7a9b1c3d5e6
Revises: e6a8b0c2d4f5
Create Date: 2026-10-28 10:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f7a9b1c3d5e6"
down_revision: Union[str, Sequence[str], None] = "e6a8b0c2d4f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Duas colunas opcionais; nada existente muda de comportamento.
    with op.batch_alter_table("runners") as batch:
        batch.add_column(sa.Column("login_user", sa.String(length=150), nullable=True))
        batch.add_column(sa.Column("os_user", sa.String(length=150), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("runners") as batch:
        batch.drop_column("os_user")
        batch.drop_column("login_user")
