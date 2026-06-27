from datetime import datetime

from pydantic import Field

from app.domain.enums import CredentialValueType
from app.schemas.common import OrkaBaseSchema


class CredentialBase(OrkaBaseSchema):
    repository_id: int = Field(..., gt=0)
    label: str = Field(..., min_length=1, max_length=150)
    active: bool = True


class CredentialCreate(CredentialBase):
    pass


class CredentialUpdate(OrkaBaseSchema):
    repository_id: int | None = Field(default=None, gt=0)
    label: str | None = Field(default=None, min_length=1, max_length=150)
    active: bool | None = None


class CredentialRead(CredentialBase):
    id: int
    created_at: datetime
    updated_at: datetime | None = None


class CredentialItemBase(OrkaBaseSchema):
    key: str = Field(..., min_length=1, max_length=120)
    value_type: CredentialValueType = CredentialValueType.SECRET


class CredentialItemCreate(CredentialItemBase):
    value: str = Field(..., min_length=1)


class CredentialItemUpdate(OrkaBaseSchema):
    key: str | None = Field(default=None, min_length=1, max_length=120)
    value_type: CredentialValueType | None = None
    value: str | None = None


class CredentialItemRead(OrkaBaseSchema):
    id: int
    credential_id: int
    key: str = Field(alias="key_name")
    value_type: CredentialValueType
    masked_preview: str | None = None
    created_at: datetime
    updated_at: datetime | None = None

    class Config:
        from_attributes = True
        populate_by_name = True


class CredentialWithItemsRead(CredentialRead):
    items: list[CredentialItemRead] = []


class CredentialItemSecretRead(OrkaBaseSchema):
    id: int
    credential_id: int
    key: str = Field(alias="key_name")
    value_type: CredentialValueType
    value: str

    class Config:
        from_attributes = True
        populate_by_name = True
