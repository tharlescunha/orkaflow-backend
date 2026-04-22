from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BaseModelMixin, TimestampMixin


class WorkerRuntimeEvent(Base, BaseModelMixin, TimestampMixin):
    __tablename__ = "worker_runtime_events"

    runner_id: Mapped[int] = mapped_column(
        ForeignKey("runners.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    task_id: Mapped[int | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    automation_id: Mapped[int | None] = mapped_column(
        ForeignKey("automations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    bot_id: Mapped[int | None] = mapped_column(
        ForeignKey("bots.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    execution_mode: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        index=True,
    )

    reason: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    runner = relationship("Runner")
    task = relationship("Task")
    automation = relationship("Automation")
    bot = relationship("Bot")
    