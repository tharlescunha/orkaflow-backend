# app\models\automation_parameter.py

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.mssql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import ParameterType
from app.models.base import Base, BaseModelMixin


class AutomationParameter(Base, BaseModelMixin):
    __tablename__ = "automation_parameters"
    __table_args__ = (
        UniqueConstraint("automation_id", "name", name="uq_automation_parameters_automation_id_name"),
    )

    automation_id: Mapped[int] = mapped_column(
        ForeignKey("automations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[str | None] = mapped_column(String(150), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    type: Mapped[ParameterType] = mapped_column(
        Enum(ParameterType, name="parameter_type"),
        nullable=False,
    )
    allowed_values: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    default_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    automation = relationship("Automation", back_populates="parameters")