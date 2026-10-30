"""Tela Sync (out/2026): health de sistemas de fora do Regente e automações escolhidas por usuário."""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, BaseModelMixin, TimestampMixin


class SyncCheck(Base, BaseModelMixin, TimestampMixin):
    """Um sistema externo acompanhado por um usuário (o backend faz o ping quando a tela pede)."""

    __tablename__ = "sync_checks"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    # Texto livre: onde o sistema está publicado (ex.: Azure) e de que projeto ele é (ex.: Insumos).
    server: Mapped[str | None] = mapped_column(String(120), nullable=True)
    project: Mapped[str | None] = mapped_column(String(120), nullable=True)
    interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    expected_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    last_ping_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    last_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class SyncAutomationPick(Base, BaseModelMixin, TimestampMixin):
    """Automação que o usuário escolheu ver na tela Sync."""

    __tablename__ = "sync_automation_picks"
    __table_args__ = (UniqueConstraint("user_id", "automation_id", name="uq_sync_pick_user_automation"),)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    automation_id: Mapped[int] = mapped_column(ForeignKey("automations.id", ondelete="CASCADE"), nullable=False, index=True)
