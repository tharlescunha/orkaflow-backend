from datetime import UTC, datetime

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
from app.repositories.credential_repository import CredentialRepository
from app.repositories.runner_repository import RunnerRepository
from app.repositories.task_error_repository import TaskErrorRepository
from app.repositories.task_log_repository import TaskLogRepository
from app.repositories.task_repository import TaskRepository
from app.schemas.worker import (
    WorkerHeartbeatResponse,
    WorkerSyncRequest,
    WorkerSyncResponse,
    WorkerTaskErrorResponse,
    WorkerTaskLogResponse,
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


class WorkerService:
    def __init__(self, db: Session):
        self.db = db
        self.runner_repository = RunnerRepository(db)
        self.task_repository = TaskRepository(db)
        self.credential_repository = CredentialRepository(db)
        self.task_log_repository = TaskLogRepository(db)
        self.task_error_repository = TaskErrorRepository(db)
        self.lock_service = LockService(db)

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
            "bot_version_id": None,
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

    def _resolve_task_parameters(self, task) -> list[dict]:
        parameters: list[dict] = []

        for param in task.parameters:
            value = param.parameter_value

            if param.resolved_from_credential_item_id:
                credential_item = self.credential_repository.get_item_by_id(
                    param.resolved_from_credential_item_id
                )

                if credential_item and credential_item.active:
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

        # Ajusta status considerando carga enviada pelo worker
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

        return WorkerSyncResponse(
            runner_id=runner.id,
            status=runner.status.value if hasattr(runner.status, "value") else str(runner.status),
            enabled=runner.enabled,
            polling_interval=polling_interval,
            max_concurrency=max_concurrency,
            message="sync successful",
        )

    def get_next_task(self, payload):
        runner = self._authenticate_runner(payload.uuid, payload.token)

        if runner.status not in {RunnerStatus.ONLINE, RunnerStatus.BUSY}:
            raise ForbiddenException("Runner precisa estar ONLINE para consultar tasks.")

        active_count = self.task_repository.count_active_for_runner(runner.id)
        max_concurrency = self._get_runner_max_concurrency(runner)

        if active_count >= max_concurrency:
            return self._empty_next_task_response()

        candidates = self.task_repository.list_waiting_candidates_for_runner(runner.id)

        task = None
        for candidate in candidates:
            if not self.task_repository.automation_has_runner_link(
                candidate.automation_id,
                runner.id,
            ):
                continue
            task = candidate
            break

        if not task:
            return self._empty_next_task_response()

        parameters = self._resolve_task_parameters(task)

        return {
            "found": True,
            "task_id": task.id,
            "automation_id": task.automation_id,
            "bot_version_id": task.bot_version_id,
            "priority": task.priority,
            "status": task.status,
            "correlation_id": task.correlation_id,
            "queue_name": task.queue_name,
            "requested_start_at": task.requested_start_at,
            "timeout_seconds": task.timeout_seconds,
            "inactivity_timeout_seconds": task.inactivity_timeout_seconds,
            "parameters": parameters,
        }

    def claim_task(self, task_id: int, payload):
        runner = self._authenticate_runner(payload.uuid, payload.token)
        task = self.task_repository.get_by_id(task_id)

        if not task:
            raise NotFoundException("Task não encontrada.")

        if runner.status not in {RunnerStatus.ONLINE, RunnerStatus.BUSY}:
            raise ForbiddenException("Runner precisa estar ONLINE para assumir tasks.")

        active_count = self.task_repository.count_active_for_runner(runner.id)
        max_concurrency = self._get_runner_max_concurrency(runner)

        if active_count >= max_concurrency:
            raise ValidationException("Runner atingiu o limite de concorrência.")

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

        self.task_log_repository.create({
            "task_id": task.id,
            "level": payload.level,
            "message": payload.message,
            "source": payload.source,
            "reference": payload.reference,
            "error_type": payload.error_type,
            "sequence_number": payload.sequence_number,
            "event_code": payload.event_code,
        })

        self.db.commit()

        return WorkerTaskLogResponse(
            message="Log registrado com sucesso.",
            task_id=task.id,
        )

    def create_task_error(self, task_id: int, payload) -> WorkerTaskErrorResponse:
        runner = self._authenticate_runner(payload.uuid, payload.token)
        task = self.task_repository.get_by_id(task_id)

        self._validate_task_runner_ownership(task, runner)

        self.task_error_repository.create({
            "task_id": task.id,
            "error_type": payload.error_type,
            "message": payload.message,
            "stacktrace": payload.stacktrace,
            "error_category": payload.error_category,
            "is_retryable": payload.is_retryable,
            "source": payload.source,
            "code": payload.code,
        })

        self.db.commit()

        return WorkerTaskErrorResponse(
            message="Erro registrado com sucesso.",
            task_id=task.id,
        )
    