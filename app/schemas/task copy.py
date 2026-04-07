# app/schemas/task.py

from datetime import datetime
from typing import Any

from pydantic import Field

from app.domain.enums import ExecutionMode, TaskStatus
from app.schemas.common import OrkaBaseSchema


class TaskParameterBase(OrkaBaseSchema):
    parameter_name: str = Field(..., max_length=100)
    parameter_value: str | None = None
    is_secret: bool = False
    resolved_from_credential_item_id: int | None = None


class TaskParameterCreate(TaskParameterBase):
    pass


class TaskParameterRead(TaskParameterBase):
    id: int
    task_id: int


class TaskBase(OrkaBaseSchema):
    automation_id: int
    bot_version_id: int | None = None
    runner_id: int | None = None
    schedule_id: int | None = None
    parent_task_id: int | None = None
    priority: int = 5
    requested_start_at: datetime | None = None
    timeout_seconds: int | None = None
    execution_mode: ExecutionMode = ExecutionMode.MANUAL
    correlation_id: str | None = Field(default=None, max_length=100)
    queue_name: str | None = Field(default=None, max_length=100)
    inactivity_timeout_seconds: int | None = None


class TaskCreate(TaskBase):
    parameters: list[TaskParameterCreate] = []


class TaskUpdate(OrkaBaseSchema):
    runner_id: int | None = None
    priority: int | None = None
    requested_start_at: datetime | None = None
    timeout_seconds: int | None = None
    queue_name: str | None = Field(default=None, max_length=100)
    inactivity_timeout_seconds: int | None = None


class TaskStatusUpdate(OrkaBaseSchema):
    status: TaskStatus
    final_message: str | None = None
    items_processed: int | None = None
    items_failed: int | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    last_update_at: datetime | None = None
    retry_count: int | None = None
    dispatch_attempts: int | None = None
    stop_requested: bool | None = None


class TaskActionResponse(OrkaBaseSchema):
    message: str
    task_id: int
    status: TaskStatus


class TaskRead(OrkaBaseSchema):
    id: int
    automation_id: int
    bot_version_id: int
    runner_id: int | None = None
    created_by: int | None = None
    schedule_id: int | None = None
    parent_task_id: int | None = None
    priority: int
    status: TaskStatus
    requested_start_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    last_update_at: datetime | None = None
    final_message: str | None = None
    items_processed: int
    items_failed: int
    timeout_seconds: int
    retry_count: int
    execution_mode: ExecutionMode
    dispatch_attempts: int
    stop_requested: bool
    correlation_id: str | None = None
    queue_name: str | None = None
    inactivity_timeout_seconds: int | None = None
    runner_claimed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None = None
    parameters: list[TaskParameterRead] = []


class TaskListItem(OrkaBaseSchema):
    id: int
    automation_id: int
    automation_name: str | None = None

    bot_version_id: int
    bot_version_label: str | None = None

    runner_id: int | None = None
    runner_name: str | None = None

    created_by: int | None = None
    created_by_name: str | None = None

    schedule_id: int | None = None
    priority: int
    status: TaskStatus

    requested_start_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    last_update_at: datetime | None = None
    created_at: datetime

    items_processed: int
    items_failed: int

    execution_mode: ExecutionMode
    stop_requested: bool
    correlation_id: str | None = None
    queue_name: str | None = None

    final_message: str | None = None

    execution_duration_seconds: int | None = None


class TaskListResponse(OrkaBaseSchema):
    items: list[TaskListItem]
    total: int


class TaskParameterListResponse(OrkaBaseSchema):
    items: list[TaskParameterRead]
    total: int


class TaskFilters(OrkaBaseSchema):
    status: TaskStatus | None = None
    automation_id: int | None = None
    runner_id: int | None = None
    created_by: int | None = None


class TaskManualCreateResponse(OrkaBaseSchema):
    message: str
    task: TaskRead
    