# app\models\credential.py

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BaseModelMixin, TimestampMixin


class Credential(Base, BaseModelMixin, TimestampMixin):
    __tablename__ = "credentials"
    __table_args__ = (
        UniqueConstraint("repository_id", "label", name="uq_credentials_repository_id_label"),
    )

    label: Mapped[str] = mapped_column(String(150), nullable=False)
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="NO ACTION"),
        nullable=False,
        index=True,
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    # Saúde (out/2026): valida | nao_verificada | invalida | senha_incorreta | senha_expirada | usuario_bloqueado.
    # Quem marca é o alerta do robô (via worker); volta a nao_verificada ao trocar um item.
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="nao_verificada", server_default="nao_verificada")
    status_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    status_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status_task_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    repository = relationship("Repository", back_populates="credentials")
    items = relationship("CredentialItem", back_populates="credential")