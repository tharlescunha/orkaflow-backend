# app/models/task_telemetry.py

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BaseModelMixin, TimestampMixin


class TaskTelemetry(Base, BaseModelMixin, TimestampMixin):
    __tablename__ = "task_telemetries"

    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    runner_id: Mapped[int | None] = mapped_column(
        ForeignKey("runners.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    execution_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    execution_finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    duration_seconds: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    cpu_percent_avg: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    cpu_percent_peak: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    memory_used_mb_avg: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    memory_used_mb_peak: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    process_memory_mb_peak: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    disk_read_mb: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    disk_write_mb: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    net_sent_mb: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    net_recv_mb: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    exit_code: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    telemetry_status: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
    )

    message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    payload_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    task = relationship("Task", back_populates="telemetry")
    runner = relationship("Runner")
    