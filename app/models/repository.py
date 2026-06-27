from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BaseModelMixin, TimestampMixin


class Repository(Base, BaseModelMixin, TimestampMixin):
    __tablename__ = "repositories"

    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    bots = relationship("Bot", back_populates="repository")
    automations = relationship("Automation", back_populates="repository")
    credentials = relationship("Credential", back_populates="repository")