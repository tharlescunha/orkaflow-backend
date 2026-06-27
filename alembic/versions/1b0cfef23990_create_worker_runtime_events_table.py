"""create worker_runtime_events table

Revision ID: 1b0cfef23990
Revises: e96953f7de5e
Create Date: 2026-04-13 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "1b0cfef23990"
down_revision: Union[str, Sequence[str], None] = "e96953f7de5e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "worker_runtime_events",
        sa.Column("runner_id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=True),
        sa.Column("automation_id", sa.Integer(), nullable=True),
        sa.Column("bot_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("execution_mode", sa.String(length=20), nullable=True),
        sa.Column("reason", sa.String(length=100), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(
            ["automation_id"],
            ["automations.id"],
            name=op.f("fk_worker_runtime_events_automation_id_automations"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["bot_id"],
            ["bots.id"],
            name=op.f("fk_worker_runtime_events_bot_id_bots"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["runner_id"],
            ["runners.id"],
            name=op.f("fk_worker_runtime_events_runner_id_runners"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.id"],
            name=op.f("fk_worker_runtime_events_task_id_tasks"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_worker_runtime_events")),
    )

    op.create_index(
        op.f("ix_worker_runtime_events_runner_id"),
        "worker_runtime_events",
        ["runner_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_worker_runtime_events_task_id"),
        "worker_runtime_events",
        ["task_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_worker_runtime_events_automation_id"),
        "worker_runtime_events",
        ["automation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_worker_runtime_events_bot_id"),
        "worker_runtime_events",
        ["bot_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_worker_runtime_events_event_type"),
        "worker_runtime_events",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_worker_runtime_events_execution_mode"),
        "worker_runtime_events",
        ["execution_mode"],
        unique=False,
    )
    op.create_index(
        op.f("ix_worker_runtime_events_reason"),
        "worker_runtime_events",
        ["reason"],
        unique=False,
    )
    op.create_index(
        op.f("ix_worker_runtime_events_created_at"),
        "worker_runtime_events",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_worker_runtime_events_created_at"), table_name="worker_runtime_events")
    op.drop_index(op.f("ix_worker_runtime_events_reason"), table_name="worker_runtime_events")
    op.drop_index(op.f("ix_worker_runtime_events_execution_mode"), table_name="worker_runtime_events")
    op.drop_index(op.f("ix_worker_runtime_events_event_type"), table_name="worker_runtime_events")
    op.drop_index(op.f("ix_worker_runtime_events_bot_id"), table_name="worker_runtime_events")
    op.drop_index(op.f("ix_worker_runtime_events_automation_id"), table_name="worker_runtime_events")
    op.drop_index(op.f("ix_worker_runtime_events_task_id"), table_name="worker_runtime_events")
    op.drop_index(op.f("ix_worker_runtime_events_runner_id"), table_name="worker_runtime_events")
    op.drop_table("worker_runtime_events")