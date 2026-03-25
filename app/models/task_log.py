# app\models\task_log.py

from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import TaskLogLevel, TaskLogSource
from app.models.base import Base, BaseModelMixin


class TaskLog(Base, BaseModelMixin):
    __tablename__ = "task_logs"

    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    level: Mapped[TaskLogLevel] = mapped_column(
        Enum(TaskLogLevel, name="task_log_level"),
        nullable=False,
        index=True,
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source: Mapped[TaskLogSource | None] = mapped_column(
        Enum(TaskLogSource, name="task_log_source"),
        nullable=True,
    )
    sequence_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    runner_id: Mapped[int | None] = mapped_column(
        ForeignKey("runners.id", ondelete="SET NULL"),
        nullable=True,
    )
    event_code: Mapped[str | None] = mapped_column(String(80), nullable=True)

    task = relationship("Task", back_populates="logs")