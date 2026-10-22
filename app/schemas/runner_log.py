from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import OrkaBaseSchema

MAX_LINES_PER_BATCH = 500
MAX_MESSAGE_LENGTH = 4000


class WorkerLogLine(BaseModel):
    # BaseModel puro: não tira espaços (preserva indentação de traceback).
    logged_at: datetime
    level: str = Field(default="INFO", max_length=20)
    message: str


class WorkerLogBatchRequest(OrkaBaseSchema):
    uuid: str
    token: str
    lines: list[WorkerLogLine] = Field(default_factory=list, max_length=MAX_LINES_PER_BATCH)


class WorkerLogBatchResponse(OrkaBaseSchema):
    accepted: int


class RunnerLogLineRead(OrkaBaseSchema):
    id: int
    runner_id: int
    logged_at: datetime
    level: str
    source: str
    task_id: int | None = None
    message: str


class RunnerLogPage(OrkaBaseSchema):
    items: list[RunnerLogLineRead]
    last_id: int | None = None
    retention_days: int
