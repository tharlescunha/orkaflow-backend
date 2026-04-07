from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import ExecutionMode, TaskStatus
from app.models.base import Base, BaseModelMixin


class Task(Base, BaseModelMixin):
    __tablename__ = "tasks"

    automation_id: Mapped[int] = mapped_column(
        ForeignKey("automations.id", ondelete="NO ACTION"),
        nullable=False,
        index=True,
    )
    bot_version_id: Mapped[int] = mapped_column(
        ForeignKey("bot_versions.id", ondelete="NO ACTION"),
        nullable=False,
        index=True,
    )
    runner_id: Mapped[int | None] = mapped_column(
        ForeignKey("runners.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    schedule_id: Mapped[int | None] = mapped_column(
        ForeignKey("schedules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    parent_task_id = mapped_column(
        ForeignKey("tasks.id", ondelete="NO ACTION"),
        nullable=True,
        index=True
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, name="task_status"),
        nullable=False,
        default=TaskStatus.WAITING,
        index=True,
    )
    requested_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_update_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    final_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    items_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    items_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=3600)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    execution_mode: Mapped[ExecutionMode] = mapped_column(
        Enum(ExecutionMode, name="execution_mode"),
        nullable=False,
        default=ExecutionMode.MANUAL,
    )
    dispatch_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stop_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    correlation_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    queue_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    inactivity_timeout_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    runner_claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    automation = relationship("Automation", back_populates="tasks")
    bot_version = relationship("BotVersion", back_populates="tasks")
    runner = relationship("Runner", back_populates="tasks")
    created_by_user = relationship("User", back_populates="created_tasks")
    schedule = relationship("Schedule", back_populates="tasks")
    parent_task = relationship("Task", remote_side="Task.id")
    parameters = relationship("TaskParameter", back_populates="task")
    logs = relationship("TaskLog", back_populates="task")
    errors = relationship("TaskError", back_populates="task")
    locks = relationship("Lock", back_populates="task")

    telemetry = relationship(
        "TaskTelemetry",
        back_populates="task",
        uselist=False,
        cascade="all, delete-orphan",
    )
    