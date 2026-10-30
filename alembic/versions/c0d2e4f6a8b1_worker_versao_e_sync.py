"""Versão do worker por máquina, configurações do sistema e tela Sync

Revision ID: c0d2e4f6a8b1
Revises: b9c1d3e5f7a8
Create Date: 2026-10-30 16:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c0d2e4f6a8b1"
down_revision: Union[str, Sequence[str], None] = "b9c1d3e5f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NOW = sa.text("sysdatetimeoffset()")


def upgrade() -> None:
    # Colunas novas, todas opcionais ou com padrão: nada existente muda de comportamento.
    with op.batch_alter_table("runners") as batch:
        batch.add_column(sa.Column("worker_commit", sa.String(length=40), nullable=True))
        batch.add_column(sa.Column("worker_version", sa.String(length=30), nullable=True))
        batch.add_column(sa.Column("worker_update_requested_at", sa.DateTime(timezone=True), nullable=True))

    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("sync_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")))

    op.create_table(
        "system_settings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=_NOW),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=_NOW),
    )
    op.create_index("ix_system_settings_key", "system_settings", ["key"], unique=True)

    op.create_table(
        "sync_checks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("server", sa.String(length=120), nullable=True),
        sa.Column("project", sa.String(length=120), nullable=True),
        sa.Column("interval_seconds", sa.Integer(), nullable=False, server_default=sa.text("60")),
        sa.Column("expected_status", sa.Integer(), nullable=True),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default=sa.text("10")),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("last_ping_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_ok", sa.Boolean(), nullable=True),
        sa.Column("last_status_code", sa.Integer(), nullable=True),
        sa.Column("last_latency_ms", sa.Integer(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=_NOW),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=_NOW),
    )
    op.create_index("ix_sync_checks_user_id", "sync_checks", ["user_id"])

    op.create_table(
        "sync_automation_picks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("automation_id", sa.Integer(), sa.ForeignKey("automations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=_NOW),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=_NOW),
        sa.UniqueConstraint("user_id", "automation_id", name="uq_sync_pick_user_automation"),
    )
    op.create_index("ix_sync_automation_picks_user_id", "sync_automation_picks", ["user_id"])
    op.create_index("ix_sync_automation_picks_automation_id", "sync_automation_picks", ["automation_id"])


def downgrade() -> None:
    op.drop_table("sync_automation_picks")
    op.drop_table("sync_checks")
    op.drop_index("ix_system_settings_key", table_name="system_settings")
    op.drop_table("system_settings")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("sync_enabled")
    with op.batch_alter_table("runners") as batch:
        batch.drop_column("worker_update_requested_at")
        batch.drop_column("worker_version")
        batch.drop_column("worker_commit")
