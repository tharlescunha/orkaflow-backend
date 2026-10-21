from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.common import OrkaBaseSchema


class EnvVariableRead(OrkaBaseSchema):
    id: int
    name: str
    scope_type: str
    scope_id: int
    scope_label: str
    is_secret: bool
    value: str | None = None  # None quando secreta: o valor nunca sai pela API
    description: str | None = None
    active: bool
    updated_at: datetime | None = None


class EnvVariableCreate(OrkaBaseSchema):
    name: str = Field(..., min_length=1, max_length=120)
    scope_type: str = Field(..., description="global | bot | automation | runner")
    scope_id: int | None = None
    value: str = Field(default="", max_length=20000)
    is_secret: bool = False
    description: str | None = Field(default=None, max_length=300)
    active: bool = True


class EnvVariableUpdate(OrkaBaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    value: str | None = Field(default=None, max_length=20000)  # None = manter o valor atual
    is_secret: bool | None = None
    description: str | None = Field(default=None, max_length=300)
    active: bool | None = None


class EnvVariableOverride(OrkaBaseSchema):
    scope_type: str
    scope_label: str


class EnvVariableEffective(OrkaBaseSchema):
    name: str
    value: str | None = None
    is_secret: bool
    scope_type: str
    scope_id: int
    scope_label: str
    overrides: list[EnvVariableOverride] = []


class WorkerTaskEnvResponse(OrkaBaseSchema):
    variables: dict[str, str] = {}
    secret_names: list[str] = []
