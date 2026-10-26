# app/models/api_token.py
"""Token pessoal de integração (MCP, scripts, outras IAs). Vale com as permissões do usuário."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BaseModelMixin, TimestampMixin


class ApiToken(Base, BaseModelMixin, TimestampMixin):
    __tablename__ = "api_tokens"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # Só o começo do token, para o usuário reconhecer qual é (ex.: "ork_a1b2c3d4").
    token_prefix: Mapped[str] = mapped_column(String(20), nullable=False)
    # sha256 do token completo; o token em si só é mostrado uma vez, na criação.
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User")
