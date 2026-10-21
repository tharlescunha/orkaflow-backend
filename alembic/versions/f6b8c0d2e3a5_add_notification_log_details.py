"""add details_json to notification_logs

Revision ID: f6b8c0d2e3a5
Revises: e5a7b9c1d2f4
Create Date: 2026-10-21 21:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f6b8c0d2e3a5"
down_revision: Union[str, Sequence[str], None] = "e5a7b9c1d2f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Coluna nova e nula: nenhuma linha existente é alterada.
    op.add_column("notification_logs", sa.Column("details_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("notification_logs", "details_json")
