# app/models/runner.py

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import RunnerStatus
from app.models.base import Base, BaseModelMixin, TimestampMixin

import uuid


class Runner(Base, BaseModelMixin, TimestampMixin):
    __tablename__ = "runners"

    uuid: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        default=lambda: str(uuid.uuid4())
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
    last_heartbeat: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    access_remote: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    config = relationship("RunnerConfig", back_populates="runner", uselist=False)
    tasks = relationship("Task", back_populates="runner")
    locks = relationship("Lock", back_populates="runner")
    automation_links = relationship("AutomationRunner", back_populates="runner")
    