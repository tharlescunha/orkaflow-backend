from datetime import datetime

from pydantic import Field

from app.domain.enums import RunnerStatus
from app.schemas.common import OrkaBaseSchema


class WorkerReleaseRunner(OrkaBaseSchema):
    id: int
    name: str
    label: str | None = None
    status: RunnerStatus
    enabled: bool
    last_heartbeat: datetime | None = None
    worker_commit: str | None = None
    worker_version: str | None = None
    # None = ainda não dá para saber (máquina sem commit informado ou commit publicado não verificado).
    up_to_date: bool | None = None
    update_requested_at: datetime | None = None
    update_request_stale: bool = False


class WorkerReleaseOverview(OrkaBaseSchema):
    repo_url: str | None = None
    branch: str
    latest_commit: str | None = None
    latest_checked_at: str | None = None
    latest_error: str | None = None
    runners: list[WorkerReleaseRunner]


class WorkerReleaseSettings(OrkaBaseSchema):
    repo_url: str | None = Field(default=None, max_length=500)


class WorkerUpdateRequest(OrkaBaseSchema):
    # Vazio = todas as máquinas ativas.
    runner_ids: list[int] | None = None


class WorkerUpdateResult(OrkaBaseSchema):
    requested: int
