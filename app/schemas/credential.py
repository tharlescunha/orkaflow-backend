from datetime import datetime

from pydantic import Field

from app.schemas.common import OrkaBaseSchema


class CredentialBase(OrkaBaseSchema):
    repository_id: int = Field(..., gt=0)
    name: str = Field(..., min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    active: bool = True


class CredentialCreate(CredentialBase):
    pass


class CredentialUpdate(OrkaBaseSchema):
    repository_id: int | None = Field(default=None, gt=0)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    active: bool | None = None


class CredentialRead(CredentialBase):
    id: int
    created_at: datetime
    updated_at: datetime | None = None


class CredentialItemBase(OrkaBaseSchema):
    key: str = Field(..., min_length=1, max_length=100)
    value_type: str = Field(..., min_length=1, max_length=50)
    active: bool = True


class CredentialItemCreate(CredentialItemBase):
    value: str = Field(..., min_length=1)
    notes: str | None = Field(default=None, max_length=500)


class CredentialItemUpdate(OrkaBaseSchema):
    key: str | None = Field(default=None, min_length=1, max_length=100)
    value_type: str | None = Field(default=None, min_length=1, max_length=50)
    value: str | None = None
    notes: str | None = Field(default=None, max_length=500)
    active: bool | None = None


class CredentialItemRead(CredentialItemBase):
    id: int
    credential_id: int
    masked_preview: str | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class CredentialWithItemsRead(CredentialRead):
    items: list[CredentialItemRead] = []


class CredentialItemSecretRead(OrkaBaseSchema):
    id: int
    credential_id: int
    key: str
    value_type: str
    value: str
    active: bool
    