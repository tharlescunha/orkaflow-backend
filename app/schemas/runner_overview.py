from datetime import datetime
from pydantic import BaseModel

from app.domain.enums import TaskStatus


class RunnerOverviewLinkedBot(BaseModel):
    bot_id: int
    bot_name: str | None = None


class RunnerOverviewTaskItem(BaseModel):
    task_id: int
    automation_id: int | None = None
    automation_name: str | None = None
    status: TaskStatus
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime
    execution_duration_seconds: int | None = None
    final_message: str | None = None


class RunnerOverviewLastExecution(BaseModel):
    task_id: int | None = None
    automation_id: int | None = None
    automation_name: str | None = None
    status: TaskStatus | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    execution_duration_seconds: int | None = None
    final_message: str | None = None


class RunnerOverviewQueue(BaseModel):
    waiting_tasks_count: int = 0
    oldest_waiting_task_id: int | None = None
    oldest_waiting_automation_name: str | None = None
    oldest_waiting_since: datetime | None = None
    oldest_waiting_seconds: int | None = None


class RunnerOverviewSummary(BaseModel):
    linked_bots_count: int = 0

    running_tasks_count: int = 0
    waiting_tasks_count: int = 0
    scheduled_tasks_count: int = 0
    ready_tasks_count: int = 0
    stop_requested_tasks_count: int = 0

    finished_tasks_count: int = 0
    error_tasks_count: int = 0
    timeout_tasks_count: int = 0
    canceled_tasks_count: int = 0
    forced_stop_tasks_count: int = 0

    executed_total_count: int = 0
    success_total_count: int = 0
    error_total_count: int = 0


class RunnerOverviewUtilization(BaseModel):
    registered_seconds: int = 0
    execution_seconds: int = 0
    utilization_percent: float = 0.0


class RunnerOverviewRunnerInfo(BaseModel):
    id: int
    uuid: str
    name: str
    label: str | None = None
    host_name: str | None = None
    ip: str | None = None
    os_name: str | None = None
    os_version: str | None = None
    cpu_arch: str | None = None
    memory_total: int | None = None
    access_remote: bool
    enabled: bool
    status: str
    created_at: datetime
    updated_at: datetime | None = None
    last_heartbeat: datetime | None = None


class RunnerOverviewResponse(BaseModel):
    runner: RunnerOverviewRunnerInfo
    summary: RunnerOverviewSummary
    utilization: RunnerOverviewUtilization
    queue: RunnerOverviewQueue
    last_execution: RunnerOverviewLastExecution
    linked_bots: list[RunnerOverviewLinkedBot] = []
    running_tasks: list[RunnerOverviewTaskItem] = []
    recent_tasks: list[RunnerOverviewTaskItem] = []


class RunnerOverviewListItem(BaseModel):
    runner_id: int
    runner_name: str
    runner_label: str | None = None
    status: str
    enabled: bool
    linked_bots_count: int = 0
    running_tasks_count: int = 0
    waiting_tasks_count: int = 0
    executed_total_count: int = 0
    success_total_count: int = 0
    error_total_count: int = 0
    utilization_percent: float = 0.0
    last_execution_at: datetime | None = None
    last_execution_status: TaskStatus | None = None


class RunnerOverviewListResponse(BaseModel):
    items: list[RunnerOverviewListItem]
    total: int
    