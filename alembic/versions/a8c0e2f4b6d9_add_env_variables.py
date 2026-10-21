"""add env_variables

Revision ID: a8c0e2f4b6d9
Revises: f6b8c0d2e3a5
Create Date: 2026-10-22 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a8c0e2f4b6d9"
down_revision: Union[str, Sequence[str], None] = "f6b8c0d2e3a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Só cria uma tabela nova: nenhuma linha existente é alterada.
    op.create_table(
        "env_variables",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("scope_type", sa.String(length=20), nullable=False),
        sa.Column("scope_id", sa.Integer(), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("is_secret", sa.Boolean(), nullable=False),
        sa.Column("description", sa.String(length=300), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("sysdatetimeoffset()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("sysdatetimeoffset()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_env_variables"),
        sa.UniqueConstraint("scope_type", "scope_id", "name", name="uq_env_variables_scope_name"),
    )
    op.create_index("ix_env_variables_name", "env_variables", ["name"], unique=False)
    op.create_index("ix_env_variables_scope_type", "env_variables", ["scope_type"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_env_variables_scope_type", table_name="env_variables")
    op.drop_index("ix_env_variables_name", table_name="env_variables")
    op.drop_table("env_variables")
