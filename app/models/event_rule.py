"""Eventos (out/2026): "Quando" (robô + condição sobre a saída) → "Então" (requisições HTTP).

Mesmo formato de envio do canal de notificação: etapas prévias (login que devolve token), envio
principal com cabeçalhos e corpo com {{variáveis}}. O que muda é o gatilho: por task, não por
sequência de falhas de agendamento.
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BaseModelMixin, TimestampMixin


class EventRule(Base, BaseModelMixin, TimestampMixin):
    __tablename__ = "event_rules"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    # Quando: escopo (automation | bot | all) + gatilho.
    scope_type: Mapped[str] = mapped_column(String(20), nullable=False, default="automation")
    scope_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    # task_error | task_success | task_timeout | credential_invalid | result_contains | exit_code
    trigger_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    # result_contains: {"key": "status", "value": "reprovado"}; exit_code: {"code": 3}
    trigger_config_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Então: etapas prévias + envio principal (mesmo formato do canal de notificação).
    pre_steps_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    method: Mapped[str] = mapped_column(String(10), nullable=False, default="POST")
    headers_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_template: Mapped[str] = mapped_column(Text, nullable=False, default="")
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=15)

    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    runs = relationship("EventRun", back_populates="rule")


class EventRun(Base, BaseModelMixin, TimestampMixin):
    """Cada disparo de um evento: fica pendente ao fim da task e é executado pelo loop de
    notificações, fora da transação que fecha a task."""

    __tablename__ = "event_runs"

    rule_id: Mapped[int | None] = mapped_column(
        ForeignKey("event_rules.id", ondelete="SET NULL"), nullable=True, index=True
    )
    rule_name: Mapped[str] = mapped_column(String(150), nullable=False)
    task_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    automation_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    trigger_type: Mapped[str] = mapped_column(String(40), nullable=False)
    # pending | running | success | error | test
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    variables_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    # requisição enviada, etapas e resposta inteira (segredos mascarados), em JSON
    details_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    rule = relationship("EventRule", back_populates="runs")
