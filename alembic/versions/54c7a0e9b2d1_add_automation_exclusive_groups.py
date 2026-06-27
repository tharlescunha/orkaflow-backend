"""add automation exclusive groups

Revision ID: 54c7a0e9b2d1
Revises: 2c8e1f4a6b90
Create Date: 2026-06-26
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "54c7a0e9b2d1"
down_revision: str | Sequence[str] | None = "2c8e1f4a6b90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "automation_exclusive_groups",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("label", sa.String(length=150), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("capacity", sa.Integer(), nullable=False, server_default="1"),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_automation_exclusive_groups")),
        sa.UniqueConstraint("name", name="uq_automation_exclusive_groups_name"),
    )
    op.create_index(
        op.f("ix_automation_exclusive_groups_active"),
        "automation_exclusive_groups",
        ["active"],
        unique=False,
    )
    op.create_index(
        op.f("ix_automation_exclusive_groups_name"),
        "automation_exclusive_groups",
        ["name"],
        unique=False,
    )

    op.create_table(
        "automation_exclusive_group_members",
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("automation_id", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(
            ["automation_id"],
            ["automations.id"],
            name=op.f("fk_automation_exclusive_group_members_automation_id_automations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["automation_exclusive_groups.id"],
            name=op.f("fk_automation_exclusive_group_members_group_id_automation_exclusive_groups"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_automation_exclusive_group_members")),
        sa.UniqueConstraint(
            "group_id",
            "automation_id",
            name="uq_automation_exclusive_group_members_group_automation",
        ),
    )
    op.create_index(
        op.f("ix_automation_exclusive_group_members_automation_id"),
        "automation_exclusive_group_members",
        ["automation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_automation_exclusive_group_members_group_id"),
        "automation_exclusive_group_members",
        ["group_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_automation_exclusive_group_members_group_id"),
        table_name="automation_exclusive_group_members",
    )
    op.drop_index(
        op.f("ix_automation_exclusive_group_members_automation_id"),
        table_name="automation_exclusive_group_members",
    )
    op.drop_table("automation_exclusive_group_members")
    op.drop_index(op.f("ix_automation_exclusive_groups_name"), table_name="automation_exclusive_groups")
    op.drop_index(op.f("ix_automation_exclusive_groups_active"), table_name="automation_exclusive_groups")
    op.drop_table("automation_exclusive_groups")
