from sqlalchemy import Boolean, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BaseModelMixin, TimestampMixin


class AutomationSuccessTrigger(Base, BaseModelMixin, TimestampMixin):
    __tablename__ = "automation_success_triggers"
    __table_args__ = (
        UniqueConstraint(
            "source_automation_id",
            "target_automation_id",
            name="uq_automation_success_triggers_source_target",
        ),
    )

    source_automation_id: Mapped[int] = mapped_column(
        ForeignKey("automations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_automation_id: Mapped[int] = mapped_column(
        ForeignKey("automations.id", ondelete="NO ACTION"),
        nullable=False,
        index=True,
    )
    priority_override: Mapped[int | None] = mapped_column(Integer, nullable=True)
    inherit_parent_parameters: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    source_automation = relationship(
        "Automation",
        foreign_keys=[source_automation_id],
        back_populates="success_trigger_links",
    )
    target_automation = relationship(
        "Automation",
        foreign_keys=[target_automation_id],
    )
