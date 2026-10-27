"""Calendários (dias úteis, feriados, janelas proibidas) e vínculo no agendamento

Revision ID: b3d5f7a9c1e2
Revises: a2c4e6f8b0d1
Create Date: 2026-10-27 21:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b3d5f7a9c1e2"
down_revision: Union[str, Sequence[str], None] = "a2c4e6f8b0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Tabela nova + duas colunas opcionais no agendamento: nada existente muda de comportamento.
    op.create_table(
        "calendars",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("weekdays_json", sa.JSON(), nullable=True),
        sa.Column("holidays_json", sa.JSON(), nullable=True),
        sa.Column("blackouts_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("sysdatetimeoffset()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("sysdatetimeoffset()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_calendars"),
    )
    op.create_index("ix_calendars_name", "calendars", ["name"], unique=True)
    op.create_index("ix_calendars_active", "calendars", ["active"], unique=False)

    with op.batch_alter_table("schedules") as batch:
        batch.add_column(sa.Column("calendar_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("calendar_policy", sa.String(length=10), nullable=False, server_default="defer"))
        batch.create_foreign_key(
            "fk_schedules_calendar_id_calendars", "calendars", ["calendar_id"], ["id"], ondelete="SET NULL"
        )
        batch.create_index("ix_schedules_calendar_id", ["calendar_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("schedules") as batch:
        batch.drop_index("ix_schedules_calendar_id")
        batch.drop_constraint("fk_schedules_calendar_id_calendars", type_="foreignkey")
        batch.drop_column("calendar_policy")
        batch.drop_column("calendar_id")
    op.drop_index("ix_calendars_active", table_name="calendars")
    op.drop_index("ix_calendars_name", table_name="calendars")
    op.drop_table("calendars")
