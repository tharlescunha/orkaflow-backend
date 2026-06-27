# app\models\automation.py

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
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
    default_parameters_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    default_runtime_parameters_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    bot = relationship("Bot", back_populates="automations")
    repository = relationship("Repository", back_populates="automations")
    runner_links = relationship("AutomationRunner", back_populates="automation")
    exclusive_group_links = relationship(
        "AutomationExclusiveGroupMember",
        back_populates="automation",
        cascade="all, delete-orphan",
    )
    success_trigger_links = relationship(
        "AutomationSuccessTrigger",
        foreign_keys="AutomationSuccessTrigger.source_automation_id",
        back_populates="source_automation",
        cascade="all, delete-orphan",
    )
    parameters = relationship("AutomationParameter", back_populates="automation")
    tasks = relationship("Task", back_populates="automation")
    schedules = relationship("Schedule", back_populates="automation")
    notifications = relationship("Notification", back_populates="automation")
