from __future__ import annotations

from sqlalchemy import Boolean, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import UserRole
from app.models.base import Base, BaseModelMixin, TimestampMixin


class User(Base, BaseModelMixin, TimestampMixin):
    __tablename__ = "users"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    login: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    email: Mapped[str] = mapped_column(String(150), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"),
        nullable=False,
        default=UserRole.VIEWER,
    )

    profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    profile = relationship("Profile", back_populates="users", lazy="selectin")

    created_tasks = relationship("Task", back_populates="created_by_user")
    created_bot_versions = relationship("BotVersion", back_populates="created_by_user")
    notifications = relationship("Notification", back_populates="user")

    audit_logs = relationship(
        "AuditLog",
        back_populates="actor_user",
        passive_deletes=True,
        lazy="selectin",
    )
    