# app\models\schedule.py

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.mssql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import CalendarType, SchedulePolicy, ScheduleStatus, ScheduleType
from app.models.base import Base, BaseModelMixin, TimestampMixin


class Schedule(Base, BaseModelMixin, TimestampMixin):
    __tablename__ = "schedules"

    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    automation_id: Mapped[int] = mapped_column(
        ForeignKey("automations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    priority: Mapped[int | None] = mapped_column(Integer, nullable=True)
    schedule_type: Mapped[ScheduleType] = mapped_column(
        Enum(ScheduleType, name="schedule_type"),
        nullable=False,
    )
    calendar_type: Mapped[CalendarType | None] = mapped_column(
        Enum(CalendarType, name="calendar_type"),
        nullable=True,
    )
    cron_expression: Mapped[str | None] = mapped_column(String(120), nullable=True)
    policy: Mapped[SchedulePolicy] = mapped_column(
        Enum(SchedulePolicy, name="schedule_policy"),
        nullable=False,
    )
    parameters_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    timezone: Mapped[str] = mapped_column(String(80), nullable=False, default="UTC")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    status: Mapped[ScheduleStatus] = mapped_column(
        Enum(ScheduleStatus, name="schedule_status"),
        nullable=False,
        default=ScheduleStatus.ACTIVE,
    )
    interval_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    interval_unit: Mapped[str | None] = mapped_column(String(30), nullable=True)
    misfire_policy: Mapped[str | None] = mapped_column(String(50), nullable=True)

    automation = relationship("Automation", back_populates="schedules")
    tasks = relationship("Task", back_populates="schedule")