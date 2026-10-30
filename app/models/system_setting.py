"""Configurações simples do sistema (chave/valor). Out/2026: link do repositório do worker e último commit visto."""
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, BaseModelMixin, TimestampMixin


class SystemSetting(Base, BaseModelMixin, TimestampMixin):
    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
