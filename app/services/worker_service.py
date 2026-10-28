import base64
import binascii
import json
import logging
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.exceptions import (
    ForbiddenException,
    NotFoundException,
    UnauthorizedException,
    ValidationException,
)
from app.services import event_service, retry_service
from app.services.credential_health_service import CredentialHealthService
from app.services.git_environment_service import GitEnvironmentService
from app.services.task_events import add_task_log
from app.core.security import (
    decrypt_credential_value,
    generate_runner_token,
    get_runner_token_hash,
    verify_runner_token,
)
from app.domain.enums import ErrorCategory, RunnerStatus, TaskLogLevel, TaskLogSource, TaskStatus
from app.models.automation import Automation
from app.models.automation_runner import AutomationRunner
from app.models.bot import Bot
from app.models.bot_version import BotVersion
from app.models.runner import Runner
from app.models.task import Task
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
from app.services.automation_trigger_service import AutomationTriggerService
from app.services.capacity_service import (
    CapacityService,
    normalize_host,
    runner_max_concurrency,
)
from app.services.lock_service import LockService
from app.services.queue_reasons import describe_wait_reason, set_waiting_reason
from app.services.task_events import add_task_error, add_task_log
from app.services.task_rules import (
    runner_in_maintenance,
    EXECUTING_STATUSES,
    FINAL_STATUSES,
    MODE_BACKGROUND,
    MODE_FOREGROUND,
    normalize_mode,
)

logger = logging.getLogger(__name__)

# Status que o runner pode informar como finalização.
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

RUNNER_STARTUP_ACTIVE_STATUSES = set(EXECUTING_STATUSES)

