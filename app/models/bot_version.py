from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BaseModelMixin
from app.models.base import TimestampMixin


class BotVersion(Base, BaseModelMixin, TimestampMixin):
    __tablename__ = "bot_versions"
    __table_args__ = (
        UniqueConstraint("bot_id", "version", name="uq_bot_versions_bot_id_version"),
    )

    bot_id: Mapped[int] = mapped_column(
        ForeignKey("bots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    storage_type: Mapped[str] = mapped_column(String(50), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    commit_hash: Mapped[str | None] = mapped_column(String(80), nullable=True)
    branch: Mapped[str | None] = mapped_column(String(120), nullable=True)
    artifact_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    changelog: Mapped[str | None] = mapped_column(Text, nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="NO ACTION"),
        nullable=False,
        index=True,
    )

    bot = relationship("Bot", back_populates="versions")
    created_by_user = relationship("User", back_populates="created_bot_versions")
    tasks = relationship("Task", back_populates="bot_version")