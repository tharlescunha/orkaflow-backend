from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BaseModelMixin, TimestampMixin


class AutomationExclusiveGroup(Base, BaseModelMixin, TimestampMixin):
    __tablename__ = "automation_exclusive_groups"
    __table_args__ = (
        UniqueConstraint("name", name="uq_automation_exclusive_groups_name"),
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    label: Mapped[str | None] = mapped_column(String(150), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    automation_links = relationship(
        "AutomationExclusiveGroupMember",
        back_populates="group",
        cascade="all, delete-orphan",
    )


class AutomationExclusiveGroupMember(Base, BaseModelMixin):
    __tablename__ = "automation_exclusive_group_members"
    __table_args__ = (
        UniqueConstraint(
            "group_id",
            "automation_id",
            name="uq_automation_exclusive_group_members_group_automation",
        ),
    )

    group_id: Mapped[int] = mapped_column(
        ForeignKey("automation_exclusive_groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    automation_id: Mapped[int] = mapped_column(
        ForeignKey("automations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    group = relationship("AutomationExclusiveGroup", back_populates="automation_links")
    automation = relationship("Automation", back_populates="exclusive_group_links")