DEFAULT_ERROR_MESSAGE = "Task finalizada com erro (o worker não informou detalhes)."


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
        self.capacity = CapacityService(db)
        self.automation_trigger_service = AutomationTriggerService(db)
        self.worker_runtime_event_repository = WorkerRuntimeEventRepository(db)

    # ------------------------------------------------------------------
    # helpers de runner / task
    # ------------------------------------------------------------------
    def _set_runner_status(self, runner, status: RunnerStatus, reason: str | None = None):
        self.capacity.set_runner_status(runner, status, reason)
        return runner

    def _refresh_runner_status(self, runner, reason: str = "status_derivado_das_tasks"):
        """BUSY/ONLINE derivam das tasks abertas no banco, nunca do que o worker informa."""
        return self.capacity.refresh_runner_status(runner, reason)

    def _mark_alive(self, runner, reason: str = "worker_ativo") -> None:
        """Qualquer chamada autenticada válida prova que o worker está vivo.

        Atualiza last_heartbeat e, se o watchdog tinha deixado o runner OFFLINE
        (heartbeat atrasado, sync/instalação), volta para ONLINE.
        """
        runner.last_heartbeat = datetime.now(UTC)
        self.db.add(runner)
        # BLOCKED não existe mais como decisão do sistema (só sobrou em dados antigos
        # de paradas forçadas de versões anteriores): o worker vivo volta a ficar ONLINE.
        if runner.enabled and runner.status in (RunnerStatus.OFFLINE, RunnerStatus.BLOCKED):
            self._set_runner_status(runner, RunnerStatus.ONLINE, reason)

    def _touch_task(self, task, *, renew_lock: bool = True) -> None:
        """Atividade real da task: atualiza last_update_at e renova o lock se estiver aberta."""
        if task.status in FINAL_STATUSES:
            return
        task.last_update_at = datetime.now(UTC)
        self.db.add(task)
        if renew_lock and task.status in EXECUTING_STATUSES:
            self.lock_service.renew_task_locks(task)

    def _runner_has_executing_task(self, runner_id: int) -> bool:
        return self.capacity.runner_has_executing_tasks(runner_id)

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
        """Persiste evento do worker. task_id/automation_id/bot_id são opcionais.

        Eventos sem task (sync_failed, bot_auto_update_failed, credential_resolve_failed,
        bot_install_failed...) são aceitos. Referências inexistentes não derrubam o evento:
        viram NULL e o valor original vai para extra_json.
        """
        runner = self._authenticate_runner(payload.uuid, payload.token)
        self._mark_alive(runner)

        extra: dict = {}
        raw_extra = getattr(payload, "extra", None)
        if raw_extra is not None:
            extra["extra"] = raw_extra

        task_id = payload.task_id
        if task_id is not None and self.db.get(Task, task_id) is None:
            extra["task_id_inexistente"] = task_id
            task_id = None

        automation_id = payload.automation_id
        if automation_id is not None and self.db.get(Automation, automation_id) is None:
            extra["automation_id_inexistente"] = automation_id
            automation_id = None

        bot_id = payload.bot_id
        if bot_id is not None and self.db.get(Bot, bot_id) is None:
            extra["bot_id_inexistente"] = bot_id
            bot_id = None

        raw_mode = self._normalize_execution_mode(payload.execution_mode)
        if payload.execution_mode and raw_mode is None:
            extra["execution_mode_original"] = payload.execution_mode

        event_type = (payload.event_type or "unknown").strip()[:100] or "unknown"
        reason = payload.reason[:100] if payload.reason else None

        event = self.worker_runtime_event_repository.create(
            {
                "runner_id": runner.id,
                "task_id": task_id,
                "automation_id": automation_id,
                "bot_id": bot_id,
                "event_type": event_type,
                "execution_mode": raw_mode,
                "reason": reason,
                "message": payload.message,
                "extra_json": json.dumps(extra, ensure_ascii=False, default=str) if extra else None,
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

        if runner.deleted_at is not None:
            raise ForbiddenException(
                "Runner removido do painel: esta máquina não está configurada. "
                "Rode o configurar_worker.bat para registrá-la de novo."
            )

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

    def _find_runner_for_registration(self, payload) -> Runner | None:
        """Procura por uuid; senão por nome (case-insensitive, preferindo o mesmo host)."""
        runner = self.runner_repository.get_by_uuid(payload.uuid)
        if runner:
            return runner

        name = (payload.name or "").strip().lower()
        if not name:
            return None

        rows = list(
            self.db.execute(select(Runner).where(func.lower(Runner.name) == name)).scalars().all()
        )
        if not rows:
            return None

        host = normalize_host(payload.host_name)
        if host is not None:
            for row in rows:
                if normalize_host(row.host_name) == host:
                    return row
        return rows[0]

    def register_runner(self, payload):
        """Upsert: reinstalar/editar o worker não exige apagar o runner.

        Procura por uuid, depois por nome. Se achou, atualiza (host, ip, os, label,
        uuid novo, token rotacionado, reativa); senão cria.
        """
        existing = self._find_runner_for_registration(payload)
        plain_token = generate_runner_token()
        token_hash = get_runner_token_hash(plain_token)

        if existing:
            update_data = dict(
                label=payload.label,
                host_name=payload.host_name,
                ip=payload.ip,
                os_name=payload.os_name,
                os_version=payload.os_version,
                cpu_arch=payload.cpu_arch,
                memory_total=payload.memory_total,
                access_remote=payload.access_remote,
                token_hash=token_hash,
                enabled=True,
            )

            if existing.uuid != payload.uuid:
                update_data["uuid"] = payload.uuid

            # Nome: só troca se não colidir com outro runner.
            new_name = (payload.name or "").strip()
            if new_name and new_name != existing.name:
                clash = self.db.execute(
                    select(Runner.id)
                    .where(func.lower(Runner.name) == new_name.lower())
                    .where(Runner.id != existing.id)
                ).first()
                if not clash:
                    update_data["name"] = new_name

            # Manutenção é decisão do administrador: preserva. Demais voltam OFFLINE
            # até o primeiro sync/heartbeat.
            if existing.status != RunnerStatus.MAINTENANCE:
                update_data["status"] = RunnerStatus.OFFLINE

            # Registrar de novo uma máquina removida a traz de volta (update() ignora None).
            if existing.deleted_at is not None:
                existing.deleted_at = None
                logger.info("Runner %s (id=%s) estava removido e voltou pelo registro.", existing.name, existing.id)

            runner = self.runner_repository.update(existing, **update_data)
            logger.info("Runner %s (id=%s) re-registrado (upsert).", runner.name, runner.id)
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
            "max_concurrency": runner_max_concurrency(runner),
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
        """running_tasks do worker é só informativo; BUSY/ONLINE deriva das tasks do banco."""
        runner = self._authenticate_runner(payload.uuid, payload.token)

        if payload.ip:
            runner.ip = payload.ip
        os_user = (getattr(payload, "os_user", None) or "").strip()[:150]
        if os_user and runner.os_user != os_user:
            runner.os_user = os_user
        self._mark_alive(runner, reason="heartbeat")
        self._refresh_runner_status(runner, reason="heartbeat")

        # Heartbeat renova o lock das tasks abertas do runner (não conta como atividade da task).
        for task in self.task_repository.list_active_for_runner(runner.id):
            self.lock_service.renew_task_locks(task)

        self.db.commit()
        self.db.refresh(runner)

        return WorkerHeartbeatResponse(
            ok=True,
            runner_id=runner.id,
            status=runner.status,
            server_time=datetime.now(UTC),
            running_tasks=payload.running_tasks,
        )

    def sync_runner(self, payload: WorkerSyncRequest) -> WorkerSyncResponse:
        runner = self._authenticate_runner(payload.uuid, payload.token)

        if payload.host_name is not None:
            runner.host_name = payload.host_name
        if payload.ip is not None:
            runner.ip = payload.ip

        self._mark_alive(runner, reason="sync")
        self._refresh_runner_status(runner, reason="sync")
        self.db.commit()
        self.db.refresh(runner)

        config = self.runner_repository.get_config(runner.id)
        polling_interval = (
            config.polling_interval
            if config and config.polling_interval is not None
            else 10
        )

        automation_links = (
            self.db.query(AutomationRunner)
            .filter(AutomationRunner.runner_id == runner.id)
            .all()
        )

        bot_payloads: list[dict] = []
        git_environments = GitEnvironmentService(self.db)
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

            # Mesma regra de versão usada na criação das tasks (ativa; fallback última).
            active_version = self.task_repository.get_latest_bot_version_for_bot(bot.id)
            # Link limpo ganha o token do ambiente de Git (Configurações); link com token fica como está.
            clone_url = git_environments.resolve_url(bot.source_url)

            bot_payloads.append(
                {
                    "bot_id": bot.id,
                    "bot_version_id": active_version.id if active_version else None,
                    "name": bot.name,
                    "technology": bot.technology.value if hasattr(bot.technology, "value") else str(bot.technology),
                    "source_type": bot.source_type.value if hasattr(bot.source_type, "value") else str(bot.source_type),
                    "source_url": clone_url,
                    "repository_url": clone_url,
                    "entrypoint": bot.entrypoint,
                    "requirements_file": bot.requirements_file,
                    "timeout_default": bot.timeout_default,
                    "version": active_version.version if active_version else bot.release_version or bot.current_version,
                    "commit_hash": active_version.commit_hash if active_version else None,
                    "branch": active_version.branch if active_version else None,
                    "storage_type": active_version.storage_type if active_version else None,
                    "artifact_path": active_version.artifact_path if active_version else None,
                    "checksum": active_version.checksum if active_version else None,
                    "execution_mode": normalize_mode(bot.execution_mode),
                    # Flag do próprio bot (coluna bots.auto_update, junho/2026).
                    # Com versão fixada por Release o worker NÃO pode puxar a branch: ele faz
                    # checkout do commit da versão (comportamento atual sem auto_update).
                    "auto_update": bool(getattr(bot, "auto_update", False))
                    and getattr(bot, "pinned_version_id", None) is None,
                    # Robô antigo recebe o caminho do JSON por argumento; robô com maestro não precisa.
                    "reads_task_file_arg": bool(getattr(bot, "reads_task_file_arg", True)),
                }
            )
            added_bot_ids.add(bot.id)

        return WorkerSyncResponse(
            runner_id=runner.id,
            status=runner.status.value if hasattr(runner.status, "value") else str(runner.status),
            enabled=runner.enabled,
            polling_interval=polling_interval,
            max_concurrency=runner_max_concurrency(runner),
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
        """Worker reiniciou: o que estava em execução não existe mais no processo local.

        As tasks READY/RUNNING/STOP_REQUESTED do runner viram ERROR (com TaskError e
        TaskLog), os locks são liberados e o runner NÃO é bloqueado.
        """
        runner = self._authenticate_runner(payload.uuid, payload.token)
        self._mark_alive(runner, reason="startup")
        tasks = self.task_repository.list_active_for_runner(runner.id)

        tasks_finalized = 0
        task_locks_released = 0

        now = datetime.now(UTC)
        message = "Task interrompida: worker foi reiniciado"

        for task in tasks:
            if task.status not in RUNNER_STARTUP_ACTIVE_STATUSES:
                continue

            previous_status = task.status.value if hasattr(task.status, "value") else str(task.status)

            self.task_repository.update(
                task,
                {
                    "status": TaskStatus.ERROR,
                    "finished_at": now,
                    "last_update_at": now,
                    "final_message": message,
                },
            )
            add_task_error(
                self.db,
                task.id,
                "WorkerRestarted",
                message,
                category=ErrorCategory.TECHNICAL,
                source=TaskLogSource.SYSTEM,
                code="WORKER_RESTARTED",
                is_retryable=True,
            )
            add_task_log(
                self.db,
                task.id,
                f"{message} (status anterior: {previous_status}). Task marcada como ERROR.",
                level=TaskLogLevel.ERROR,
                source=TaskLogSource.SYSTEM,
                event_code="WORKER_RESTARTED",
                runner_id=runner.id,
            )
            tasks_finalized += 1
            retry_service.schedule_retry_if_applicable(self.db, task)

            released = self.lock_service.release_task_locks(task.id)
            task_locks_released += len(released)

        runner_locks_released = len(self.lock_service.release_runner_locks(runner.id))

        self._refresh_runner_status(runner, reason="startup_recuperacao")
        self.db.commit()

        return WorkerTaskReleaseStartupLocksResponse(
            message="Recuperação inicial do worker concluída com sucesso.",
            runner_id=runner.id,
            tasks_finalized=tasks_finalized,
            task_locks_released=task_locks_released,
            runner_locks_released=runner_locks_released,
        )

    def get_next_task(self, payload):
        """Devolve o primeiro candidato realmente claimável do modo pedido, se houver capacidade."""
        runner = self._authenticate_runner(payload.uuid, payload.token)

        if not runner.enabled:
            return self._empty_next_task_response()

        self._mark_alive(runner, reason="next_task")
        self._refresh_runner_status(runner, reason="next_task")
        self.db.commit()

        if runner.status in (RunnerStatus.MAINTENANCE, RunnerStatus.OFFLINE) or runner_in_maintenance(runner):
            return self._empty_next_task_response()

        requested = self._resolve_requested_execution_mode(payload)
        modes = [requested] if requested else [MODE_BACKGROUND, MODE_FOREGROUND]

        for mode in modes:
            # WAITING pré-vinculada não consome capacidade; só READY/RUNNING/STOP_REQUESTED.
            if not self.capacity.has_capacity(runner, mode):
                continue

            rows = self.task_repository.list_claim_candidates(runner.id, mode)
            for candidate, bot_id, raw_mode in rows:
                if self.lock_service.is_key_locked(self.lock_service.build_task_lock_key(candidate)):
                    # Automação já em execução: não é claimável agora, tenta o próximo.
                    continue

                # Out/2026: as mesmas regras que o claim aplicaria (automação ocupada, grupo
                # exclusivo). Pular aqui evita a task da frente travar a fila inteira, e o
                # motivo fica registrado na task.
                reason = describe_wait_reason(self.task_repository, candidate)
                if reason is not None:
                    set_waiting_reason(self.db, candidate, reason, source=TaskLogSource.DISPATCHER)
                    self.db.commit()
                    continue

                return {
                    "found": True,
                    "task_id": candidate.id,
                    "automation_id": candidate.automation_id,
                    "bot_id": bot_id,
                    "bot_version_id": candidate.bot_version_id,
                    "execution_mode": normalize_mode(raw_mode),
                    "priority": candidate.priority,
                    "status": candidate.status,
                    "correlation_id": candidate.correlation_id,
                    "queue_name": candidate.queue_name,
                    "requested_start_at": candidate.requested_start_at,
                    "timeout_seconds": candidate.timeout_seconds,
                    "inactivity_timeout_seconds": candidate.inactivity_timeout_seconds,
                    "parameters": self._resolve_task_parameters(candidate),
                }

        return self._empty_next_task_response()

    def claim_task(self, task_id: int, payload):
        """Claim atômico: UPDATE condicional (WAITING e sem outro runner) + checagem de rowcount."""
        runner = self._authenticate_runner(payload.uuid, payload.token)
        task = self.db.get(Task, task_id)

        if not task:
            raise NotFoundException("Task não encontrada.")

        # Chamada autenticada válida = worker vivo. Persiste antes de qualquer validação.
        self._mark_alive(runner, reason="claim_task")
        self.db.commit()

        if runner.status == RunnerStatus.MAINTENANCE or runner_in_maintenance(runner):
            raise ValidationException(
                "Runner em manutenção (definido pelo administrador): não pode assumir novas tasks."
            )

        # Serializa os claims do mesmo runner (lock de linha até o commit),
        # para a checagem de capacidade abaixo não correr em paralelo.
        self.db.execute(
            update(Runner)
            .where(Runner.id == runner.id)
            .values(last_heartbeat=datetime.now(UTC))
            .execution_options(synchronize_session=False)
        )

        self.db.refresh(task)

        # Retry idempotente do mesmo runner (ex.: resposta perdida na rede).
        if task.runner_id == runner.id and task.status in EXECUTING_STATUSES:
            self.db.commit()
            return {"task_id": task.id, "runner_id": runner.id, "status": task.status}

        if task.status != TaskStatus.WAITING:
            self.db.rollback()
            raise ValidationException("Somente tasks em WAITING podem ser assumidas pelo runner.")

        if task.runner_id is not None and task.runner_id != runner.id:
            self.db.rollback()
            raise ValidationException("A task já está vinculada a outro runner.")

        if not self.task_repository.automation_has_runner_link(task.automation_id, runner.id):
            self.db.rollback()
            raise ForbiddenException("Esta automação não está vinculada a este runner.")

        # Regras de junho/2026 preservadas: uma task aberta por automação e exclusão
        # mútua por grupo exclusivo. (A regra "1 task aberta por runner" foi substituída
        # pela capacidade por modo: N BACKGROUND + 1 FOREGROUND por host.)
        if self.task_repository.get_open_task_for_automation(
            task.automation_id,
            exclude_task_id=task.id,
        ):
            self.db.rollback()
            raise ValidationException("Automacao ja possui outra task aberta.")

        if self.task_repository.get_reserved_task_for_exclusive_groups(
            task.automation_id,
            exclude_task_id=task.id,
        ):
            self.db.rollback()
            raise ValidationException(
                "Grupo exclusivo ja possui outra task reservada ou em execucao."
            )

        _, bot_mode = self._resolve_task_bot_context(task)
        mode = bot_mode or MODE_BACKGROUND

        if not self.capacity.has_capacity(runner, mode, exclude_task_id=task.id):
            self.db.rollback()
            if mode == MODE_FOREGROUND:
                raise ValidationException(
                    "Já existe uma task FOREGROUND em execução neste host."
                )
            raise ValidationException(
                f"Runner atingiu o limite de {self.capacity.capacity_limit(runner, mode)} "
                "task(s) BACKGROUND simultâneas."
            )

        try:
            self.lock_service.acquire_for_task(task, runner_id=runner.id)
            if mode == MODE_FOREGROUND:
                self.lock_service.acquire_foreground_for_task(task, runner)
        except ValidationException:
            self.db.rollback()
            raise

        now = datetime.now(UTC)
        result = self.db.execute(
            update(Task)
            .where(Task.id == task.id)
            .where(Task.status == TaskStatus.WAITING)
            .where((Task.runner_id.is_(None)) | (Task.runner_id == runner.id))
            .values(
                status=TaskStatus.READY,
                runner_id=runner.id,
                runner_claimed_at=now,
                last_update_at=now,
                waiting_reason=None,
                dispatch_attempts=func.coalesce(Task.dispatch_attempts, 0) + 1,
            )
            .execution_options(synchronize_session=False)
        )

        if result.rowcount != 1:
            # Outro claim ganhou: desfaz locks criados nesta transação.
            self.db.rollback()
            raise ValidationException("A task já foi assumida por outro runner.")

        self.db.refresh(task)
        self._refresh_runner_status(runner, reason="task_claimed")
        self.db.commit()

        return {
            "task_id": task.id,
            "runner_id": runner.id,
            "status": task.status,
        }

    def resolve_task_env(self, task_id: int, payload):
        """Variáveis de ambiente da task (global < bot < automação < máquina) para o worker."""
        from app.services import env_variable_service

        runner = self._authenticate_runner(payload.uuid, payload.token)
        task = self.task_repository.get_by_id(task_id)

        self._validate_task_runner_ownership(task, runner)

        self._mark_alive(runner, reason="task_env")
        self.db.commit()

        return env_variable_service.resolve_for_task(self.db, task)

    def check_task_status(self, task_id: int, payload):
        runner = self._authenticate_runner(payload.uuid, payload.token)
        task = self.task_repository.get_by_id(task_id)

        self._validate_task_runner_ownership(task, runner)

        self._mark_alive(runner, reason="task_status")
        self.db.commit()

        stop_requested = bool(getattr(task, "stop_requested", False))

        if task.status == TaskStatus.STOP_REQUESTED:
            stop_requested = True

        # Task finalizada pelo backend (timeout, cancelamento, parada forçada...):
        # só na resposta, o worker deve encerrar o processo local.
        if task.status in FINAL_STATUSES and task.status != TaskStatus.FINISHED:
            stop_requested = True

        return {
            "task_id": task.id,
            "status": task.status,
            "stop_requested": stop_requested,
            "runner_id": task.runner_id,
            "exists": True,
        }

    def _ignore_transition(self, runner, task, requested: TaskStatus):
        """Task já finalizada: ignora a mudança, registra TaskLog e responde 200."""
        requested_value = requested.value if hasattr(requested, "value") else str(requested)
        current_value = task.status.value if hasattr(task.status, "value") else str(task.status)
        add_task_log(
            self.db,
            task.id,
            f"Atualização de status '{requested_value}' ignorada: a task já está finalizada como "
            f"'{current_value}'.",
            level=TaskLogLevel.WARNING,
            source=TaskLogSource.SYSTEM,
            event_code="STATUS_TRANSITION_IGNORED",
            runner_id=runner.id,
        )
        self.lock_service.release_task_locks(task.id)
        self._refresh_runner_status(runner, reason="task_finalizada")
        self.db.commit()
        return task

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

        self._mark_alive(runner, reason="task_status_update")

        # Estados finais não voltam atrás (nem para outro final).
        if task.status in FINAL_STATUSES:
            return self._ignore_transition(runner, task, payload.status)

        if task.status == TaskStatus.WAITING and payload.status in RUNNER_PROGRESS_STATUSES:
            raise ValidationException(
                "A task ainda está em WAITING: faça o claim antes de informar progresso."
            )

        now = datetime.now(UTC)
        new_status = payload.status

        # STOP_REQUESTED é pegajoso e RUNNING não regride para READY.
        if task.status == TaskStatus.STOP_REQUESTED and new_status in (TaskStatus.READY, TaskStatus.RUNNING):
            new_status = TaskStatus.STOP_REQUESTED
        elif task.status == TaskStatus.RUNNING and new_status == TaskStatus.READY:
            new_status = TaskStatus.RUNNING

        update_data = {"status": new_status, "last_update_at": now}

        if payload.items_processed is not None:
            update_data["items_processed"] = payload.items_processed
        if payload.items_failed is not None:
            update_data["items_failed"] = payload.items_failed
        if payload.final_message is not None:
            update_data["final_message"] = payload.final_message
        if getattr(payload, "result_json", None) is not None:
            update_data["result_json"] = payload.result_json

        if payload.status == TaskStatus.RUNNING and task.started_at is None:
            update_data["started_at"] = now

        is_final = new_status in RUNNER_FINALIZABLE_STATUSES
        if is_final:
            update_data["finished_at"] = now
            if new_status == TaskStatus.ERROR and not (
                update_data.get("final_message") or task.final_message
            ):
                update_data["final_message"] = DEFAULT_ERROR_MESSAGE

        task = self.task_repository.update(task, update_data)

        if is_final:
            self.lock_service.release_task_locks(task.id)
        else:
            self.lock_service.renew_task_locks(task)

        if new_status == TaskStatus.FINISHED:
            # Gatilhos de sucesso (junho/2026): só na primeira transição para FINISHED
            # (estados finais já retornaram antes, em _ignore_transition).
            self._mark_credentials_valid(task)
            self.automation_trigger_service.create_success_followups(task)
        if is_final:
            retry_service.schedule_retry_if_applicable(self.db, task)
            event_service.enqueue_for_task(self.db, task)

        self._refresh_runner_status(runner, reason="task_finalizada" if is_final else "task_progress")
        self.db.commit()
        return task

    def finish_task(self, task_id: int, payload):
        runner = self._authenticate_runner(payload.uuid, payload.token)
        task = self.task_repository.get_by_id(task_id)

        self._validate_task_runner_ownership(task, runner)

        if payload.status not in RUNNER_FINALIZABLE_STATUSES:
            raise ValidationException("Finalização exige status final válido.")

        self._mark_alive(runner, reason="task_finish")

        if task.status in FINAL_STATUSES:
            return self._ignore_transition(runner, task, payload.status)

        now = datetime.now(UTC)

        update_data = {
            "status": payload.status,
            "started_at": task.started_at or now,
            "finished_at": now,
            "last_update_at": now,
        }

        final_message = payload.final_message if payload.final_message is not None else task.final_message
        if payload.status == TaskStatus.ERROR and not final_message:
            final_message = DEFAULT_ERROR_MESSAGE
        if final_message is not None:
            update_data["final_message"] = final_message

        if getattr(payload, "result_json", None) is not None:
            update_data["result_json"] = payload.result_json

        # Nulos não sobrescrevem contadores já registrados.
        if getattr(payload, "items_processed", None) is not None:
            update_data["items_processed"] = payload.items_processed
        if getattr(payload, "items_failed", None) is not None:
            update_data["items_failed"] = payload.items_failed

        task = self.task_repository.update(task, update_data)

        self.lock_service.release_task_locks(task.id)
        self._refresh_runner_status(runner, reason="task_finalizada")

        if payload.status == TaskStatus.FINISHED:
            self._mark_credentials_valid(task)
            self.automation_trigger_service.create_success_followups(task)
        retry_service.schedule_retry_if_applicable(self.db, task)
        event_service.enqueue_for_task(self.db, task)

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
                "runner_id": runner.id,
            }
        )

        # Log do worker é atividade da task (alimenta inactivity_timeout e renova o lock).
        self._touch_task(task)
        self._mark_alive(runner, reason="task_log")

        self.db.commit()

        return WorkerTaskLogResponse(
            message="Log registrado com sucesso.",
            task_id=task.id,
        )

    def create_task_error(self, task_id: int, payload) -> WorkerTaskErrorResponse:
        runner = self._authenticate_runner(payload.uuid, payload.token)
        task = self.task_repository.get_by_id(task_id)

        self._validate_task_runner_ownership(task, runner)

        error_screenshot = None

        if payload.error_screenshot_base64:
            image_base64 = payload.error_screenshot_base64.strip()

            if "," in image_base64:
                image_base64 = image_base64.split(",", 1)[1]

            try:
                error_screenshot = base64.b64decode(image_base64, validate=True)
            except (binascii.Error, ValueError):
                raise ValidationException("Imagem de erro inválida. Envie uma imagem em base64 válido.")

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
                "error_screenshot": error_screenshot,
            }
        )

        self._touch_task(task)
        self._mark_alive(runner, reason="task_error")

        self.db.commit()

        return WorkerTaskErrorResponse(
            message="Erro registrado com sucesso.",
            task_id=task.id,
        )

    def resolve_credential_for_runner(self, credential_id: int, payload):
        runner = self._authenticate_runner(payload.uuid, payload.token)

        credential = self.credential_repository.get_by_id(credential_id)
        if not credential:
            raise NotFoundException("Credencial não encontrada.")

        if not credential.active:
            raise ValidationException("Credencial está inativa.")

        # A credencial só sai para a task que a usa, e só se for do mesmo repositório da automação.
        # Antes qualquer máquina autenticada resolvia qualquer credencial pelo id.
        task_id = getattr(payload, "task_id", None)
        if task_id is not None:
            task = self.task_repository.get_by_id(task_id)
            if not task or task.runner_id != runner.id:
                raise ForbiddenException("A task informada não pertence a esta máquina.")
            automation = task.automation or self.task_repository.get_automation_by_id(task.automation_id)
            if automation is not None and automation.repository_id != credential.repository_id:
                raise ForbiddenException(
                    f"Credencial '{credential.label}' é de outro repositório e não pode ser usada por esta automação."
                )
        else:
            logger.warning(
                "Worker do runner %s resolveu a credencial %s sem informar a task (worker antigo).",
                runner.id, credential.id,
            )

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

    def report_credential_alert(self, task_id: int, payload):
        """Robô avisou (via worker) que a credencial não serve mais: marca, pausa agendamentos, bloqueia."""
        runner = self._authenticate_runner(payload.uuid, payload.token)
        task = self.task_repository.get_by_id(task_id)
        self._validate_task_runner_ownership(task, runner)

        health = CredentialHealthService(self.db)
        credential = None
        if payload.credential_id is not None:
            credential = self.credential_repository.get_by_id(payload.credential_id)
        if credential is None:
            # Worker não soube dizer qual: procura no parameters_json da própria task.
            ids = health.credential_ids_for_task(task)
            if len(ids) == 1:
                credential = self.credential_repository.get_by_id(next(iter(ids)))

        if credential is None:
            add_task_log(
                self.db,
                task.id,
                "Robô avisou credencial inválida, mas a task não usa nenhuma credencial cadastrada "
                f"({payload.sistema or 'sistema não informado'}: {payload.mensagem or payload.motivo}).",
                level=TaskLogLevel.WARNING,
                source=TaskLogSource.BACKEND,
                event_code="credential_alert",
                runner_id=runner.id,
            )
            self.db.commit()
            return {"task_id": task.id, "credential_id": None, "status": "nao_encontrada", "schedules_paused": 0}

        paused = health.mark_invalid(
            credential,
            motivo=payload.motivo,
            mensagem=payload.mensagem,
            task=task,
            chave=payload.chave,
            sistema=payload.sistema,
        )
        event_service.enqueue_for_task(
            self.db,
            task,
            trigger_types=["credential_invalid"],
            extra={
                "credencial": credential.label,
                "credencial_id": credential.id,
                "motivo": credential.status,
                "chave": payload.chave,
                "sistema": payload.sistema,
                "mensagem": payload.mensagem,
            },
        )
        self.db.commit()
        return {
            "task_id": task.id,
            "credential_id": credential.id,
            "status": credential.status,
            "schedules_paused": paused,
        }

    def _mark_credentials_valid(self, task) -> None:
        """Task com sucesso: as credenciais usadas viram 'válida'. Nunca derruba o fechamento da task."""
        try:
            CredentialHealthService(self.db).mark_valid_from_task(task)
        except Exception:  # noqa: BLE001
            logger.exception("Falha ao marcar credenciais como válidas para a task %s", task.id)

    ATTACHMENT_MAX_BYTES = 5 * 1024 * 1024
    ATTACHMENTS_PER_TASK = 10

    def create_task_attachment(self, task_id: int, payload):
        """Arquivo anexado pelo robô (maestro.attach). Limites: 5 MB por arquivo, 10 por task."""
        from app.models.task_attachment import TaskAttachment

        runner = self._authenticate_runner(payload.uuid, payload.token)
        task = self.task_repository.get_by_id(task_id)
        self._validate_task_runner_ownership(task, runner)

        try:
            content = base64.b64decode(payload.content_base64, validate=True)
        except (binascii.Error, ValueError):
            raise ValidationException("Anexo inválido: envie o conteúdo em base64 válido.")
        if not content:
            raise ValidationException("Anexo vazio.")
        if len(content) > self.ATTACHMENT_MAX_BYTES:
            raise ValidationException(f"Anexo acima do limite de {self.ATTACHMENT_MAX_BYTES} bytes.")

        count = self.db.execute(
            select(func.count(TaskAttachment.id)).where(TaskAttachment.task_id == task.id)
        ).scalar_one()
        if int(count or 0) >= self.ATTACHMENTS_PER_TASK:
            raise ValidationException(f"A task já tem {self.ATTACHMENTS_PER_TASK} anexos (limite).")

        filename = (payload.filename or "arquivo").strip().replace("\\", "/").rsplit("/", 1)[-1][:255] or "arquivo"
        attachment = TaskAttachment(
            task_id=task.id,
            filename=filename,
            content_type=(payload.content_type or "application/octet-stream")[:120],
            size_bytes=len(content),
            description=(payload.description or None),
            content=content,
        )
        self.db.add(attachment)
        self.db.flush()
        add_task_log(
            self.db,
            task.id,
            f"Arquivo anexado: {filename} ({len(content)} bytes)" + (f" · {payload.description}" if payload.description else ""),
            level=TaskLogLevel.INFO,
            source=TaskLogSource.WORKER,
            event_code="attachment",
            runner_id=runner.id,
        )
        self.db.commit()
        return {"task_id": task.id, "attachment_id": attachment.id, "size_bytes": attachment.size_bytes}

    def update_task_progress(self, task_id: int, payload):
        """Etapa atual do robô (maestro.step). Só enquanto a task está em execução."""
        runner = self._authenticate_runner(payload.uuid, payload.token)
        task = self.task_repository.get_by_id(task_id)
        self._validate_task_runner_ownership(task, runner)

        if task.status in EXECUTING_STATUSES:
            task.progress_current = int(payload.current)
            task.progress_total = None if payload.total is None else int(payload.total)
            task.progress_text = (payload.text or None)
            task.last_update_at = datetime.now(UTC)
            self.db.add(task)
            self.db.commit()

        return {
            "task_id": task.id,
            "progress_current": task.progress_current,
            "progress_total": task.progress_total,
            "progress_text": task.progress_text,
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

        self._touch_task(task)
        self._mark_alive(runner, reason="task_telemetry")

        self.db.commit()

        return {
            "message": "Telemetria registrada com sucesso.",
            "task_id": task.id,
        }
