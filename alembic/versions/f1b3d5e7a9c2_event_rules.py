"""Eventos: regras "Quando → Então" por robô e histórico de disparos

Revision ID: f1b3d5e7a9c2
Revises: e4a7c9d1b3f5
Create Date: 2026-10-27 17:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f1b3d5e7a9c2"
down_revision: Union[str, Sequence[str], None] = "e4a7c9d1b3f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Só tabelas novas: nada existente muda.
    op.create_table(
        "event_rules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("scope_type", sa.String(length=20), nullable=False, server_default="automation"),
        sa.Column("scope_id", sa.Integer(), nullable=True),
        sa.Column("trigger_type", sa.String(length=40), nullable=False),
        sa.Column("trigger_config_json", sa.Text(), nullable=True),
        sa.Column("pre_steps_json", sa.Text(), nullable=True),
        sa.Column("url", sa.String(length=1000), nullable=False, server_default=""),
        sa.Column("method", sa.String(length=10), nullable=False, server_default="POST"),
        sa.Column("headers_json", sa.Text(), nullable=True),
        sa.Column("body_template", sa.Text(), nullable=False, server_default=""),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="15"),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_ok", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("sysdatetimeoffset()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("sysdatetimeoffset()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_event_rules"),
    )
    op.create_index("ix_event_rules_active", "event_rules", ["active"], unique=False)
    op.create_index("ix_event_rules_scope_id", "event_rules", ["scope_id"], unique=False)
    op.create_index("ix_event_rules_trigger_type", "event_rules", ["trigger_type"], unique=False)

    op.create_table(
        "event_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("rule_id", sa.Integer(), nullable=True),
        sa.Column("rule_name", sa.String(length=150), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=True),
        sa.Column("automation_name", sa.String(length=200), nullable=True),
        sa.Column("trigger_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("variables_json", sa.Text(), nullable=True),
        sa.Column("ok", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("response_snippet", sa.Text(), nullable=True),
        sa.Column("details_json", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("sysdatetimeoffset()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("sysdatetimeoffset()"), nullable=False),
        sa.ForeignKeyConstraint(["rule_id"], ["event_rules.id"], name="fk_event_runs_rule_id_event_rules", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_event_runs"),
    )
    op.create_index("ix_event_runs_rule_id", "event_runs", ["rule_id"], unique=False)
    op.create_index("ix_event_runs_task_id", "event_runs", ["task_id"], unique=False)
    op.create_index("ix_event_runs_status", "event_runs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_event_runs_status", table_name="event_runs")
    op.drop_index("ix_event_runs_task_id", table_name="event_runs")
    op.drop_index("ix_event_runs_rule_id", table_name="event_runs")
    op.drop_table("event_runs")
    op.drop_index("ix_event_rules_trigger_type", table_name="event_rules")
    op.drop_index("ix_event_rules_scope_id", table_name="event_rules")
    op.drop_index("ix_event_rules_active", table_name="event_rules")
    op.drop_table("event_rules")
