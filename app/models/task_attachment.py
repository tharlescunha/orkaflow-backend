"""Arquivo anexado à task pelo robô (maestro.attach): planilha, PDF, log... Guardado no banco
(até 5 MB por arquivo, 10 por task; o worker aplica o limite antes de enviar)."""
from sqlalchemy import ForeignKey, Integer, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BaseModelMixin, TimestampMixin


class TaskAttachment(Base, BaseModelMixin, TimestampMixin):
    __tablename__ = "task_attachments"

    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False, default="application/octet-stream")
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    description: Mapped[str | None] = mapped_column(String(300), nullable=True)
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    task = relationship("Task", back_populates="attachments")
