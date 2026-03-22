from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import NotificationType
from app.models.base import Base, BaseModelMixin, TimestampMixin


class Automation(Base, BaseModelMixin, TimestampMixin):
    __tablename__ = "automations"
    __table_args__ = (
        UniqueConstraint("repository_id", "name", name="uq_automations_repository_id_name"),
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    label: Mapped[str | None] = mapped_column(String(150), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    bot_id: Mapped[int] = mapped_column(
        ForeignKey("bots.id", ondelete="NO ACTION"),
        nullable=False,
        index=True,
    )
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="NO ACTION"),
        nullable=False,
        index=True,
    )
    default_priority: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    notification_type: Mapped[NotificationType | None] = mapped_column(
        Enum(NotificationType, name="notification_type"),
        nullable=True,
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    bot = relationship("Bot", back_populates="automations")
    repository = relationship("Repository", back_populates="automations")
    runner_links = relationship("AutomationRunner", back_populates="automation")
    parameters = relationship("AutomationParameter", back_populates="automation")
    tasks = relationship("Task", back_populates="automation")
    schedules = relationship("Schedule", back_populates="automation")
    notifications = relationship("Notification", back_populates="automation")
