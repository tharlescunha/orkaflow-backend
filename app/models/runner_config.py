from sqlalchemy import Boolean, ForeignKey, Integer
from sqlalchemy.dialects.mssql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BaseModelMixin, TimestampMixin


class RunnerConfig(Base, BaseModelMixin, TimestampMixin):
    __tablename__ = "runner_configs"

    runner_id: Mapped[int] = mapped_column(
        ForeignKey("runners.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    max_concurrency: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    allowed_parallel_bots: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    polling_interval: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    auto_update_bots: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    install_all_bots_on_register: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    maintenance_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    runner = relationship("Runner", back_populates="config")
    