"""add pre_steps_json to notification_channels

Revision ID: e5a7b9c1d2f4
Revises: d4f6a8c0b1e3
Create Date: 2026-10-21 20:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5a7b9c1d2f4"
down_revision: Union[str, Sequence[str], None] = "d4f6a8c0b1e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Coluna nova e nula: nenhuma linha existente é alterada.
    op.add_column("notification_channels", sa.Column("pre_steps_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("notification_channels", "pre_steps_json")
