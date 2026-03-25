from datetime import datetime

from pydantic import Field

from app.schemas.common import OrkaBaseSchema


class BotVersionBase(OrkaBaseSchema):
    bot_id: int
    version: str = Field(..., min_length=1, max_length=50)
    storage_type: str = Field(..., min_length=1, max_length=50)
    artifact_path: str | None = Field(default=None, max_length=500)
    changelog: str | None = None
    checksum: str | None = Field(default=None, max_length=255)
    created_by: int | None = None
    is_active: bool = True


class BotVersionCreate(BotVersionBase):
    pass


class BotVersionUpdate(OrkaBaseSchema):
    version: str | None = Field(default=None, min_length=1, max_length=50)
    storage_type: str | None = Field(default=None, min_length=1, max_length=50)
    artifact_path: str | None = Field(default=None, max_length=500)
    changelog: str | None = None
    checksum: str | None = Field(default=None, max_length=255)
    created_by: int | None = None
    is_active: bool | None = None


class BotVersionResponse(BotVersionBase):
    id: int
    created_at: datetime
    updated_at: datetime | None = None
    