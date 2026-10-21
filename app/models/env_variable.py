# app/models/env_variable.py
"""Variáveis de ambiente entregues ao robô pelo worker, com escopo e herança."""

from sqlalchemy import Boolean, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, BaseModelMixin, TimestampMixin


class EnvVariable(Base, BaseModelMixin, TimestampMixin):
    """
    Variável nome=valor injetada no ambiente do processo do robô.

    Escopos (do mais geral ao mais específico; o mais específico vence):
    global (scope_id=0) < bot < automation < runner (máquina).
    Valores secretos ficam criptografados (mesma chave das credenciais) e nunca voltam pela API.
    """

    __tablename__ = "env_variables"
    __table_args__ = (
        UniqueConstraint("scope_type", "scope_id", "name", name="uq_env_variables_scope_name"),
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    scope_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    scope_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_secret: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    description: Mapped[str | None] = mapped_column(String(300), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
