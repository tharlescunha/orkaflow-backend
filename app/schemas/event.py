"""Eventos: regras "Quando → Então" e histórico de disparos."""
from datetime import datetime
from typing import Any

from pydantic import Field, field_validator

from app.schemas.common import OrkaBaseSchema
from app.schemas.notification import NotificationStep, _clean_headers

SCOPE_TYPES = ("automation", "bot", "all")
TRIGGER_TYPES = (
    "task_error",
    "task_success",
    "task_timeout",
    "credential_invalid",
    "result_contains",
    "exit_code",
)
MAIN_METHODS = ("POST", "PUT", "PATCH", "GET")


class EventTriggerConfig(OrkaBaseSchema):
    # result_contains: chave (caminho `a.b.c`) e valor esperado (vazio = basta existir)
    key: str | None = Field(default=None, max_length=200)
    value: str | None = Field(default=None, max_length=500)
    # exit_code
    code: int | None = None


class EventRuleBase(OrkaBaseSchema):
    name: str = Field(..., min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=500)
    active: bool = True
    scope_type: str = "automation"
    scope_id: int | None = None
    # Vários alvos (bots ou automações). Se vier, scope_id passa a ser o primeiro da lista.
    scope_ids: list[int] = []
    trigger_type: str
    trigger_config: EventTriggerConfig = EventTriggerConfig()
    pre_steps: list[NotificationStep] = []
    url: str = Field(..., min_length=1, max_length=1000)
    method: str = "POST"
    headers: dict[str, str] = {}
    body_template: str = ""
    timeout_seconds: int = Field(default=15, ge=1, le=120)

    @field_validator("scope_type")
    @classmethod
    def _scope(cls, value: str):
        value = (value or "").strip().lower()
        if value not in SCOPE_TYPES:
            raise ValueError("Escopo deve ser automation, bot ou all.")
        return value

    @field_validator("trigger_type")
    @classmethod
    def _trigger(cls, value: str):
        value = (value or "").strip().lower()
        if value not in TRIGGER_TYPES:
            raise ValueError("Gatilho inválido: " + ", ".join(TRIGGER_TYPES) + ".")
        return value

    @field_validator("method")
    @classmethod
    def _method(cls, value: str):
        method = (value or "").strip().upper()
        if method not in MAIN_METHODS:
            raise ValueError("Método deve ser POST, PUT, PATCH ou GET.")
        return method

    @field_validator("url")
    @classmethod
    def _url(cls, value: str):
        value = value.strip()
        if not value.lower().startswith(("http://", "https://")):
            raise ValueError("A URL deve começar com http:// ou https://")
        return value

    @field_validator("headers")
    @classmethod
    def _headers(cls, value: dict[str, str]):
        return _clean_headers(value)


class EventRuleCreate(EventRuleBase):
    pass


class EventRuleUpdate(EventRuleBase):
    pass


class EventRuleRead(OrkaBaseSchema):
    id: int
    name: str
    description: str | None = None
    active: bool
    scope_type: str
    scope_id: int | None = None
    scope_ids: list[int] = []
    scope_label: str | None = None
    trigger_type: str
    trigger_label: str
    trigger_config: EventTriggerConfig
    pre_steps: list[NotificationStep] = []
    url: str
    method: str
    headers: dict[str, str] = {}
    body_template: str
    timeout_seconds: int
    last_run_at: datetime | None = None
    last_run_ok: bool | None = None
    runs_count: int = 0
    created_at: datetime
    updated_at: datetime | None = None


class EventRunRead(OrkaBaseSchema):
    id: int
    rule_id: int | None = None
    rule_name: str
    task_id: int | None = None
    automation_name: str | None = None
    trigger_type: str
    trigger_label: str
    status: str
    ok: bool
    status_code: int | None = None
    error: str | None = None
    response_snippet: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime


class EventRunDetail(EventRunRead):
    variables: dict[str, Any] = {}
    details: dict[str, Any] | None = None


class EventTestRequest(OrkaBaseSchema):
    # Task usada para montar as variáveis; sem ela, a última task do escopo (ou valores de exemplo).
    task_id: int | None = None


class EventTriggerRead(OrkaBaseSchema):
    type: str
    label: str
    description: str


class EventVariableRead(OrkaBaseSchema):
    name: str
    description: str
    example: str
