import base64
import binascii
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import (
    ForbiddenException,
    NotFoundException,
    UnauthorizedException,
    ValidationException,
)
from app.core.security import (
    decrypt_credential_value,
    generate_runner_token,
    get_runner_token_hash,
    verify_runner_token,
)
from app.domain.enums import RunnerStatus, TaskStatus
from app.models.automation import Automation
from app.models.automation_runner import AutomationRunner
from app.models.bot_version import BotVersion
from app.models.runner_status_history import RunnerStatusHistory
from app.repositories.bot_repository import BotRepository
from app.repositories.credential_repository import CredentialRepository
from app.repositories.runner_repository import RunnerRepository
from app.repositories.task_error_repository import TaskErrorRepository
from app.repositories.task_log_repository import TaskLogRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.task_telemetry_repository import TaskTelemetryRepository
from app.repositories.worker_runtime_event_repository import WorkerRuntimeEventRepository
from app.schemas.worker import (
    WorkerHeartbeatResponse,
    WorkerRuntimeEventResponse,
    WorkerScreenshotUploadResponse,
    WorkerSyncRequest,
    WorkerSyncResponse,
    WorkerTaskActiveListResponse,
    WorkerTaskErrorResponse,
    WorkerTaskLogResponse,
    WorkerTaskReleaseStartupLocksResponse,
)
from app.services.lock_service import LockService


RUNNER_FINALIZABLE_STATUSES = {
    TaskStatus.FINISHED,
    TaskStatus.ERROR,
    TaskStatus.CANCELED,
    TaskStatus.TIMEOUT,
}

RUNNER_PROGRESS_STATUSES = {
    TaskStatus.READY,
    TaskStatus.RUNNING,
    TaskStatus.STOP_REQUESTED,
}

RUNNER_STARTUP_ACTIVE_STATUSES = {
    TaskStatus.READY,
    TaskStatus.RUNNING,
    TaskStatus.STOP_REQUESTED,
}


