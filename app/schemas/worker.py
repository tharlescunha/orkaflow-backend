from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.enums import ErrorCategory, RunnerStatus, TaskLogLevel, TaskLogSource, TaskStatus
from app.schemas.common import OrkaBaseSchema


class WorkerRegisterRequest(OrkaBaseSchema):
    uuid: str = Field(..., max_length=100)
    name: str = Field(..., max_length=120)
    label: str | None = Field(default=None, max_length=150)
    host_name: str | None = Field(default=None, max_length=150)
    ip: str | None = Field(default=None, max_length=45)
    os_name: str | None = Field(default=None, max_length=80)
    os_version: str | None = Field(default=None, max_length=80)
    cpu_arch: str | None = Field(default=None, max_length=50)
    memory_total: int | None = None
    access_remote: bool = False


class WorkerRegisterResponse(OrkaBaseSchema):
    runner_id: int
    uuid: str
    name: str
    status: RunnerStatus
    enabled: bool
    token: str
    polling_interval: int
    max_concurrency: int


class WorkerAuthRequest(OrkaBaseSchema):
    uuid: str
    token: str


class WorkerAuthResponse(OrkaBaseSchema):
    authenticated: bool
    runner_id: int
    uuid: str
    status: RunnerStatus
    enabled: bool


class WorkerHeartbeatRequest(OrkaBaseSchema):
    uuid: str
    token: str
    ip: str | None = None
    running_tasks: int = 0


class WorkerHeartbeatResponse(OrkaBaseSchema):
    ok: bool
    runner_id: int
    status: RunnerStatus
    server_time: datetime
    running_tasks: int = 0


class WorkerTaskNextRequest(OrkaBaseSchema):
    uuid: str
    token: str


class WorkerTaskParameterRead(OrkaBaseSchema):
    parameter_name: str
    parameter_value: str | None = None
    is_secret: bool = False
    resolved_from_credential_item_id: int | None = None


class WorkerTaskNextResponse(OrkaBaseSchema):
    found: bool
    task_id: int | None = None
    automation_id: int | None = None
    bot_id: int | None = None
    bot_version_id: int | None = None
    priority: int | None = None
    status: TaskStatus | None = None
    correlation_id: str | None = None
    queue_name: str | None = None
    requested_start_at: datetime | None = None
    timeout_seconds: int | None = None
    inactivity_timeout_seconds: int | None = None
    parameters: list[WorkerTaskParameterRead] = []


class WorkerTaskClaimRequest(OrkaBaseSchema):
    uuid: str
    token: str


class WorkerTaskClaimResponse(OrkaBaseSchema):
    task_id: int
    runner_id: int
    status: TaskStatus


class WorkerTaskStatusUpdateRequest(OrkaBaseSchema):
    uuid: str
    token: str
    status: TaskStatus
    items_processed: int | None = None
    items_failed: int | None = None
    final_message: str | None = None


class WorkerTaskFinishRequest(OrkaBaseSchema):
    uuid: str
    token: str
    status: TaskStatus
    final_message: str | None = None
    items_processed: int = 0
    items_failed: int = 0


class WorkerTaskLogCreate(OrkaBaseSchema):
    uuid: str
    token: str
    level: TaskLogLevel
    message: str
    source: TaskLogSource = TaskLogSource.WORKER
    reference: str | None = None
    error_type: str | None = None
    sequence_number: int | None = None
    event_code: str | None = None


class WorkerTaskLogResponse(OrkaBaseSchema):
    message: str
    task_id: int


class WorkerTaskErrorCreate(OrkaBaseSchema):
    uuid: str
    token: str
    error_type: str = Field(..., max_length=100)
    message: str
    stacktrace: str | None = None
    error_category: ErrorCategory | None = None
    is_retryable: bool = False
    source: TaskLogSource = TaskLogSource.WORKER
    code: str | None = Field(default=None, max_length=80)


class WorkerTaskErrorResponse(OrkaBaseSchema):
    message: str
    task_id: int


class WorkerSyncRequest(BaseModel):
    uuid: str
    token: str
    host_name: str | None = None
    ip: str | None = None


class WorkerSyncResponse(BaseModel):
    runner_id: int
    status: str
    enabled: bool
    polling_interval: int
    max_concurrency: int
    message: str
    bots: list[dict] = []
    