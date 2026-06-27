from sqlalchemy import Boolean, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import NotificationType
from app.models.base import Base, BaseModelMixin, TimestampMixin


class Notification(Base, BaseModelMixin, TimestampMixin):
    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint(
            "automation_id",
            "user_id",
            "notification_type",
            name="uq_notifications_automation_id_user_id_notification_type",
        ),
    )

    automation_id: Mapped[int] = mapped_column(
        ForeignKey("automations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    notification_type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType, name="notification_channel_type"),
        nullable=False,
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    automation = relationship("Automation", back_populates="notifications")
    user = relationship("User", back_populates="notifications")