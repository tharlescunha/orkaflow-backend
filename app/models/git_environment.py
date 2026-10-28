"""Ambientes de Git (out/2026): token por prefixo de URL, para o bot ser cadastrado com o link limpo.

Exemplos: ``https://dev.azure.com/alzgraos/`` (um token da organização cobre todos os repositórios) e
``https://github.com/tharlescunha/`` (no GitHub o token é da conta, um ambiente por conta). Quando o
link do bot não traz token, o backend injeta o do ambiente cujo prefixo casa com o link na hora de
usar (worker e prévia de versão). Link que já vem com token continua valendo como sempre.
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, BaseModelMixin, TimestampMixin


class GitEnvironment(Base, BaseModelMixin, TimestampMixin):
    __tablename__ = "git_environments"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # Começo do link, normalizado (minúsculas, sem %20, com barra no fim). Único.
    url_prefix: Mapped[str] = mapped_column(String(500), nullable=False, unique=True, index=True)
    # Usuário opcional na URL de clone (user:token@). Azure DevOps e GitHub aceitam só o token.
    username: Mapped[str | None] = mapped_column(String(150), nullable=True)
    token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    # Últimos caracteres do token, só para a pessoa reconhecer qual é (nunca o valor inteiro).
    token_hint: Mapped[str | None] = mapped_column(String(12), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
