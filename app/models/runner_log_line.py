# app/models/runner_log_line.py
"""Linhas do log local do worker (worker.log) enviadas pela máquina para a tela de Logs."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utc_now


class RunnerLogLine(Base):
    """
    Uma linha do worker.log de um runner.

    source: "worker" (o que o worker faz) ou "bot" (saída do robô, com task_id).
    Retenção curta (RUNNER_LOG_RETENTION_DAYS); a limpeza roda no watchdog.
    """

    __tablename__ = "runner_log_lines"
    __table_args__ = (
        Index("ix_runner_log_lines_runner_id_id", "runner_id", "id"),
    )

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    runner_id: Mapped[int] = mapped_column(
        ForeignKey("runners.id", ondelete="CASCADE"),
        nullable=False,
    )
    logged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    level: Mapped[str] = mapped_column(String(20), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    task_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.sysdatetimeoffset(),
        index=True,
    )
