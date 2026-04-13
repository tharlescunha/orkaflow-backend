from datetime import datetime

from pydantic import Field

from app.schemas.common import OrkaBaseSchema


class BotBase(OrkaBaseSchema):
    name: str = Field(..., min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    technology: str = Field(..., min_length=1, max_length=50)
    repository_id: int
    source_type: str = Field(..., min_length=1, max_length=50)
    execution_mode: str = Field(default="background", pattern="^(background|foreground)$")
    source_url: str | None = Field(default=None, max_length=500)
    entrypoint: str = Field(..., min_length=1, max_length=255)
    requirements_file: str | None = Field(default=None, max_length=255)
    timeout_default: int = Field(..., ge=1)
    active: bool = True


class BotCreate(BotBase):
    initial_version: str = Field(..., min_length=1, max_length=50)


class BotUpdate(OrkaBaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    technology: str | None = Field(default=None, min_length=1, max_length=50)
    repository_id: int | None = None
    source_type: str | None = Field(default=None, min_length=1, max_length=50)
    execution_mode: str | None = Field(default=None, pattern="^(background|foreground)$")
    source_url: str | None = Field(default=None, max_length=500)
    entrypoint: str | None = Field(default=None, min_length=1, max_length=255)
    requirements_file: str | None = Field(default=None, max_length=255)
    timeout_default: int | None = Field(default=None, ge=1)
    release_version: str | None = Field(default=None, min_length=1, max_length=50)
    active: bool | None = None


class BotRead(BotBase):
    id: int
    repository_name: str | None = None
    current_version: str | None = None
    release_version: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class BotListItem(OrkaBaseSchema):
    id: int
    name: str
    description: str | None = None
    repository_id: int
    repository_name: str | None = None
    execution_mode: str
    current_version: str | None = None
    release_version: str | None = None
    active: bool
    created_at: datetime


class BotListResponse(OrkaBaseSchema):
    items: list[BotListItem]
    total: int
    