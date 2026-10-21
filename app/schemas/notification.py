from __future__ import annotations

from datetime import datetime

import re

from pydantic import Field, field_validator

from app.schemas.common import OrkaBaseSchema

ALLOWED_METHODS = ("POST", "PUT", "PATCH")
STEP_METHODS = ("GET", "POST", "PUT", "PATCH")
VARIABLE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
MAX_PRE_STEPS = 5


def _clean_headers(value: dict[str, str]) -> dict[str, str]:
    cleaned: dict[str, str] = {}
    for key, val in value.items():
        key = str(key).strip()
        if not key:
            raise ValueError("Cabeçalho com nome vazio.")
        if any(char in key for char in "\r\n:"):
            raise ValueError(f"Nome de cabeçalho inválido: {key!r}.")
        cleaned[key] = str(val)
    return cleaned


class NotificationExtract(OrkaBaseSchema):
    variable: str = Field(..., min_length=1, max_length=60)
    path: str = Field(default="", max_length=200)

    @field_validator("variable")
    @classmethod
    def _variable(cls, value: str):
        value = value.strip()
        if not VARIABLE_NAME_RE.match(value):
            raise ValueError("Nome de variável inválido (use letras, números e _; não comece com número).")
        return value


class NotificationStep(OrkaBaseSchema):
    name: str = Field(default="Etapa", max_length=120)
    method: str = "POST"
    url: str = Field(..., min_length=1, max_length=1000)
    headers: dict[str, str] = {}
    body_template: str = ""
    extract: list[NotificationExtract] = []

    @field_validator("method")
    @classmethod
    def _method(cls, value: str):
        method = value.strip().upper()
        if method not in STEP_METHODS:
            raise ValueError("Método da etapa deve ser GET, POST, PUT ou PATCH.")
        return method

    @field_validator("url")
    @classmethod
    def _url(cls, value: str):
        value = value.strip()
        if not value.lower().startswith(("http://", "https://")):
            raise ValueError("A URL da etapa deve começar com http:// ou https://")
        return value

    @field_validator("headers")
    @classmethod
    def _headers(cls, value: dict[str, str]):
        return _clean_headers(value)


class NotificationChannelRead(OrkaBaseSchema):
    id: int
    name: str
    enabled: bool
    url: str
    method: str
    headers: dict[str, str] = {}
    body_template: str
    timeout_seconds: int
    failure_threshold: int
    pause_schedule: bool
    deactivate_automation: bool
    panel_base_url: str | None = None
    pre_steps: list[NotificationStep] = []
    updated_at: datetime | None = None


class NotificationChannelUpdate(OrkaBaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    enabled: bool | None = None
    url: str | None = Field(default=None, max_length=1000)
    method: str | None = None
    headers: dict[str, str] | None = None
    body_template: str | None = None
    timeout_seconds: int | None = Field(default=None, ge=1, le=120)
    failure_threshold: int | None = Field(default=None, ge=1, le=50)
    pause_schedule: bool | None = None
    deactivate_automation: bool | None = None
    panel_base_url: str | None = Field(default=None, max_length=300)
    pre_steps: list[NotificationStep] | None = Field(default=None, max_length=MAX_PRE_STEPS)

    @field_validator("method")
    @classmethod
    def _method(cls, value: str | None):
        if value is None:
            return value
        method = value.strip().upper()
        if method not in ALLOWED_METHODS:
            raise ValueError("Método deve ser POST, PUT ou PATCH.")
        return method

    @field_validator("url", "panel_base_url")
    @classmethod
    def _url(cls, value: str | None):
        if value is None:
            return value
        value = value.strip()
        if value and not value.lower().startswith(("http://", "https://")):
            raise ValueError("A URL deve começar com http:// ou https://")
        return value

    @field_validator("headers")
    @classmethod
    def _headers(cls, value: dict[str, str] | None):
        if value is None:
            return value
        cleaned: dict[str, str] = {}
        for key, val in value.items():
            key = str(key).strip()
            if not key:
                raise ValueError("Cabeçalho com nome vazio.")
            if any(char in key for char in "\r\n:"):
                raise ValueError(f"Nome de cabeçalho inválido: {key!r}.")
            cleaned[key] = str(val)
        return cleaned


class NotificationTestResult(OrkaBaseSchema):
    ok: bool
    status_code: int | None = None
    response_snippet: str | None = None
    error: str | None = None
    request_preview: dict
    steps: list[dict] = []


class NotificationLogRead(OrkaBaseSchema):
    id: int
    created_at: datetime
    kind: str
    schedule_id: int | None = None
    schedule_name: str | None = None
    automation_name: str | None = None
    task_ids: str | None = None
    ok: bool
    status_code: int | None = None
    error: str | None = None
    response_snippet: str | None = None
    paused_schedule: bool = False


class NotificationLogDetail(NotificationLogRead):
    request: dict | None = None
    steps: list[dict] = []
    response_body: str | None = None


class NotificationVariableRead(OrkaBaseSchema):
    name: str
    description: str
    example: str
