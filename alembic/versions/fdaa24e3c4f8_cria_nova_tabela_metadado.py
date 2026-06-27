"""create task telemetries table

Revision ID: create_task_telemetries
Revises: SUA_REVISAO_ANTERIOR
Create Date: 2026-04-06 00:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "create_task_telemetries"
down_revision = "521c04d773fb"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "task_telemetries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("runner_id", sa.Integer(), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("execution_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("execution_finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("cpu_percent_avg", sa.Float(), nullable=True),
        sa.Column("cpu_percent_peak", sa.Float(), nullable=True),
        sa.Column("memory_used_mb_avg", sa.Float(), nullable=True),
        sa.Column("memory_used_mb_peak", sa.Float(), nullable=True),
        sa.Column("process_memory_mb_peak", sa.Float(), nullable=True),
        sa.Column("disk_read_mb", sa.Float(), nullable=True),
        sa.Column("disk_write_mb", sa.Float(), nullable=True),
        sa.Column("net_sent_mb", sa.Float(), nullable=True),
        sa.Column("net_recv_mb", sa.Float(), nullable=True),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column("telemetry_status", sa.String(length=50), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["runner_id"], ["runners.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id"),
    )

    op.create_index(op.f("ix_task_telemetries_task_id"), "task_telemetries", ["task_id"], unique=True)
    op.create_index(op.f("ix_task_telemetries_runner_id"), "task_telemetries", ["runner_id"], unique=False)
    op.create_index(op.f("ix_task_telemetries_captured_at"), "task_telemetries", ["captured_at"], unique=False)
    op.create_index(op.f("ix_task_telemetries_telemetry_status"), "task_telemetries", ["telemetry_status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_task_telemetries_telemetry_status"), table_name="task_telemetries")
    op.drop_index(op.f("ix_task_telemetries_captured_at"), table_name="task_telemetries")
    op.drop_index(op.f("ix_task_telemetries_runner_id"), table_name="task_telemetries")
    op.drop_index(op.f("ix_task_telemetries_task_id"), table_name="task_telemetries")
    op.drop_table("task_telemetries")
    