"""runners.deleted_at (remover runner) e tabela runner_log_lines (tela de Logs)

Revision ID: b9d1f3a5c7e2
Revises: a8c0e2f4b6d9
Create Date: 2026-10-22 16:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b9d1f3a5c7e2"
down_revision: Union[str, Sequence[str], None] = "a8c0e2f4b6d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Coluna nova e nula: nenhum runner existente muda (todos continuam visíveis).
    op.add_column("runners", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_runners_deleted_at", "runners", ["deleted_at"], unique=False)

    op.create_table(
        "runner_log_lines",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("runner_id", sa.Integer(), nullable=False),
        sa.Column("logged_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("level", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.text("sysdatetimeoffset()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["runner_id"], ["runners.id"],
            name="fk_runner_log_lines_runner_id_runners",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_runner_log_lines"),
    )
    op.create_index("ix_runner_log_lines_runner_id_id", "runner_log_lines", ["runner_id", "id"], unique=False)
    op.create_index("ix_runner_log_lines_received_at", "runner_log_lines", ["received_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_runner_log_lines_received_at", table_name="runner_log_lines")
    op.drop_index("ix_runner_log_lines_runner_id_id", table_name="runner_log_lines")
    op.drop_table("runner_log_lines")
    op.drop_index("ix_runners_deleted_at", table_name="runners")
    op.drop_column("runners", "deleted_at")
