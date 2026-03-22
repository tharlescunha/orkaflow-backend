from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BaseModelMixin, TimestampMixin


class Credential(Base, BaseModelMixin, TimestampMixin):
    __tablename__ = "credentials"
    __table_args__ = (
        UniqueConstraint("repository_id", "label", name="uq_credentials_repository_id_label"),
    )

    label: Mapped[str] = mapped_column(String(150), nullable=False)
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="NO ACTION"),
        nullable=False,
        index=True,
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    repository = relationship("Repository", back_populates="credentials")
    items = relationship("CredentialItem", back_populates="credential")