"""add storage_type to bot_versions

Revision ID: 05a6b64d45a3
Revises: ee675d945755
Create Date: 2026-03-24 16:03:23.983376
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '05a6b64d45a3'
down_revision: Union[str, Sequence[str], None] = 'ee675d945755'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "bot_versions",
        sa.Column("storage_type", sa.String(length=50), nullable=True),
        schema="orkaflow",
    )

    op.execute(
        "UPDATE orkaflow.bot_versions SET storage_type = 'local' WHERE storage_type IS NULL"
    )

    op.alter_column(
        "bot_versions",
        "storage_type",
        existing_type=sa.String(length=50),
        nullable=False,
        schema="orkaflow",
    )


def downgrade() -> None:
    op.drop_column("bot_versions", "storage_type", schema="orkaflow")