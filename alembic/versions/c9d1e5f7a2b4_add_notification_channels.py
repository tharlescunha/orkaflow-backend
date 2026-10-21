"""add notification channels and logs

Revision ID: c9d1e5f7a2b4
Revises: b7e4c2a91f10
Create Date: 2026-10-21 18:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c9d1e5f7a2b4"
down_revision: Union[str, Sequence[str], None] = "b7e4c2a91f10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Só cria tabelas novas: nenhuma linha existente é alterada.
    op.create_table(
        "notification_channels",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("url", sa.String(length=1000), nullable=False),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("headers_json", sa.Text(), nullable=True),
        sa.Column("body_template", sa.Text(), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("failure_threshold", sa.Integer(), nullable=False),
        sa.Column("pause_schedule", sa.Boolean(), nullable=False),
        sa.Column("deactivate_automation", sa.Boolean(), nullable=False),
        sa.Column("panel_base_url", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("sysdatetimeoffset()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("sysdatetimeoffset()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_notification_channels"),
    )

    op.create_table(
        "notification_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("channel_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("schedule_id", sa.Integer(), nullable=True),
        sa.Column("schedule_name", sa.String(length=200), nullable=True),
        sa.Column("automation_name", sa.String(length=200), nullable=True),
        sa.Column("task_ids", sa.String(length=400), nullable=True),
        sa.Column("ok", sa.Boolean(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("response_snippet", sa.Text(), nullable=True),
        sa.Column("paused_schedule", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("sysdatetimeoffset()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("sysdatetimeoffset()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["channel_id"],
            ["notification_channels.id"],
            name="fk_notification_logs_channel_id_notification_channels",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_notification_logs"),
    )
    op.create_index("ix_notification_logs_schedule_id", "notification_logs", ["schedule_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_notification_logs_schedule_id", table_name="notification_logs")
    op.drop_table("notification_logs")
    op.drop_table("notification_channels")
