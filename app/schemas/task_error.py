# app/schemas/task_error.py

from datetime import datetime

from pydantic import Field

from app.domain.enums import ErrorCategory, TaskLogSource
from app.schemas.common import OrkaBaseSchema


class TaskErrorBase(OrkaBaseSchema):
    task_id: int
    error_type: str = Field(..., max_length=100)
    message: str
    stacktrace: str | None = None
    error_category: ErrorCategory | None = None
    is_retryable: bool = False
    source: TaskLogSource | None = None
    code: str | None = Field(default=None, max_length=80)


class TaskErrorCreate(TaskErrorBase):
    pass


class TaskErrorRead(TaskErrorBase):
    id: int
    created_at: datetime
    updated_at: datetime | None = None


class TaskErrorListItem(OrkaBaseSchema):
    id: int
    task_id: int
    error_type: str
    message: str
    stacktrace: str | None = None
    error_category: ErrorCategory | None = None
    is_retryable: bool
    source: TaskLogSource | None = None
    code: str | None = None
    created_at: datetime


class TaskErrorListResponse(OrkaBaseSchema):
    items: list[TaskErrorListItem]
    total: int


class TaskErrorRichListItem(OrkaBaseSchema):
    id: int
    task_id: int
    error_type: str
    message: str
    stacktrace: str | None = None
    error_category: ErrorCategory | None = None
    is_retryable: bool
    source: TaskLogSource | None = None
    code: str | None = None
    created_at: datetime

    task_status: str | None = None

    automation_id: int | None = None
    automation_name: str | None = None
    automation_label: str | None = None

    bot_id: int | None = None
    bot_name: str | None = None

    bot_version_id: int | None = None
    bot_version_label: str | None = None

    repository_id: int | None = None
    repository_name: str | None = None

    runner_id: int | None = None
    runner_name: str | None = None
    runner_label: str | None = None

    created_by: int | None = None
    created_by_name: str | None = None

    final_message: str | None = None

    task_created_at: datetime | None = None
    task_started_at: datetime | None = None
    task_finished_at: datetime | None = None

    execution_duration_seconds: int | None = None


class TaskErrorRichListResponse(OrkaBaseSchema):
    items: list[TaskErrorRichListItem]
    total: int
    