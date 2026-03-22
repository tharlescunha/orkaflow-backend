from sqlalchemy import Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import CredentialValueType
from app.models.base import Base, BaseModelMixin, TimestampMixin


class CredentialItem(Base, BaseModelMixin, TimestampMixin):
    __tablename__ = "credential_items"
    __table_args__ = (
        UniqueConstraint("credential_id", "key_name", name="uq_credential_items_credential_id_key_name"),
    )

    credential_id: Mapped[int] = mapped_column(
        ForeignKey("credentials.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key_name: Mapped[str] = mapped_column(String(120), nullable=False)
    encrypted_value: Mapped[str] = mapped_column(Text, nullable=False)
    value_type: Mapped[CredentialValueType] = mapped_column(
        Enum(CredentialValueType, name="credential_value_type"),
        nullable=False,
        default=CredentialValueType.SECRET,
    )
    masked_preview: Mapped[str | None] = mapped_column(String(120), nullable=True)

    credential = relationship("Credential", back_populates="items")