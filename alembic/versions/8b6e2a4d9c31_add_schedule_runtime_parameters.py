"""add schedule runtime parameters

Revision ID: 8b6e2a4d9c31
Revises: 3f7b2e9c1d40
Create Date: 2026-06-26
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql


revision: str = "8b6e2a4d9c31"
down_revision: str | Sequence[str] | None = "3f7b2e9c1d40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("schedules", sa.Column("runtime_parameters_json", mssql.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("schedules", "runtime_parameters_json")
