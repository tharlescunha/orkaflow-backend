from datetime import datetime

from pydantic import Field

from app.schemas.common import OrkaBaseSchema


class SyncPreference(OrkaBaseSchema):
    sync_enabled: bool


class SyncCheckPayload(OrkaBaseSchema):
    name: str = Field(..., min_length=1, max_length=120)
    url: str = Field(..., min_length=1, max_length=500)
    server: str | None = Field(default=None, max_length=120)
    project: str | None = Field(default=None, max_length=120)
    interval_seconds: int = Field(default=60, ge=15, le=3600)
    # Vazio = qualquer resposta abaixo de 400 conta como saudável.
    expected_status: int | None = Field(default=None, ge=100, le=599)
    timeout_seconds: int = Field(default=10, ge=1, le=30)
    active: bool = True


class SyncCheckRead(OrkaBaseSchema):
    id: int
    name: str
    url: str
    server: str | None = None
    project: str | None = None
    interval_seconds: int
    expected_status: int | None = None
    timeout_seconds: int
    active: bool
    last_ping_at: datetime | None = None
    last_ok: bool | None = None
    last_status_code: int | None = None
    last_latency_ms: int | None = None
    last_error: str | None = None


class SyncState(OrkaBaseSchema):
    automation_ids: list[int]
    checks: list[SyncCheckRead]


class SyncPicks(OrkaBaseSchema):
    automation_ids: list[int]
