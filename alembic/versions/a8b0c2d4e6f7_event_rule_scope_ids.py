"""Evento: regra vale para vários bots/automações (scope_ids_json)

Revision ID: a8b0c2d4e6f7
Revises: f7a9b1c3d5e6
Create Date: 2026-10-28 14:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a8b0c2d4e6f7"
down_revision: Union[str, Sequence[str], None] = "f7a9b1c3d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Lista de ids em JSON ("[12, 15]"). Vazio/nulo = só o scope_id de sempre.
    with op.batch_alter_table("event_rules") as batch:
        batch.add_column(sa.Column("scope_ids_json", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("event_rules") as batch:
        batch.drop_column("scope_ids_json")