class WorkerService:
    def __init__(self, db: Session):
        self.db = db
        self.runner_repository = RunnerRepository(db)
        self.task_repository = TaskRepository(db)
        self.credential_repository = CredentialRepository(db)
        self.task_log_repository = TaskLogRepository(db)
        self.task_error_repository = TaskErrorRepository(db)
        self.task_telemetry_repository = TaskTelemetryRepository(db)
        self.lock_service = LockService(db)
        self.worker_runtime_event_repository = WorkerRuntimeEventRepository(db)

    def _get_last_runner_status_history(self, runner_id: int) -> RunnerStatusHistory | None:
        stmt = (
            select(RunnerStatusHistory)
            .where(RunnerStatusHistory.runner_id == runner_id)
            .order_by(RunnerStatusHistory.created_at.desc(), RunnerStatusHistory.id.desc())
            .limit(1)
        )
        return self.db.execute(stmt).scalars().first()

    def _add_runner_status_history_if_needed(
        self,
        runner_id: int,
        status: RunnerStatus,
        reason: str | None = None,
    ) -> None:
        last_history = self._get_last_runner_status_history(runner_id)

        status_value = status.value if hasattr(status, "value") else str(status)

        if last_history and last_history.status == status_value:
            return

        history = RunnerStatusHistory(
            runner_id=runner_id,
            status=status_value,
            reason=reason,
        )
        self.db.add(history)

    def upload_runner_screenshot(self, payload) -> WorkerScreenshotUploadResponse:
        runner = self._authenticate_runner(payload.uuid, payload.token)

        try:
            image_bytes = base64.b64decode(payload.image_base64, validate=True)
        except (binascii.Error, ValueError):
            raise ValidationException("Imagem inválida. Envie uma imagem em base64 válido.")

        now = datetime.now(UTC)

        runner.last_screenshot_image = image_bytes
        runner.last_screenshot_at = now

        self.db.add(runner)
        self.db.commit()
        self.db.refresh(runner)

        return WorkerScreenshotUploadResponse(
            message="Screenshot do runner atualizado com sucesso.",
            runner_id=runner.id,
            last_screenshot_at=runner.last_screenshot_at,
        )

    def create_runtime_event(self, payload) -> WorkerRuntimeEventResponse:
        runner = self._authenticate_runner(payload.uuid, payload.token)

        event = self.worker_runtime_event_repository.create(
            {
                "runner_id": runner.id,
                "task_id": payload.task_id,
                "automation_id": payload.automation_id,
                "bot_id": payload.bot_id,
                "event_type": payload.event_type,
                "execution_mode": payload.execution_mode,
                "reason": payload.reason,
                "message": payload.message,
                "created_at": datetime.now(UTC),
            }
        )

        self.db.commit()

        return WorkerRuntimeEventResponse(
            message="Evento de runtime registrado com sucesso.",
            event_id=event.id,
            runner_id=runner.id,
        )

    def _authenticate_runner(self, uuid: str, token: str):
        runner = self.runner_repository.get_by_uuid(uuid)
        if not runner:
            raise UnauthorizedException("Runner não encontrado.")

        if not runner.enabled:
            raise ForbiddenException("Runner desativado.")

        if not verify_runner_token(token, runner.token_hash):
            raise UnauthorizedException("Token do runner inválido.")

        return runner

    def _validate_task_runner_ownership(self, task, runner) -> None:
        if not task:
            raise NotFoundException("Task não encontrada.")

        if task.runner_id != runner.id:
            raise ForbiddenException("Esta task não pertence a este runner.")

    def _empty_next_task_response(self) -> dict:
        return {
            "found": False,
            "task_id": None,
            "automation_id": None,
            "bot_id": None,
            "bot_version_id": None,
            "execution_mode": None,
            "priority": None,
            "status": None,
            "correlation_id": None,
            "queue_name": None,
            "requested_start_at": None,
            "timeout_seconds": None,
            "inactivity_timeout_seconds": None,
            "parameters": [],
        }

    def _get_runner_max_concurrency(self, runner) -> int:
        config = self.runner_repository.get_config(runner.id)
        if not config or config.max_concurrency is None:
            return 1
        return max(1, config.max_concurrency)
    
    def _get_mode_max_concurrency(self, runner, execution_mode: str | None) -> int:
        if execution_mode == "foreground":
            return 1

        return self._get_runner_max_concurrency(runner)


    def _count_active_for_runner_by_execution_mode(self, runner_id: int, execution_mode: str | None) -> int:
        tasks = self.task_repository.list_active_for_runner(runner_id)

        total = 0
        for task in tasks:
            _, task_execution_mode = self._resolve_task_bot_context(task)

            if task_execution_mode == execution_mode:
                total += 1

        return total

    def _normalize_execution_mode(self, value) -> str | None:
        if value is None:
            return None

        text = str(value).strip().lower()
        if not text:
            return None

        if text not in {"background", "foreground"}:
            return None

        return text

    def _resolve_task_bot_context(self, task) -> tuple[int | None, str | None]:
        task_bot_id = None
        execution_mode = None

        automation = (
            self.db.query(Automation)
            .filter(Automation.id == task.automation_id)
            .first()
        )

        if task.bot_version_id:
            bot_version = (
                self.db.query(BotVersion)
                .filter(BotVersion.id == task.bot_version_id)
                .first()
            )
            if bot_version:
                task_bot_id = bot_version.bot_id

        if task_bot_id is None and automation:
            task_bot_id = automation.bot_id

        if task_bot_id is not None:
            bot = BotRepository.get_by_id(self.db, task_bot_id)
            if bot:
                raw_execution_mode = getattr(bot, "execution_mode", None)
                execution_mode = (
                    raw_execution_mode.value
                    if hasattr(raw_execution_mode, "value")
                    else raw_execution_mode
                )

        return task_bot_id, self._normalize_execution_mode(execution_mode)

    def _resolve_requested_execution_mode(self, payload) -> str | None:
        raw_mode = getattr(payload, "execution_mode", None)
        return self._normalize_execution_mode(raw_mode)

    def _resolve_task_parameters(self, task) -> list[dict]:
        parameters: list[dict] = []

        for param in task.parameters:
            value = param.parameter_value

            if param.resolved_from_credential_item_id:
                credential_item = self.credential_repository.get_item_by_id(
                    param.resolved_from_credential_item_id
                )

                if credential_item:
                    value = decrypt_credential_value(credential_item.encrypted_value)

            parameters.append(
                {
                    "parameter_name": param.parameter_name,
                    "parameter_value": value,
                    "is_secret": param.is_secret,
                    "resolved_from_credential_item_id": param.resolved_from_credential_item_id,
                }
            )

        return parameters

    def register_runner(self, payload):
        existing_by_uuid = self.runner_repository.get_by_uuid(payload.uuid)
        plain_token = generate_runner_token()
        token_hash = get_runner_token_hash(plain_token)

        if existing_by_uuid:
            runner = self.runner_repository.update(
                existing_by_uuid,
                name=payload.name,
                label=payload.label,
                host_name=payload.host_name,
                ip=payload.ip,
                os_name=payload.os_name,
                os_version=payload.os_version,
                cpu_arch=payload.cpu_arch,
                memory_total=payload.memory_total,
                access_remote=payload.access_remote,
                token_hash=token_hash,
                status=RunnerStatus.OFFLINE,
            )
        else:
            runner = self.runner_repository.create(
                uuid=payload.uuid,
                name=payload.name,
                label=payload.label,
                host_name=payload.host_name,
                ip=payload.ip,
                os_name=payload.os_name,
                os_version=payload.os_version,
                cpu_arch=payload.cpu_arch,
                memory_total=payload.memory_total,
                access_remote=payload.access_remote,
                token_hash=token_hash,
                status=RunnerStatus.OFFLINE,
                enabled=True,
            )

        config = self.runner_repository.get_config(runner.id)
        if not config:
            config = self.runner_repository.create_config(
                runner.id,
                max_concurrency=1,
                polling_interval=10,
            )

        return {
            "runner_id": runner.id,
            "uuid": runner.uuid,
            "name": runner.name,
            "status": runner.status,
            "enabled": runner.enabled,
            "token": plain_token,
            "polling_interval": config.polling_interval,
            "max_concurrency": config.max_concurrency,
        }

    def authenticate(self, payload):
        runner = self._authenticate_runner(payload.uuid, payload.token)
        return {
            "authenticated": True,
            "runner_id": runner.id,
            "uuid": runner.uuid,
            "status": runner.status,
            "enabled": runner.enabled,
        }

    def heartbeat(self, payload) -> WorkerHeartbeatResponse:
        runner = self._authenticate_runner(payload.uuid, payload.token)

        max_concurrency = self._get_runner_max_concurrency(runner)

        if payload.running_tasks >= max_concurrency and max_concurrency > 0:
            new_status = RunnerStatus.BUSY
        else:
            new_status = RunnerStatus.ONLINE

        runner = self.runner_repository.update(
            runner,
            ip=payload.ip or runner.ip,
            last_heartbeat=datetime.now(UTC),
            status=new_status,
        )

        return WorkerHeartbeatResponse(
            ok=True,
            runner_id=runner.id,
            status=runner.status,
            server_time=datetime.now(UTC),
            running_tasks=payload.running_tasks,
        )

    def sync_runner(self, payload: WorkerSyncRequest) -> WorkerSyncResponse:
        runner = self._authenticate_runner(payload.uuid, payload.token)

        update_data = {
            "last_heartbeat": datetime.now(UTC),
            "status": RunnerStatus.ONLINE,
        }

        if payload.host_name is not None:
            update_data["host_name"] = payload.host_name

        if payload.ip is not None:
            update_data["ip"] = payload.ip

        runner = self.runner_repository.update(runner, **update_data)

        self._add_runner_status_history_if_needed(
            runner_id=runner.id,
            status=RunnerStatus.ONLINE,
            reason="sync",
        )
        self.db.commit()

        config = self.runner_repository.get_config(runner.id)
        polling_interval = (
            config.polling_interval
            if config and config.polling_interval is not None
            else 10
        )
        max_concurrency = (
            config.max_concurrency
            if config and config.max_concurrency is not None
            else 1
        )

        automation_links = (
            self.db.query(AutomationRunner)
            .filter(AutomationRunner.runner_id == runner.id)
            .all()
        )

        bot_payloads: list[dict] = []
        added_bot_ids: set[int] = set()

        for link in automation_links:
            automation = (
                self.db.query(Automation)
                .filter(
                    Automation.id == link.automation_id,
                    Automation.active == True,
                )
                .first()
            )

            if not automation:
                continue

            bot = BotRepository.get_by_id(self.db, automation.bot_id)
            if not bot or not bot.active:
                continue

            if bot.id in added_bot_ids:
                continue

            active_version = (
                self.db.query(BotVersion)
                .filter(
                    BotVersion.bot_id == bot.id,
                    BotVersion.is_active == True,
                )
                .order_by(BotVersion.id.desc())
                .first()
            )

            bot_payloads.append(
                {
                    "bot_id": bot.id,
                    "bot_version_id": active_version.id if active_version else None,
                    "name": bot.name,
                    "technology": bot.technology.value if hasattr(bot.technology, "value") else str(bot.technology),
                    "source_type": bot.source_type.value if hasattr(bot.source_type, "value") else str(bot.source_type),
                    "source_url": bot.source_url,
                    "repository_url": bot.source_url,
                    "entrypoint": bot.entrypoint,
                    "requirements_file": bot.requirements_file,
                    "timeout_default": bot.timeout_default,
                    "version": active_version.version if active_version else bot.release_version or bot.current_version,
                    "commit_hash": active_version.commit_hash if active_version else None,
                    "branch": active_version.branch if active_version else None,
                    "storage_type": active_version.storage_type if active_version else None,
                    "artifact_path": active_version.artifact_path if active_version else None,
                    "checksum": active_version.checksum if active_version else None,
                    "execution_mode": self._normalize_execution_mode(
                        getattr(bot, "execution_mode", None).value
                        if hasattr(getattr(bot, "execution_mode", None), "value")
                        else getattr(bot, "execution_mode", None)
                    ),
                }
            )
            added_bot_ids.add(bot.id)

        return WorkerSyncResponse(
            runner_id=runner.id,
            status=runner.status.value if hasattr(runner.status, "value") else str(runner.status),
            enabled=runner.enabled,
            polling_interval=polling_interval,
            max_concurrency=max_concurrency,
            message="sync successful",
            bots=bot_payloads,
        )

    def list_active_tasks(self, payload) -> WorkerTaskActiveListResponse:
        runner = self._authenticate_runner(payload.uuid, payload.token)
        tasks = self.task_repository.list_active_for_runner(runner.id)

        items: list[dict] = []
        for task in tasks:
            items.append(
                {
                    "id": task.id,
                    "automation_id": task.automation_id,
                    "runner_id": task.runner_id,
                    "status": task.status,
                    "lock_key": self.lock_service.build_task_lock_key(task),
                }
            )

        return WorkerTaskActiveListResponse(
            items=items,
            total=len(items),
        )

    def release_startup_locks(self, payload) -> WorkerTaskReleaseStartupLocksResponse:
        runner = self._authenticate_runner(payload.uuid, payload.token)
        tasks = self.task_repository.list_active_for_runner(runner.id)

        tasks_finalized = 0
        task_locks_released = 0

        now = datetime.now(UTC)

        for task in tasks:
            if task.status not in RUNNER_STARTUP_ACTIVE_STATUSES:
                continue

            final_message = (
                "Task finalizada automaticamente na inicialização do worker, "
                "pois havia sido deixada em execução sem processo local ativo."
            )

            self.task_repository.update(
                task,
                {
                    "status": TaskStatus.CANCELED,
                    "finished_at": now,
                    "last_update_at": now,
                    "final_message": final_message,
                    "stop_requested": False,
                },
            )
            tasks_finalized += 1

            released = self.lock_service.release_task_locks(task.id)
            task_locks_released += len(released)

        runner_locks_released = len(self.lock_service.release_runner_locks(runner.id))

        self.db.commit()

        return WorkerTaskReleaseStartupLocksResponse(
            message="Recuperação inicial do worker concluída com sucesso.",
            runner_id=runner.id,
            tasks_finalized=tasks_finalized,
            task_locks_released=task_locks_released,
            runner_locks_released=runner_locks_released,
        )

    def get_next_task(self, payload):
        runner = self._authenticate_runner(payload.uuid, payload.token)

        if runner.status not in {RunnerStatus.ONLINE, RunnerStatus.BUSY}:
            raise ForbiddenException("Runner precisa estar ONLINE para consultar tasks.")

        requested_execution_mode = self._resolve_requested_execution_mode(payload)

        active_count = self._count_active_for_runner_by_execution_mode(
            runner.id,
            requested_execution_mode,
        )
        max_concurrency = self._get_mode_max_concurrency(
            runner,
            requested_execution_mode,
        )

        if active_count >= max_concurrency:
            return self._empty_next_task_response()
        candidates = self.task_repository.list_waiting_candidates_for_runner(runner.id)

        selected_task = None
        selected_task_bot_id = None
        selected_execution_mode = None

        for candidate in candidates:
            if not self.task_repository.automation_has_runner_link(
                candidate.automation_id,
                runner.id,
            ):
                continue

            candidate_bot_id, candidate_execution_mode = self._resolve_task_bot_context(candidate)

            if requested_execution_mode is not None and candidate_execution_mode != requested_execution_mode:
                continue

            selected_task = candidate
            selected_task_bot_id = candidate_bot_id
            selected_execution_mode = candidate_execution_mode
            break

        if not selected_task:
            return self._empty_next_task_response()

        parameters = self._resolve_task_parameters(selected_task)

        return {
            "found": True,
            "task_id": selected_task.id,
            "automation_id": selected_task.automation_id,
            "bot_id": selected_task_bot_id,
            "bot_version_id": selected_task.bot_version_id,
            "execution_mode": selected_execution_mode,
            "priority": selected_task.priority,
            "status": selected_task.status,
            "correlation_id": selected_task.correlation_id,
            "queue_name": selected_task.queue_name,
            "requested_start_at": selected_task.requested_start_at,
            "timeout_seconds": selected_task.timeout_seconds,
            "inactivity_timeout_seconds": selected_task.inactivity_timeout_seconds,
            "parameters": parameters,
        }

    def claim_task(self, task_id: int, payload):
        runner = self._authenticate_runner(payload.uuid, payload.token)
        task = self.task_repository.get_by_id(task_id)

        if not task:
            raise NotFoundException("Task não encontrada.")

        if runner.status not in {RunnerStatus.ONLINE, RunnerStatus.BUSY}:
            raise ForbiddenException("Runner precisa estar ONLINE para assumir tasks.")

        _, task_execution_mode = self._resolve_task_bot_context(task)

        active_count = self._count_active_for_runner_by_execution_mode(
            runner.id,
            task_execution_mode,
        )
        max_concurrency = self._get_mode_max_concurrency(
            runner,
            task_execution_mode,
        )

        if active_count >= max_concurrency:
            raise ValidationException(
                f"Runner atingiu o limite de concorrência para execution_mode={task_execution_mode}."
            )

        if task.status != TaskStatus.WAITING:
            raise ValidationException("Somente tasks em WAITING podem ser assumidas pelo runner.")

        if task.runner_id is not None and task.runner_id != runner.id:
            raise ValidationException("A task já está vinculada a outro runner.")

        if not self.task_repository.automation_has_runner_link(task.automation_id, runner.id):
            raise ForbiddenException("Esta automação não está vinculada a este runner.")

        self.lock_service.acquire_for_task(task, runner_id=runner.id)

        now = datetime.now(UTC)

        task = self.task_repository.update(
            task,
            {
                "runner_id": runner.id,
                "status": TaskStatus.READY,
                "runner_claimed_at": now,
                "last_update_at": now,
                "dispatch_attempts": (task.dispatch_attempts or 0) + 1,
            },
        )

        self.db.commit()

        return {
            "task_id": task.id,
            "runner_id": runner.id,
            "status": task.status,
        }

    def update_task_status(self, task_id: int, payload):
        runner = self._authenticate_runner(payload.uuid, payload.token)
        task = self.task_repository.get_by_id(task_id)

        self._validate_task_runner_ownership(task, runner)

        if (
            payload.status not in RUNNER_PROGRESS_STATUSES
            and payload.status not in RUNNER_FINALIZABLE_STATUSES
        ):
            raise ValidationException(
                "Status informado não é permitido para atualização pelo runner."
            )

        update_data = {
            "status": payload.status,
            "items_processed": (
                payload.items_processed
                if payload.items_processed is not None
                else task.items_processed
            ),
            "items_failed": (
                payload.items_failed
                if payload.items_failed is not None
                else task.items_failed
            ),
            "final_message": (
                payload.final_message
                if payload.final_message is not None
                else task.final_message
            ),
            "last_update_at": datetime.now(UTC),
        }

        if payload.status == TaskStatus.RUNNING and task.started_at is None:
            update_data["started_at"] = datetime.now(UTC)

        if payload.status in RUNNER_FINALIZABLE_STATUSES:
            update_data["finished_at"] = datetime.now(UTC)

        task = self.task_repository.update(task, update_data)
        self.db.commit()
        return task

    def finish_task(self, task_id: int, payload):
        runner = self._authenticate_runner(payload.uuid, payload.token)
        task = self.task_repository.get_by_id(task_id)

        self._validate_task_runner_ownership(task, runner)

        if payload.status not in RUNNER_FINALIZABLE_STATUSES:
            raise ValidationException("Finalização exige status final válido.")

        started_at = task.started_at or datetime.now(UTC)

        task = self.task_repository.update(
            task,
            {
                "status": payload.status,
                "started_at": started_at,
                "finished_at": datetime.now(UTC),
                "last_update_at": datetime.now(UTC),
                "final_message": payload.final_message,
                "items_processed": payload.items_processed,
                "items_failed": payload.items_failed,
            },
        )

        self.lock_service.release_task_locks(task.id)

        self.db.commit()
        return task

    def create_task_log(self, task_id: int, payload) -> WorkerTaskLogResponse:
        runner = self._authenticate_runner(payload.uuid, payload.token)
        task = self.task_repository.get_by_id(task_id)

        self._validate_task_runner_ownership(task, runner)

        self.task_log_repository.create(
            {
                "task_id": task.id,
                "level": payload.level,
                "message": payload.message,
                "source": payload.source,
                "reference": payload.reference,
                "error_type": payload.error_type,
                "sequence_number": payload.sequence_number,
                "event_code": payload.event_code,
            }
        )

        self.db.commit()

        return WorkerTaskLogResponse(
            message="Log registrado com sucesso.",
            task_id=task.id,
        )

    def create_task_error(self, task_id: int, payload) -> WorkerTaskErrorResponse:
        runner = self._authenticate_runner(payload.uuid, payload.token)
        task = self.task_repository.get_by_id(task_id)

        self._validate_task_runner_ownership(task, runner)

        self.task_error_repository.create(
            {
                "task_id": task.id,
                "error_type": payload.error_type,
                "message": payload.message,
                "stacktrace": payload.stacktrace,
                "error_category": payload.error_category,
                "is_retryable": payload.is_retryable,
                "source": payload.source,
                "code": payload.code,
            }
        )

        self.db.commit()

        return WorkerTaskErrorResponse(
            message="Erro registrado com sucesso.",
            task_id=task.id,
        )

    def resolve_credential_for_runner(self, credential_id: int, payload):
        self._authenticate_runner(payload.uuid, payload.token)

        credential = self.credential_repository.get_by_id(credential_id)
        if not credential:
            raise NotFoundException("Credencial não encontrada.")

        if not credential.active:
            raise ValidationException("Credencial está inativa.")

        requested_keys = None
        if payload.keys:
            requested_keys = {str(key) for key in payload.keys if key is not None}

        resolved_items: dict[str, str | None] = {}

        for item in credential.items:
            key_name = item.key_name

            if requested_keys is not None and key_name not in requested_keys:
                continue

            resolved_items[key_name] = decrypt_credential_value(item.encrypted_value)

        return {
            "dados_acesso": resolved_items,
        }

    def create_task_telemetry(self, task_id: int, payload):
        runner = self._authenticate_runner(payload.uuid, payload.token)
        task = self.task_repository.get_by_id(task_id)

        self._validate_task_runner_ownership(task, runner)

        existing = self.task_telemetry_repository.get_by_task_id(task.id)

        data = {
            "task_id": task.id,
            "runner_id": runner.id,
            "captured_at": payload.captured_at,
            "execution_started_at": payload.execution_started_at,
            "execution_finished_at": payload.execution_finished_at,
            "duration_seconds": payload.duration_seconds,
            "cpu_percent_avg": payload.cpu_percent_avg,
            "cpu_percent_peak": payload.cpu_percent_peak,
            "memory_used_mb_avg": payload.memory_used_mb_avg,
            "memory_used_mb_peak": payload.memory_used_mb_peak,
            "process_memory_mb_peak": payload.process_memory_mb_peak,
            "disk_read_mb": payload.disk_read_mb,
            "disk_write_mb": payload.disk_write_mb,
            "net_sent_mb": payload.net_sent_mb,
            "net_recv_mb": payload.net_recv_mb,
            "exit_code": payload.exit_code,
            "telemetry_status": payload.telemetry_status,
            "message": payload.message,
            "payload_json": payload.payload_json,
            "created_at": datetime.now(UTC),
        }

        if existing:
            self.task_telemetry_repository.update(existing, data)
        else:
            self.task_telemetry_repository.create(data)

        task.last_update_at = datetime.now(UTC)
        self.db.add(task)

        self.db.commit()

        return {
            "message": "Telemetria registrada com sucesso.",
            "task_id": task.id,
        }
    
    