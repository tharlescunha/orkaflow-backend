"""add schedule use_default_runtime_parameters

Revision ID: c4e8f1a2b3d6
Revises: b7d3e1f2a9c5
Create Date: 2026-06-27
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "c4e8f1a2b3d6"
down_revision: str | Sequence[str] | None = "b7d3e1f2a9c5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "schedules",
        sa.Column(
            "use_default_runtime_parameters",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    op.drop_column("schedules", "use_default_runtime_parameters")
