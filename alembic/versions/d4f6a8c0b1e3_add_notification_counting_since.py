"""add counting_since to notification_channels

Revision ID: d4f6a8c0b1e3
Revises: c9d1e5f7a2b4
Create Date: 2026-10-21 19:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4f6a8c0b1e3"
down_revision: Union[str, Sequence[str], None] = "c9d1e5f7a2b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Coluna nova e nula: nenhuma linha existente é alterada.
    op.add_column("notification_channels", sa.Column("counting_since", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("notification_channels", "counting_since")
