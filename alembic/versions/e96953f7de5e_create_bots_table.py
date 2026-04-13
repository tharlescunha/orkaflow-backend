"""add execution_mode to bots

Revision ID: e96953f7de5e
Revises: 06ef2dd0892f
Create Date: 2026-04-11 21:19:44.543608
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e96953f7de5e"
down_revision: Union[str, Sequence[str], None] = "06ef2dd0892f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "bots",
        sa.Column(
            "execution_mode",
            sa.String(length=20),
            nullable=False,
            server_default="background",
        ),
    )

    op.create_index(
        op.f("ix_bots_execution_mode"),
        "bots",
        ["execution_mode"],
        unique=False,
    )

    op.alter_column("bots", "execution_mode", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_bots_execution_mode"), table_name="bots")
    op.drop_column("bots", "execution_mode")
    