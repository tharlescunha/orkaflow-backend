from datetime import datetime
from pydantic import Field

from app.domain.enums import TaskStatus
from app.schemas.common import OrkaBaseSchema


class DashboardPeriodOption(str):
    DAY_1 = "1d"
    WEEK_1 = "7d"
    DAYS_15 = "15d"
    MONTH_1 = "30d"


class DashboardFilterParams(OrkaBaseSchema):
    period: str = Field(default="1d", pattern="^(1d|7d|15d|30d)$")
    repository_id: int | None = None
    runner_id: int | None = None
    bot_id: int | None = None


class DashboardSummaryCard(OrkaBaseSchema):
    label: str
    value: int | float
    subtitle: str | None = None


class DashboardOverviewSummary(OrkaBaseSchema):
    total_runners: int
    online_runners: int
    offline_runners: int
    busy_runners: int

    total_bots: int
    total_tasks: int

    success_tasks: int
    error_tasks: int
    running_tasks: int
    queued_tasks: int

    success_rate_percent: float
    avg_queue_seconds: float
    avg_execution_seconds: float


class DashboardTasksPerHourItem(OrkaBaseSchema):
    hour_label: str
    total_tasks: int
    execution_seconds: int


class DashboardRunnerBotRef(OrkaBaseSchema):
    bot_id: int
    bot_name: str


class DashboardRunnerLastExecution(OrkaBaseSchema):
    task_id: int | None = None
    automation_id: int | None = None
    automation_name: str | None = None
    status: TaskStatus | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    execution_duration_seconds: int | None = None
    final_message: str | None = None


class DashboardRunnerMetrics(OrkaBaseSchema):
    runner_id: int
    runner_name: str
    runner_label: str | None = None

    status: str
    enabled: bool
    last_heartbeat: datetime | None = None

    linked_bots_count: int
    linked_bots: list[DashboardRunnerBotRef] = []

    total_tasks: int
    success_tasks: int
    error_tasks: int
    running_tasks: int
    queued_tasks: int

    utilization_percent: float
    avg_queue_seconds: float
    avg_execution_seconds: float

    hottest_hour_label: str | None = None
    hottest_hour_tasks: int = 0

    last_execution: DashboardRunnerLastExecution | None = None


class DashboardBotMachineRef(OrkaBaseSchema):
    runner_id: int
    runner_name: str


class DashboardBotMetrics(OrkaBaseSchema):
    bot_id: int
    bot_name: str
    execution_mode: str | None = None
    current_version: str | None = None
    active: bool = True

    total_tasks: int
    success_tasks: int
    error_tasks: int
    running_tasks: int
    queued_tasks: int

    avg_queue_seconds: float
    avg_execution_seconds: float
    success_rate_percent: float

    runners: list[DashboardBotMachineRef] = []
    last_execution_status: TaskStatus | None = None
    last_execution_at: datetime | None = None


class DashboardRecentTaskItem(OrkaBaseSchema):
    task_id: int
    automation_id: int | None = None
    automation_name: str | None = None
    bot_id: int | None = None
    bot_name: str | None = None
    runner_id: int | None = None
    runner_name: str | None = None
    status: TaskStatus
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    queue_seconds: int | None = None
    execution_duration_seconds: int | None = None
    final_message: str | None = None


class DashboardOverviewResponse(OrkaBaseSchema):
    period: str
    date_from: datetime
    date_to: datetime
    summary: DashboardOverviewSummary
    tasks_per_hour: list[DashboardTasksPerHourItem]
    recent_tasks: list[DashboardRecentTaskItem]


class DashboardRunnersResponse(OrkaBaseSchema):
    period: str
    date_from: datetime
    date_to: datetime
    items: list[DashboardRunnerMetrics]
    total: int


class DashboardBotsResponse(OrkaBaseSchema):
    period: str
    date_from: datetime
    date_to: datetime
    items: list[DashboardBotMetrics]
    total: int
    