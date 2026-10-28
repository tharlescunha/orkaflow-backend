"""Ambientes de Git: token por prefixo de URL (Configurações)

Revision ID: b9c1d3e5f7a8
Revises: a8b0c2d4e6f7
Create Date: 2026-10-28 18:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b9c1d3e5f7a8"
down_revision: Union[str, Sequence[str], None] = "a8b0c2d4e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "git_environments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("url_prefix", sa.String(length=500), nullable=False),
        sa.Column("username", sa.String(length=150), nullable=True),
        sa.Column("token_encrypted", sa.Text(), nullable=False),
        sa.Column("token_hint", sa.String(length=12), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("sysdatetimeoffset()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("sysdatetimeoffset()")),
    )
    op.create_index("ix_git_environments_url_prefix", "git_environments", ["url_prefix"], unique=True)
    op.create_index("ix_git_environments_active", "git_environments", ["active"])


def downgrade() -> None:
    op.drop_index("ix_git_environments_active", table_name="git_environments")
    op.drop_index("ix_git_environments_url_prefix", table_name="git_environments")
    op.drop_table("git_environments")
