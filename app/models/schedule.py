# app\models\schedule.py

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
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
    runtime_parameters_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
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
    use_default_runtime_parameters: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Último erro transitório do engine e último motivo de execução descartada.
    # O schedule nunca vai para ERROR por causa disso: continua ACTIVE.
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_skipped_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_skipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Por que está pausado (ex.: credencial_invalida) e por qual credencial: assim a reativação
    # automática só mexe nos agendamentos que ela mesma pausou.
    paused_reason: Mapped[str | None] = mapped_column(String(60), nullable=True)
    paused_credential_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Retentativa automática (out/2026): quantas vezes a mais tentar quando a task deste agendamento
    # falhar, intervalo entre tentativas e em quais falhas ("erro" e/ou "timeout"). 0 = não retenta.
    retry_max: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    retry_delay_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=300, server_default="300")
    retry_on_json: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Calendário (out/2026): dias úteis, feriados e janelas; política num horário não permitido:
    # "defer" (roda no próximo permitido, mesmo horário) ou "skip" (não roda e anota o motivo).
    calendar_id: Mapped[int | None] = mapped_column(
        ForeignKey("calendars.id", ondelete="SET NULL"), nullable=True, index=True
    )
    calendar_policy: Mapped[str] = mapped_column(String(10), nullable=False, default="defer", server_default="defer")
    # "No N-ésimo dia útil do mês às HH:MM": calendar_type fica MONTH (1 mês) e estes dois campos
    # dizem o dia útil (1 = primeiro) e a hora. Dias úteis e feriados vêm do calendário do agendamento
    # (sem calendário: segunda a sexta, sem feriados).
    business_day_of_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    time_of_day: Mapped[str | None] = mapped_column(String(5), nullable=True)

    automation = relationship("Automation", back_populates="schedules")
    calendar = relationship("Calendar", back_populates="schedules")
    tasks = relationship("Task", back_populates="schedule")
