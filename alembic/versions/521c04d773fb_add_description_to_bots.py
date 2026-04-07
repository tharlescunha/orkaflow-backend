"""add description to bots

Revision ID: 521c04d773fb
Revises: 2b04d2128741
Create Date: 2026-04-01 15:27:48.907284
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '521c04d773fb'
down_revision: Union[str, Sequence[str], None] = '2b04d2128741'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "bots",
        sa.Column("description", sa.String(length=500), nullable=True),
        schema="orkaflow",  # ajuste se seu schema for outro
    )


def downgrade() -> None:
    op.drop_column(
        "bots",
        "description",
        schema="orkaflow",  # ajuste se seu schema for outro
    )
    