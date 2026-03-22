from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BaseModelMixin


class AutomationRunner(Base, BaseModelMixin):
    __tablename__ = "automation_runners"
    __table_args__ = (
        UniqueConstraint("automation_id", "runner_id", name="uq_automation_runners_automation_id_runner_id"),
    )

    automation_id: Mapped[int] = mapped_column(
        ForeignKey("automations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    runner_id: Mapped[int] = mapped_column(
        ForeignKey("runners.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    automation = relationship("Automation", back_populates="runner_links")
    runner = relationship("Runner", back_populates="automation_links")