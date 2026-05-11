"""add error screenshot to task errors

Revision ID: 4138c14a08de
Revises: cc2d58f688e7
Create Date: 2026-05-04 17:59:50.621514

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4138c14a08de'
down_revision: Union[str, Sequence[str], None] = 'cc2d58f688e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "task_errors",
        sa.Column("error_screenshot", sa.LargeBinary(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    pass
