from datetime import datetime

from pydantic import Field

from app.domain.enums import RunnerStatus
from app.schemas.common import OrkaBaseSchema


class RunnerConfigBase(OrkaBaseSchema):
    max_concurrency: int = Field(1, ge=1)
    allowed_parallel_bots: dict | list | None = None
    polling_interval: int = Field(15, ge=5)
    auto_update_bots: bool = True
    install_all_bots_on_register: bool = False
    maintenance_mode: bool = False


class RunnerConfigCreate(RunnerConfigBase):
    pass


class RunnerConfigUpdate(OrkaBaseSchema):
    max_concurrency: int | None = Field(default=None, ge=1)
    allowed_parallel_bots: dict | list | None = None
    polling_interval: int | None = Field(default=None, ge=5)
    auto_update_bots: bool | None = None
    install_all_bots_on_register: bool | None = None
    maintenance_mode: bool | None = None


class RunnerConfigRead(RunnerConfigBase):
    id: int
    runner_id: int
    created_at: datetime
    updated_at: datetime | None = None


class RunnerBase(OrkaBaseSchema):
    name: str = Field(..., min_length=1, max_length=120)
    label: str | None = Field(default=None, max_length=150)
    host_name: str | None = Field(default=None, max_length=150)
    ip: str | None = Field(default=None, max_length=45)
    os_name: str | None = Field(default=None, max_length=80)
    os_version: str | None = Field(default=None, max_length=80)
    cpu_arch: str | None = Field(default=None, max_length=50)
    memory_total: int | None = Field(default=None, ge=0)
    access_remote: bool = False
    enabled: bool = True
    status: RunnerStatus = RunnerStatus.OFFLINE


class RunnerCreate(RunnerBase):
    token_hash: str
    config: RunnerConfigCreate | None = None


class RunnerUpdate(OrkaBaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    label: str | None = Field(default=None, max_length=150)
    host_name: str | None = Field(default=None, max_length=150)
    ip: str | None = Field(default=None, max_length=45)
    os_name: str | None = Field(default=None, max_length=80)
    os_version: str | None = Field(default=None, max_length=80)
    cpu_arch: str | None = Field(default=None, max_length=50)
    memory_total: int | None = Field(default=None, ge=0)
    access_remote: bool | None = None
    enabled: bool | None = None
    status: RunnerStatus | None = None


class RunnerRead(RunnerBase):
    id: int
    uuid: str
    last_heartbeat: datetime | None = None
    created_at: datetime
    updated_at: datetime | None = None
    config: RunnerConfigRead | None = None


class RunnerListItem(OrkaBaseSchema):
    id: int
    uuid: str
    name: str
    label: str | None = None
    status: RunnerStatus
    enabled: bool
    host_name: str | None = None
    ip: str | None = None
    last_heartbeat: datetime | None = None
    