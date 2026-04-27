from datetime import datetime

from pydantic import BaseModel


class AutomationHealthTaskResponse(BaseModel):
    id: int | None = None
    status: str | None = None
    runner_id: int | None = None
    runner_name: str | None = None
    runner_label: str | None = None
    runner_display_name: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    last_update_at: datetime | None = None
    final_message: str | None = None
    execution_duration_seconds: int | None = None


class AutomationHealthScheduleResponse(BaseModel):
    id: int
    name: str
    schedule_type: str
    calendar_type: str | None = None
    cron_expression: str | None = None
    interval_value: int | None = None
    interval_unit: str | None = None
    timezone: str
    active: bool
    status: str | None = None
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    expected_interval_seconds: int | None = None
    rule_label: str | None = None


class AutomationHealthItemResponse(BaseModel):
    automation_id: int
    automation_name: str
    automation_label: str | None = None
    automation_description: str | None = None
    automation_active: bool

    repository_id: int | None = None
    repository_name: str | None = None

    bot_id: int | None = None
    bot_name: str | None = None
    bot_active: bool | None = None

    health_status: str
    health_label: str
    status_color: str

    monitored_at: datetime
    last_execution_at: datetime | None = None
    is_overdue: bool
    has_recent_success: bool
    has_recent_error: bool
    has_running_task: bool

    machine_name: str | None = None
    machine_label: str | None = None
    machine_display_name: str | None = None

    schedule: AutomationHealthScheduleResponse | None = None
    last_task: AutomationHealthTaskResponse | None = None


class AutomationHealthListResponse(BaseModel):
    items: list[AutomationHealthItemResponse]
    total: int
    