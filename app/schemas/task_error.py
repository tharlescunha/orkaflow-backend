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
    