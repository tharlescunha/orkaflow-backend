from __future__ import annotations

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Table, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BaseModelMixin, TimestampMixin


profile_permissions = Table(
    "profile_permissions",
    Base.metadata,
    Column("profile_id", Integer, ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", Integer, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


class Profile(Base, BaseModelMixin, TimestampMixin):
    __tablename__ = "profiles"

    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    permissions: Mapped[list["Permission"]] = relationship(
        "Permission",
        secondary=profile_permissions,
        back_populates="profiles",
        lazy="selectin",
    )

    users: Mapped[list["User"]] = relationship(
        "User",
        back_populates="profile",
        lazy="selectin",
    )


class Permission(Base, BaseModelMixin):
    __tablename__ = "permissions"
    __table_args__ = (
        UniqueConstraint("module", "action", name="uq_permissions_module_action"),
    )

    module: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    profiles: Mapped[list["Profile"]] = relationship(
        "Profile",
        secondary=profile_permissions,
        back_populates="permissions",
        lazy="selectin",
    )
    