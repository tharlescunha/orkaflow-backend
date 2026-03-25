from datetime import datetime

from pydantic import Field

from app.schemas.common import OrkaBaseSchema


class BotBase(OrkaBaseSchema):
    name: str = Field(..., min_length=1, max_length=120)
    technology: str = Field(..., min_length=1, max_length=50)
    repository_id: int
    source_type: str = Field(..., min_length=1, max_length=50)
    source_url: str | None = Field(default=None, max_length=500)
    entrypoint: str = Field(..., min_length=1, max_length=255)
    requirements_file: str | None = Field(default=None, max_length=255)
    timeout_default: int = Field(..., ge=1)
    active: bool = True


class BotCreate(BotBase):
    pass


class BotUpdate(OrkaBaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    technology: str | None = Field(default=None, min_length=1, max_length=50)
    source_type: str | None = Field(default=None, min_length=1, max_length=50)
    source_url: str | None = Field(default=None, max_length=500)
    entrypoint: str | None = Field(default=None, min_length=1, max_length=255)
    requirements_file: str | None = Field(default=None, max_length=255)
    timeout_default: int | None = Field(default=None, ge=1)
    active: bool | None = None


class BotResponse(BotBase):
    id: int
    current_version: str | None = None
    release_version: str | None = None
    created_at: datetime
    updated_at: datetime | None = None
    