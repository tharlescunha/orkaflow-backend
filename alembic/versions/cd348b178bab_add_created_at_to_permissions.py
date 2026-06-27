"""add created_at to permissions

Revision ID: cd348b178bab
Revises: a1b2c3d4_profiles_permissions
Create Date: 2026-04-21 13:40:58.156138

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cd348b178bab'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4_profiles_permissions'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column(
        "permissions",
        sa.Column("created_at", sa.DateTime(), nullable=True)
    )

def downgrade():
    op.drop_column("permissions", "created_at")
    