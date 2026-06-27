"""add auto_update to bots

Revision ID: a3f2e8b1c4d5
Revises: c4e8f1a2b3d6
Create Date: 2026-06-27 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a3f2e8b1c4d5"
down_revision: Union[str, Sequence[str], None] = "c4e8f1a2b3d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "bots",
        sa.Column("auto_update", sa.Boolean(), nullable=False, server_default=sa.false()),
        schema="orkaflow",
    )


def downgrade() -> None:
    op.drop_column("bots", "auto_update", schema="orkaflow")
