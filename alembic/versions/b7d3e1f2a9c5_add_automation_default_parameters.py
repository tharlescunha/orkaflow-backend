"""add automation default parameters

Revision ID: b7d3e1f2a9c5
Revises: 8b6e2a4d9c31
Create Date: 2026-06-27
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql


revision: str = "b7d3e1f2a9c5"
down_revision: str | Sequence[str] | None = "8b6e2a4d9c31"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("automations", sa.Column("default_parameters_json", mssql.JSON(), nullable=True))
    op.add_column("automations", sa.Column("default_runtime_parameters_json", mssql.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("automations", "default_runtime_parameters_json")
    op.drop_column("automations", "default_parameters_json")
