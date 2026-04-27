from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base


class RunnerStatusHistory(Base):
    __tablename__ = "runner_status_history"

    id = Column(Integer, primary_key=True, index=True)

    runner_id = Column(
        Integer,
        ForeignKey("runners.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ONLINE | OFFLINE
    status = Column(String(20), nullable=False)

    # motivo da mudança (opcional, mas MUITO útil)
    reason = Column(String(50), nullable=True)

    # momento do evento
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.sysdatetimeoffset(),
        index=True,
    )

    # relacionamento (opcional, mas bom ter)
    runner = relationship("Runner", back_populates="status_history")


# 🔥 Índices importantes para performance
Index("ix_runner_status_history_runner_created", RunnerStatusHistory.runner_id, RunnerStatusHistory.created_at)
Index("ix_runner_status_history_runner_status", RunnerStatusHistory.runner_id, RunnerStatusHistory.status)
