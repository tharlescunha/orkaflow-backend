# app/models/task_error.py

from sqlalchemy import Boolean, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import ErrorCategory, TaskLogSource
from app.models.base import Base, BaseModelMixin, TimestampMixin


class TaskError(Base, BaseModelMixin, TimestampMixin):
    __tablename__ = "task_errors"

    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    error_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    stacktrace: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_category: Mapped[ErrorCategory | None] = mapped_column(
        Enum(ErrorCategory, name="error_category"),
        nullable=True,
    )
    is_retryable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source: Mapped[TaskLogSource | None] = mapped_column(
        Enum(TaskLogSource, name="task_error_source"),
        nullable=True,
    )
    code: Mapped[str | None] = mapped_column(String(80), nullable=True)

    task = relationship("Task", back_populates="errors")
    