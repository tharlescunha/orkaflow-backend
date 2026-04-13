from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import BotSourceType, BotTechnology, BotExecutionMode
from app.models.base import Base, BaseModelMixin, TimestampMixin


class Bot(Base, BaseModelMixin, TimestampMixin):
    __tablename__ = "bots"
    __table_args__ = (
        UniqueConstraint("repository_id", "name", name="uq_bots_repository_id_name"),
    )

    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    technology: Mapped[BotTechnology] = mapped_column(
        Enum(BotTechnology, name="bot_technology"),
        nullable=False,
    )

    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="NO ACTION"),
        nullable=False,
        index=True,
    )

    current_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    release_version: Mapped[str | None] = mapped_column(String(50), nullable=True)

    source_type: Mapped[BotSourceType] = mapped_column(
        Enum(BotSourceType, name="bot_source_type"),
        nullable=False,
    )

    execution_mode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="background",
        index=True,
    )

    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    entrypoint: Mapped[str] = mapped_column(String(255), nullable=False)
    requirements_file: Mapped[str | None] = mapped_column(String(255), nullable=True)
    timeout_default: Mapped[int] = mapped_column(Integer, nullable=False, default=3600)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    repository = relationship("Repository", back_populates="bots")
    versions = relationship("BotVersion", back_populates="bot")
    automations = relationship("Automation", back_populates="bot")
