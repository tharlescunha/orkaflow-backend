from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.common import OrkaBaseSchema


class PermissionRead(OrkaBaseSchema):
    id: int
    module: str
    action: str
    description: str | None = None


class PermissionCreate(OrkaBaseSchema):
    module: str = Field(..., min_length=1, max_length=100)
    action: str = Field(..., min_length=1, max_length=50)
    description: str | None = None


class ProfileBase(OrkaBaseSchema):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    active: bool = True


class ProfileCreate(ProfileBase):
    permission_ids: list[int] = Field(default_factory=list)


class ProfileUpdate(OrkaBaseSchema):
    name: str | None = None
    description: str | None = None
    active: bool | None = None
    permission_ids: list[int] | None = None


class ProfileRead(OrkaBaseSchema):
    id: int
    name: str
    description: str | None
    active: bool
    permissions: list[PermissionRead] = []
    created_at: datetime
    updated_at: datetime | None = None


class ProfileListItem(OrkaBaseSchema):
    id: int
    name: str
    active: bool
    permissions_count: int = 0
    