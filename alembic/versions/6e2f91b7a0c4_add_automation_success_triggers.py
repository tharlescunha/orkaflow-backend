"""add automation success triggers

Revision ID: 6e2f91b7a0c4
Revises: 54c7a0e9b2d1
Create Date: 2026-06-26
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "6e2f91b7a0c4"
down_revision: str | Sequence[str] | None = "54c7a0e9b2d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "automation_success_triggers",
        sa.Column("source_automation_id", sa.Integer(), nullable=False),
        sa.Column("target_automation_id", sa.Integer(), nullable=False),
        sa.Column("priority_override", sa.Integer(), nullable=True),
        sa.Column(
            "inherit_parent_parameters",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("sysdatetimeoffset()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("sysdatetimeoffset()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["source_automation_id"],
            ["automations.id"],
            name=op.f("fk_automation_success_triggers_source_automation_id_automations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_automation_id"],
            ["automations.id"],
            name=op.f("fk_automation_success_triggers_target_automation_id_automations"),
            ondelete="NO ACTION",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_automation_success_triggers")),
        sa.UniqueConstraint(
            "source_automation_id",
            "target_automation_id",
            name="uq_automation_success_triggers_source_target",
        ),
    )
    op.create_index(
        op.f("ix_automation_success_triggers_active"),
        "automation_success_triggers",
        ["active"],
        unique=False,
    )
    op.create_index(
        op.f("ix_automation_success_triggers_source_automation_id"),
        "automation_success_triggers",
        ["source_automation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_automation_success_triggers_target_automation_id"),
        "automation_success_triggers",
        ["target_automation_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_automation_success_triggers_target_automation_id"),
        table_name="automation_success_triggers",
    )
    op.drop_index(
        op.f("ix_automation_success_triggers_source_automation_id"),
        table_name="automation_success_triggers",
    )
    op.drop_index(
        op.f("ix_automation_success_triggers_active"),
        table_name="automation_success_triggers",
    )
    op.drop_table("automation_success_triggers")
