# app\schemas\schedule.py

from datetime import datetime
from typing import Any, Optional

from pydantic import AliasChoices, BaseModel, Field, field_validator

from app.domain.enums import SchedulePolicy, ScheduleStatus, ScheduleType, CalendarType


def _clean_policy(value: str) -> str:
    value = (value or "defer").strip().lower()
    if value not in ("skip", "defer"):
        raise ValueError("calendar_policy aceita só 'skip' ou 'defer'.")
    return value


def _clean_retry_on(value: list[str]) -> list[str]:
    cleaned = [str(v).strip().lower() for v in (value or [])]
    bad = [v for v in cleaned if v not in ("erro", "timeout")]
    if bad:
        raise ValueError("retry_on aceita só 'erro' e 'timeout'.")
    return cleaned or ["erro", "timeout"]


class ScheduleBase(BaseModel):
    name: str = Field(..., max_length=150)
    automation_id: int
    priority: int = Field(default=5, ge=1, le=10)
    schedule_type: ScheduleType
    calendar_type: Optional[CalendarType] = None
    cron_expression: Optional[str] = None
    policy: SchedulePolicy
    runtime_parameters_json: Optional[dict[str, Any]] = None
    use_default_runtime_parameters: bool = True
    timezone: str = Field(default="UTC", max_length=100)
    active: bool = True
    interval_value: Optional[int] = None
    interval_unit: Optional[str] = Field(default=None, max_length=30)
    # Retentativa automática: 0 a 5 tentativas extras, espera em segundos, em quais falhas.
    retry_max: int = Field(default=0, ge=0, le=5)
    retry_delay_seconds: int = Field(default=300, ge=0, le=86400)
    retry_on: list[str] = Field(default_factory=lambda: ["erro", "timeout"])

    @field_validator("interval_value")
    @classmethod
    def validate_interval_value(cls, value: Optional[int]):
        if value is not None and value <= 0:
            raise ValueError("interval_value deve ser maior que zero")
        return value

    # Calendário de dias úteis (opcional) e o que fazer num horário não permitido.
    calendar_id: Optional[int] = None
    calendar_policy: str = "defer"

    @field_validator("retry_on")
    @classmethod
    def validate_retry_on(cls, value: list[str]):
        return _clean_retry_on(value)

    @field_validator("calendar_policy")
    @classmethod
    def validate_calendar_policy(cls, value: str):
        return _clean_policy(value)


class ScheduleCreate(ScheduleBase):
    pass


class ScheduleUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=150)
    automation_id: Optional[int] = None
    priority: Optional[int] = Field(default=None, ge=1, le=10)
    schedule_type: Optional[ScheduleType] = None
    calendar_type: Optional[CalendarType] = None
    cron_expression: Optional[str] = None
    policy: Optional[SchedulePolicy] = None
    runtime_parameters_json: Optional[dict[str, Any]] = None
    use_default_runtime_parameters: Optional[bool] = None
    timezone: Optional[str] = Field(default=None, max_length=100)
    active: Optional[bool] = None
    status: Optional[ScheduleStatus] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    interval_value: Optional[int] = None
    interval_unit: Optional[str] = Field(default=None, max_length=30)
    misfire_policy: Optional[str] = None
    retry_max: Optional[int] = Field(default=None, ge=0, le=5)
    retry_delay_seconds: Optional[int] = Field(default=None, ge=0, le=86400)
    retry_on: Optional[list[str]] = None
    calendar_id: Optional[int] = None
    calendar_policy: Optional[str] = None

    @field_validator("interval_value")
    @classmethod
    def validate_interval_value(cls, value: Optional[int]):
        if value is not None and value <= 0:
            raise ValueError("interval_value deve ser maior que zero")
        return value

    @field_validator("retry_on")
    @classmethod
    def validate_retry_on(cls, value: Optional[list[str]]):
        return None if value is None else _clean_retry_on(value)

    @field_validator("calendar_policy")
    @classmethod
    def validate_calendar_policy(cls, value: Optional[str]):
        return None if value is None else _clean_policy(value)


class ScheduleResponse(ScheduleBase):
    id: int
    # O modelo guarda retry_on_json; a resposta expõe retry_on.
    retry_on: list[str] = Field(
        default_factory=lambda: ["erro", "timeout"],
        validation_alias=AliasChoices("retry_on", "retry_on_json"),
    )

    @field_validator("retry_on", mode="before")
    @classmethod
    def _retry_on_default(cls, value):
        return value if isinstance(value, list) and value else ["erro", "timeout"]

    # Nome do calendário para a tela (lido da relação).
    calendar_name: Optional[str] = Field(default=None, validation_alias=AliasChoices("calendar_name", "calendar"))

    @field_validator("calendar_name", mode="before")
    @classmethod
    def _calendar_name(cls, value):
        if value is None or isinstance(value, str):
            return value
        return getattr(value, "name", None)
    status: Optional[ScheduleStatus] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    misfire_policy: Optional[str] = None
    last_error: Optional[str] = None
    last_skipped_reason: Optional[str] = None
    last_skipped_at: Optional[datetime] = None
    paused_reason: Optional[str] = None
    paused_credential_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
    
