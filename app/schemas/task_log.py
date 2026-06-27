from datetime import datetime

from pydantic import Field

from app.domain.enums import TaskLogLevel, TaskLogSource
from app.schemas.common import OrkaBaseSchema


class TaskLogBase(OrkaBaseSchema):
    task_id: int
    level: TaskLogLevel
    message: str
    reference: str | None = Field(default=None, max_length=255)
    error_type: str | None = Field(default=None, max_length=100)
    source: TaskLogSource | None = None
    sequence_number: int | None = None
    runner_id: int | None = None
    event_code: str | None = Field(default=None, max_length=80)


class TaskLogCreate(TaskLogBase):
    pass


class TaskLogRead(TaskLogBase):
    id: int
    created_at: datetime
    updated_at: datetime | None = None


class TaskLogListItem(OrkaBaseSchema):
    id: int
    task_id: int
    level: TaskLogLevel
    message: str
    reference: str | None = None
    error_type: str | None = None
    source: TaskLogSource | None = None
    sequence_number: int | None = None
    runner_id: int | None = None
    event_code: str | None = None
    created_at: datetime


class TaskLogListResponse(OrkaBaseSchema):
    items: list[TaskLogListItem]
    total: int
    