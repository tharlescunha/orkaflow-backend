from datetime import datetime
import re

from pydantic import Field, field_validator

from app.schemas.common import OrkaBaseSchema


SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


class BotVersionBase(OrkaBaseSchema):
    bot_id: int
    version: str = Field(..., min_length=1, max_length=50)
    storage_type: str = Field(..., min_length=1, max_length=50)
    commit_hash: str | None = Field(default=None, max_length=80)
    branch: str | None = Field(default=None, max_length=120)
    artifact_path: str | None = Field(default=None, max_length=500)
    changelog: str | None = None
    checksum: str | None = Field(default=None, max_length=255)
    created_by: int | None = None
    is_active: bool = True

    @field_validator("version")
    @classmethod
    def validate_version(cls, value: str) -> str:
        value = value.strip()
        if not SEMVER_RE.match(value):
            raise ValueError("A versão deve estar no formato 1.0.0.")
        return value


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

    @field_validator("version")
    @classmethod
    def validate_version(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not SEMVER_RE.match(value):
            raise ValueError("A versão deve estar no formato 1.0.0.")
        return value


class BotVersionResponse(OrkaBaseSchema):
    id: int
    bot_id: int
    bot_name: str | None = None
    version: str
    storage_type: str
    commit_hash: str | None = None
    branch: str | None = None
    artifact_path: str | None = None
    changelog: str | None = None
    checksum: str | None = None
    created_by: int | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime | None = None
    