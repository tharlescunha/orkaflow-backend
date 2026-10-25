"""bots.pinned_version_id (Release) e autor/data do commit em bot_versions

Revision ID: c2e4a6b8d0f1
Revises: b9d1f3a5c7e2
Create Date: 2026-10-24 21:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c2e4a6b8d0f1"
down_revision: Union[str, Sequence[str], None] = "b9d1f3a5c7e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Só colunas novas e nulas: nenhum bot muda de versão (nulo = segue a mais nova, como hoje).
    op.add_column("bots", sa.Column("pinned_version_id", sa.Integer(), nullable=True))
    op.create_index("ix_bots_pinned_version_id", "bots", ["pinned_version_id"], unique=False)

    op.add_column("bot_versions", sa.Column("commit_author", sa.String(length=150), nullable=True))
    op.add_column("bot_versions", sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("bot_versions", "committed_at")
    op.drop_column("bot_versions", "commit_author")
    op.drop_index("ix_bots_pinned_version_id", table_name="bots")
    op.drop_column("bots", "pinned_version_id")
