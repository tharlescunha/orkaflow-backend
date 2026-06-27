"""add automation health indexes

Revision ID: 9d4b7c2e1a30
Revises: 6e2f91b7a0c4
Create Date: 2026-06-26
"""

from collections.abc import Sequence

from alembic import op


revision: str = "9d4b7c2e1a30"
down_revision: str | Sequence[str] | None = "6e2f91b7a0c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_tasks_health_latest_by_automation",
        "tasks",
        ["automation_id", "created_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_schedules_health_latest_by_automation",
        "schedules",
        ["automation_id", "active", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_schedules_health_latest_by_automation", table_name="schedules")
    op.drop_index("ix_tasks_health_latest_by_automation", table_name="tasks")
