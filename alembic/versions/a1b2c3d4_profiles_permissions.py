"""create profiles, permissions and user profile relation

Revision ID: a1b2c3d4_profiles_permissions
Revises: 1b0cfef23990
Create Date: 2026-04-20

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a1b2c3d4_profiles_permissions"
down_revision = "1b0cfef23990"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ==========================================================
    # PROFILES
    # ==========================================================
    op.create_table(
        "profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_index("ix_profiles_name", "profiles", ["name"], unique=True)
    op.create_index("ix_profiles_active", "profiles", ["active"])


    # ==========================================================
    # PERMISSIONS
    # ==========================================================
    op.create_table(
        "permissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("module", sa.String(length=100), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.UniqueConstraint("module", "action", name="uq_permissions_module_action"),
    )

    op.create_index("ix_permissions_module", "permissions", ["module"])
    op.create_index("ix_permissions_action", "permissions", ["action"])


    # ==========================================================
    # PROFILE_PERMISSIONS
    # ==========================================================
    op.create_table(
        "profile_permissions",
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("permission_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["profiles.id"],
            ondelete="CASCADE",
            name="fk_profile_permissions_profile_id_profiles",
        ),
        sa.ForeignKeyConstraint(
            ["permission_id"],
            ["permissions.id"],
            ondelete="CASCADE",
            name="fk_profile_permissions_permission_id_permissions",
        ),
        sa.PrimaryKeyConstraint(
            "profile_id",
            "permission_id",
            name="pk_profile_permissions",
        ),
    )


    # ==========================================================
    # USERS -> PROFILE_ID
    # ==========================================================
    op.add_column(
        "users",
        sa.Column("profile_id", sa.Integer(), nullable=True),
    )

    op.create_index("ix_users_profile_id", "users", ["profile_id"])

    op.create_foreign_key(
        "fk_users_profile",
        "users",
        "profiles",
        ["profile_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_users_profile", "users", type_="foreignkey")
    op.drop_index("ix_users_profile_id", table_name="users")
    op.drop_column("users", "profile_id")

    op.drop_table("profile_permissions")

    op.drop_index("ix_permissions_action", table_name="permissions")
    op.drop_index("ix_permissions_module", table_name="permissions")
    op.drop_table("permissions")

    op.drop_index("ix_profiles_active", table_name="profiles")
    op.drop_index("ix_profiles_name", table_name="profiles")
    op.drop_table("profiles")
    