# app/models/runner.py

from datetime import datetime
import uuid

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import RunnerStatus
from app.models.base import Base, BaseModelMixin, TimestampMixin


class Runner(Base, BaseModelMixin, TimestampMixin):
    __tablename__ = "runners"

    uuid: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        default=lambda: str(uuid.uuid4()),
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    label: Mapped[str | None] = mapped_column(String(150), nullable=True)
    host_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    os_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    os_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    cpu_arch: Mapped[str | None] = mapped_column(String(50), nullable=True)
    memory_total: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    status: Mapped[RunnerStatus] = mapped_column(
        Enum(RunnerStatus, name="runner_status"),
        nullable=False,
        default=RunnerStatus.OFFLINE,
        index=True,
    )

    last_heartbeat: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    access_remote: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Usuário com que a equipe acessa a máquina (cadastrado no painel) e usuário do Windows em que o
    # worker está rodando (informado pelo próprio worker no heartbeat). Out/2026.
    login_user: Mapped[str | None] = mapped_column(String(150), nullable=True)
    os_user: Mapped[str | None] = mapped_column(String(150), nullable=True)
    # Versão do worker na máquina (commit do Git e número), informada no heartbeat; e o pedido de atualização
    # feito pelo painel (limpo quando o worker volta rodando outro commit). Out/2026.
    worker_commit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    worker_version: Mapped[str | None] = mapped_column(String(30), nullable=True)
    worker_update_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    # Runner removido pelo administrador: some das listagens e não executa mais nada.
    # A linha fica no banco para o histórico das tasks antigas continuar com o nome.
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    # Último print de tela enviado pelo worker. deferred: só sai do banco quando a rota do print
    # pede (0,7 MB por linha; vinha junto em toda task/health/dashboard que carregava o runner).
    last_screenshot_image: Mapped[bytes | None] = mapped_column(
        LargeBinary,
        nullable=True,
        deferred=True,
    )

    # Horário do último print recebido
    last_screenshot_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    config = relationship("RunnerConfig", back_populates="runner", uselist=False)
    tasks = relationship("Task", back_populates="runner")
    locks = relationship("Lock", back_populates="runner")
    automation_links = relationship("AutomationRunner", back_populates="runner")

    status_history = relationship(
        "RunnerStatusHistory",
        back_populates="runner",
        cascade="all, delete-orphan",
    )
    