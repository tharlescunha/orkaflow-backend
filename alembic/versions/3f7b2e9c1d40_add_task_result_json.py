"""add task result json

Revision ID: 3f7b2e9c1d40
Revises: 9d4b7c2e1a30
Create Date: 2026-06-26
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "3f7b2e9c1d40"
down_revision: str | Sequence[str] | None = "9d4b7c2e1a30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("result_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("tasks", "result_json")
