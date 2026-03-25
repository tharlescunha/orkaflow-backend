# app/models/task_parameter.py

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BaseModelMixin


class TaskParameter(Base, BaseModelMixin):
    __tablename__ = "task_parameters"

    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parameter_name: Mapped[str] = mapped_column(String(100), nullable=False)
    parameter_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_secret: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    resolved_from_credential_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("credential_items.id", ondelete="SET NULL"),
        nullable=True,
    )

    task = relationship("Task", back_populates="parameters")