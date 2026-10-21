# app/models/notification_channel.py
"""Canal de notificação configurável (ex.: abrir chamado no desk) e histórico de envios."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, BaseModelMixin, TimestampMixin


class NotificationChannel(Base, BaseModelMixin, TimestampMixin):
    """
    Configuração do envio disparado quando um agendamento falha N vezes seguidas.

    Nada do destino fica no código: URL, método, cabeçalhos e corpo (com variáveis como
    {{erro}} e {{automacao}}) são editados na tela de Notificações.
    """

    __tablename__ = "notification_channels"

    name: Mapped[str] = mapped_column(String(120), nullable=False, default="Chamado")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    url: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    method: Mapped[str] = mapped_column(String(10), nullable=False, default="POST")
    headers_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_template: Mapped[str] = mapped_column(Text, nullable=False, default="")
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    failure_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    pause_schedule: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    deactivate_automation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    panel_base_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # Só falhas de tasks finalizadas a partir deste momento contam para o alerta
    # (definido ao ativar o canal), para falhas antigas não abrirem chamado.
    counting_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Etapas executadas antes do envio principal (ex.: login que devolve um token), em JSON.
    pre_steps_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class NotificationLog(Base, BaseModelMixin, TimestampMixin):
    """Histórico de cada envio (alerta de falhas ou teste)."""

    __tablename__ = "notification_logs"

    channel_id: Mapped[int | None] = mapped_column(
        ForeignKey("notification_channels.id", ondelete="SET NULL"),
        nullable=True,
    )
    kind: Mapped[str] = mapped_column(String(30), nullable=False, default="failure_alert")
    schedule_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    schedule_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    automation_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    task_ids: Mapped[str | None] = mapped_column(String(400), nullable=True)
    ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    paused_schedule: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Detalhes completos do envio (requisição enviada, etapas, resposta inteira), em JSON.
    details_json: Mapped[str | None] = mapped_column(Text, nullable=True)
