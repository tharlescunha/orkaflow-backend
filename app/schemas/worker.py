from typing import Any
from datetime import datetime
from pydantic import BaseModel, Field

from app.domain.enums import ErrorCategory, RunnerStatus, TaskLogLevel, TaskLogSource, TaskStatus
from app.schemas.common import OrkaBaseSchema
import base64


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
    # Usuário do Windows em que o worker roda (DOMINIO\usuario). Opcional: worker antigo não manda.
    os_user: str | None = None


class WorkerHeartbeatResponse(OrkaBaseSchema):
    ok: bool
    runner_id: int
    status: RunnerStatus
    server_time: datetime
    running_tasks: int = 0


class WorkerScreenshotUploadRequest(OrkaBaseSchema):
    uuid: str
    token: str
    image_base64: str = Field(..., min_length=1)
    content_type: str = Field(default="image/png", max_length=50)


class WorkerScreenshotUploadResponse(OrkaBaseSchema):
    message: str
    runner_id: int
    last_screenshot_at: datetime


class WorkerTaskNextRequest(OrkaBaseSchema):
    uuid: str
    token: str
    execution_mode: str = Field(
        ...,
        pattern="^(background|foreground)$",
        description="Define se o worker quer tasks de background ou foreground",
    )


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
    execution_mode: str | None = None
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

class WorkerTaskStatusCheckRequest(OrkaBaseSchema):
    uuid: str
    token: str


class WorkerTaskStatusCheckResponse(OrkaBaseSchema):
    task_id: int
    status: TaskStatus
    stop_requested: bool = False
    runner_id: int | None = None
    exists: bool = True
    

class WorkerTaskStatusUpdateRequest(OrkaBaseSchema):
    uuid: str
    token: str
    status: TaskStatus
    items_processed: int | None = None
    items_failed: int | None = None
    final_message: str | None = None
    result_json: str | None = None


class WorkerTaskFinishRequest(OrkaBaseSchema):
    uuid: str
    token: str
    status: TaskStatus
    final_message: str | None = None
    result_json: str | None = None
    # None = "não informado": não sobrescreve os contadores já registrados na task.
    items_processed: int | None = None
    items_failed: int | None = None


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


class WorkerTaskProgressRequest(OrkaBaseSchema):
    """Etapa atual informada pelo robô pelo maestro.step (o worker repassa quando muda)."""

    uuid: str
    token: str
    current: int = Field(..., ge=0)
    total: int | None = Field(default=None, ge=0)
    text: str | None = Field(default=None, max_length=200)


class WorkerTaskProgressResponse(OrkaBaseSchema):
    task_id: int
    progress_current: int | None = None
    progress_total: int | None = None
    progress_text: str | None = None


class WorkerTaskAttachmentCreate(OrkaBaseSchema):
    """Arquivo anexado pelo robô (maestro.attach), em base64. Até 5 MB por arquivo."""

    uuid: str
    token: str
    filename: str = Field(..., min_length=1, max_length=255)
    content_type: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=300)
    content_base64: str


class WorkerTaskAttachmentResponse(OrkaBaseSchema):
    task_id: int
    attachment_id: int
    size_bytes: int


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

    # Imagem do erro enviada pelo worker em base64
    error_screenshot_base64: str | None = None


class WorkerTaskErrorResponse(OrkaBaseSchema):
    message: str
    task_id: int


class WorkerCredentialResolveRequest(OrkaBaseSchema):
    uuid: str
    token: str
    keys: list[str] | None = None
    # Task que está usando a credencial: o backend confere que ela é do mesmo repositório da
    # automação. Opcional por uma versão (workers antigos não mandam).
    task_id: int | None = None


class WorkerCredentialAlertRequest(OrkaBaseSchema):
    """Robô avisou (linha ORKAFLOW_ALERTA_CREDENCIAL ou saída 3) que a credencial não serve mais."""

    uuid: str
    token: str
    credential_id: int | None = None
    chave: str | None = Field(default=None, max_length=120)
    # senha_incorreta | senha_expirada | usuario_bloqueado | invalida
    motivo: str = Field(default="invalida", max_length=40)
    mensagem: str | None = Field(default=None, max_length=1000)
    sistema: str | None = Field(default=None, max_length=80)


class WorkerCredentialAlertResponse(OrkaBaseSchema):
    task_id: int
    credential_id: int | None = None
    status: str
    schedules_paused: int = 0


class WorkerCredentialResolveResponse(OrkaBaseSchema):
    dados_acesso: dict[str, str | None] = {}


class WorkerTaskActiveListRequest(OrkaBaseSchema):
    uuid: str
    token: str


class WorkerTaskActiveItem(OrkaBaseSchema):
    id: int
    automation_id: int
    runner_id: int | None = None
    status: TaskStatus
    lock_key: str | None = None


class WorkerTaskActiveListResponse(OrkaBaseSchema):
    items: list[WorkerTaskActiveItem] = []
    total: int = 0


class WorkerTaskReleaseStartupLocksRequest(OrkaBaseSchema):
    uuid: str
    token: str


class WorkerTaskReleaseStartupLocksResponse(OrkaBaseSchema):
    message: str
    runner_id: int
    tasks_finalized: int = 0
    task_locks_released: int = 0
    runner_locks_released: int = 0


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


class WorkerTaskTelemetryCreate(OrkaBaseSchema):
    uuid: str
    token: str

    captured_at: datetime

    execution_started_at: datetime | None = None
    execution_finished_at: datetime | None = None
    duration_seconds: float | None = None

    cpu_percent_avg: float | None = None
    cpu_percent_peak: float | None = None

    memory_used_mb_avg: float | None = None
    memory_used_mb_peak: float | None = None
    process_memory_mb_peak: float | None = None

    disk_read_mb: float | None = None
    disk_write_mb: float | None = None

    net_sent_mb: float | None = None
    net_recv_mb: float | None = None

    exit_code: int | None = None

    telemetry_status: str | None = None
    message: str | None = None

    payload_json: str | None = None


class WorkerTaskTelemetryResponse(OrkaBaseSchema):
    message: str
    task_id: int


class WorkerRuntimeEventCreate(OrkaBaseSchema):
    uuid: str
    token: str

    # Limites não são validados aqui (viram 422 e o evento se perderia):
    # o service trunca event_type/reason e normaliza execution_mode.
    event_type: str

    # task_id/automation_id/bot_id são opcionais (ex.: sync_failed, bot_install_failed).
    task_id: int | None = None
    automation_id: int | None = None
    bot_id: int | None = None

    execution_mode: str | None = None

    reason: str | None = None
    message: str | None = None

    # Dados livres adicionais (persistidos em worker_runtime_events.extra_json).
    extra: Any = None


class WorkerRuntimeEventResponse(OrkaBaseSchema):
    message: str
    event_id: int
    runner_id: int
