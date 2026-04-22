# app/models/lock.py

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import LockScopeType
from app.models.base import Base, BaseModelMixin, TimestampMixin


class Lock(Base, BaseModelMixin, TimestampMixin):
    __tablename__ = "locks"

    lock_key: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        index=True,
    )
    scope_type: Mapped[LockScopeType] = mapped_column(
        Enum(LockScopeType, name="lock_scope_type"),
        nullable=False,
        index=True,
    )
    owner_task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    runner_id: Mapped[int | None] = mapped_column(
        ForeignKey("runners.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    acquired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    released_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )

    task = relationship("Task", back_populates="locks")
    runner = relationship("Runner", back_populates="locks")
    