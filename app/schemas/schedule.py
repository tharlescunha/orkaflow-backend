# app\schemas\schedule.py

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from app.domain.enums import SchedulePolicy, ScheduleStatus, ScheduleType, CalendarType


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

    @field_validator("interval_value")
    @classmethod
    def validate_interval_value(cls, value: Optional[int]):
        if value is not None and value <= 0:
            raise ValueError("interval_value deve ser maior que zero")
        return value


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

    @field_validator("interval_value")
    @classmethod
    def validate_interval_value(cls, value: Optional[int]):
        if value is not None and value <= 0:
            raise ValueError("interval_value deve ser maior que zero")
        return value


class ScheduleResponse(ScheduleBase):
    id: int
    status: Optional[ScheduleStatus] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    misfire_policy: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
    
