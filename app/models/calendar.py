"""Calendário (out/2026): dias úteis, feriados e janelas proibidas que um agendamento pode seguir."""
from sqlalchemy import JSON, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BaseModelMixin, TimestampMixin


class Calendar(Base, BaseModelMixin, TimestampMixin):
    __tablename__ = "calendars"

    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    # Dias da semana permitidos: 0 = segunda ... 6 = domingo (padrão seg a sex).
    weekdays_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Feriados: lista de "YYYY-MM-DD".
    holidays_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Janelas proibidas: [{"label": "Backup", "start": "00:00", "end": "02:00", "weekdays": []}] (vazio = todo dia).
    blackouts_json: Mapped[list | None] = mapped_column(JSON, nullable=True)

    schedules = relationship("Schedule", back_populates="calendar")
