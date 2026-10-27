import logging
import json
from datetime import UTC, datetime

from app.core.exceptions import NotFoundException, ValidationException
from app.models.runner import Runner
from app.services import event_service, retry_service
from app.services.credential_health_service import CredentialHealthService
from app.services.task_rules import runner_in_maintenance
from app.domain.enums import ExecutionMode, RunnerStatus, TaskLogLevel, TaskLogSource, TaskStatus
from app.repositories.runner_repository import RunnerRepository
from app.repositories.task_repository import TaskRepository
from app.schemas.task import TaskParameterCreate, TaskCreate, TaskStatusUpdate, TaskUpdate
from app.services.automation_trigger_service import AutomationTriggerService
from app.services.capacity_service import CapacityService
from app.services.lock_service import LockService
from app.services.task_events import add_task_log
from app.services.task_rules import FINAL_STATUSES as _FINAL_STATUSES
from app.services.task_rules import as_aware

# Inclui FORCED_STOP (junho/2026).
FINAL_STATUSES = set(_FINAL_STATUSES)

STOP_ALLOWED_STATUSES = {
    TaskStatus.WAITING,
    TaskStatus.READY,
    TaskStatus.RUNNING,
    TaskStatus.STOP_REQUESTED,
}

FORCE_STOP_ALLOWED_STATUSES = {
    TaskStatus.READY,
    TaskStatus.RUNNING,
    TaskStatus.STOP_REQUESTED,
}

CANCEL_ALLOWED_STATUSES = {
    TaskStatus.WAITING,
    TaskStatus.SCHEDULED,
    TaskStatus.READY,
}


def _calculate_execution_duration_seconds(task) -> int | None:
    # as_aware: datas sem fuso (bancos/drivers que devolvem naive) não podem derrubar a listagem.
    started_at = as_aware(task.started_at)
    finished_at = as_aware(task.finished_at)
    if started_at and finished_at:
        return int((finished_at - started_at).total_seconds())

    if started_at and task.status == TaskStatus.RUNNING:
        now = datetime.now(UTC)
        return int((now - started_at).total_seconds())

    return None


logger = logging.getLogger(__name__)


class TaskService:
    def __init__(self, db):
        self.db = db
        self.repository = TaskRepository(db)
        self.runner_repository = RunnerRepository(db)
        self.lock_service = LockService(db)
        self.capacity = CapacityService(db)
        self.automation_trigger_service = AutomationTriggerService(db)

    def _release_after_final(self, task) -> None:
        """Libera os locks da task na hora e recalcula o estado do runner (derivado das tasks).

        Não bloqueia nem pausa o runner: o runner só deixa de receber tasks se o
        administrador o desativar.
        """
        self.lock_service.release_task_locks(task.id)
        self.capacity.refresh_runner_status_by_id(task.runner_id, reason="task_finalizada")
        # Retentativa automática e eventos "Quando → Então" (out/2026); nenhum dos dois derruba a task.
        retry_service.schedule_retry_if_applicable(self.db, task)
        event_service.enqueue_for_task(self.db, task)

    def _get_automation_name(self, task) -> str | None:
        if not getattr(task, "automation", None):
            return None

        return task.automation.label or task.automation.name

    def _get_bot_version_label(self, task) -> str | None:
        if not getattr(task, "bot_version", None):
            return None

        return getattr(task.bot_version, "version", None)

    def _get_runner_name(self, task) -> str | None:
        if not getattr(task, "runner", None):
            return None

        return task.runner.name

    def _get_runner_label(self, task) -> str | None:
        if not getattr(task, "runner", None):
            return None

        return task.runner.label

    def _get_runner_display_name(self, task) -> str | None:
        if not getattr(task, "runner", None):
            return None

        return task.runner.label or task.runner.name

    def _get_created_by_name(self, task) -> str | None:
        if not getattr(task, "created_by_user", None):
            return None

        return task.created_by_user.name

    def _get_schedule_name(self, task) -> str | None:
        if not getattr(task, "schedule", None):
            return None

        return task.schedule.name

    def _build_telemetry_payload(self, task):
        if not task.telemetry:
            return None

        telemetry = task.telemetry
        return {
            "id": telemetry.id,
            "task_id": telemetry.task_id,
            "runner_id": telemetry.runner_id,
            "captured_at": telemetry.captured_at,
            "execution_started_at": telemetry.execution_started_at,
            "execution_finished_at": telemetry.execution_finished_at,
            "duration_seconds": telemetry.duration_seconds,
            "cpu_percent_avg": telemetry.cpu_percent_avg,
            "cpu_percent_peak": telemetry.cpu_percent_peak,
            "memory_used_mb_avg": telemetry.memory_used_mb_avg,
            "memory_used_mb_peak": telemetry.memory_used_mb_peak,
            "process_memory_mb_peak": telemetry.process_memory_mb_peak,
            "disk_read_mb": telemetry.disk_read_mb,
            "disk_write_mb": telemetry.disk_write_mb,
            "net_sent_mb": telemetry.net_sent_mb,
            "net_recv_mb": telemetry.net_recv_mb,
            "exit_code": telemetry.exit_code,
            "telemetry_status": telemetry.telemetry_status,
            "message": telemetry.message,
            "payload_json": telemetry.payload_json,
            "created_at": telemetry.created_at,
        }

    def _build_runner_details_payload(self, task):
        runner = task.runner
        if not runner:
            return None

        config_payload = None
        if runner.config:
            config_payload = {
                "id": runner.config.id,
                "runner_id": runner.config.runner_id,
                "max_concurrency": runner.config.max_concurrency,
                "allowed_parallel_bots": runner.config.allowed_parallel_bots,
                "polling_interval": runner.config.polling_interval,
                "auto_update_bots": runner.config.auto_update_bots,
                "install_all_bots_on_register": runner.config.install_all_bots_on_register,
                "maintenance_mode": runner.config.maintenance_mode,
                "created_at": runner.config.created_at,
                "updated_at": runner.config.updated_at,
            }

        return {
            "id": runner.id,
            "uuid": runner.uuid,
            "name": runner.name,
            "label": runner.label,
            "display_name": runner.label or runner.name,
            "host_name": runner.host_name,
            "ip": runner.ip,
            "os_name": runner.os_name,
            "os_version": runner.os_version,
            "cpu_arch": runner.cpu_arch,
            "memory_total": runner.memory_total,
            "access_remote": runner.access_remote,
            "enabled": runner.enabled,
            "status": runner.status.value if hasattr(runner.status, "value") else str(runner.status),
            "last_heartbeat": runner.last_heartbeat,
            "created_at": runner.created_at,
            "updated_at": runner.updated_at,
            "config": config_payload,
        }

    def _build_runner_usage_payload(self, task):
        runner = task.runner
        if not runner:
            return None

        period_start = runner.created_at
        period_end = task.finished_at or datetime.now(UTC)

        if not period_start or not period_end or period_end <= period_start:
            return {
                "period_start": period_start,
                "period_end": period_end,
                "available_seconds": 0,
                "execution_seconds": 0,
                "usage_percent": 0.0,
            }

        available_seconds = int((period_end - period_start).total_seconds())
        execution_seconds = self.runner_repository.get_total_execution_seconds(
            runner_id=runner.id,
            date_from=period_start,
            date_to=period_end,
        )

        usage_percent = 0.0
        if available_seconds > 0:
            usage_percent = round((execution_seconds / available_seconds) * 100, 2)

        return {
            "period_start": period_start,
            "period_end": period_end,
            "available_seconds": available_seconds,
            "execution_seconds": execution_seconds,
            "usage_percent": usage_percent,
        }

    def _serialize_task_read(self, task):
        return {
            "id": task.id,
            "automation_id": task.automation_id,
            "automation_name": self._get_automation_name(task),
            "bot_version_id": task.bot_version_id,
            "bot_version_label": self._get_bot_version_label(task),
            "runner_id": task.runner_id,
            "runner_name": self._get_runner_name(task),
            "runner_label": self._get_runner_label(task),
            "runner_display_name": self._get_runner_display_name(task),
            "created_by": task.created_by,
            "created_by_name": self._get_created_by_name(task),
            "schedule_id": task.schedule_id,
            "schedule_name": self._get_schedule_name(task),
            "parent_task_id": task.parent_task_id,
            "priority": task.priority,
            "status": task.status,
            "requested_start_at": task.requested_start_at,
            "started_at": task.started_at,
            "finished_at": task.finished_at,
            "last_update_at": task.last_update_at,
            "final_message": task.final_message,
            "result_json": task.result_json,
            "items_processed": task.items_processed,
            "items_failed": task.items_failed,
            "timeout_seconds": task.timeout_seconds,
            "retry_count": task.retry_count,
            "execution_mode": task.execution_mode,
            "dispatch_attempts": task.dispatch_attempts,
            "stop_requested": task.stop_requested,
            "waiting_reason": task.waiting_reason if task.status == TaskStatus.WAITING else None,
            "correlation_id": task.correlation_id,
            "queue_name": task.queue_name,
            "inactivity_timeout_seconds": task.inactivity_timeout_seconds,
            "runner_claimed_at": task.runner_claimed_at,
            "created_at": task.created_at,
            "updated_at": getattr(task, "updated_at", None),
            "parameters": list(task.parameters or []),
            "children": [
                {
                    "id": child.id,
                    "automation_id": child.automation_id,
                    "automation_name": self._get_automation_name(child),
                    "status": child.status,
                    "execution_mode": child.execution_mode,
                    "retry_count": child.retry_count,
                    "created_at": child.created_at,
                    "finished_at": child.finished_at,
                }
                for child in self.repository.list_children(task.id)
            ],
            "telemetry": self._build_telemetry_payload(task),
            "runner_details": self._build_runner_details_payload(task),
            "runner_usage": self._build_runner_usage_payload(task),
            "execution_duration_seconds": _calculate_execution_duration_seconds(task),
        }

    def get_filter_options(self):
        automations = self.repository.list_active_automation_options()
        runners = self.repository.list_active_runner_options()

        return {
            "automations": [
                {
                    "id": automation.id,
                    "name": automation.name,
                    "label": automation.label or automation.name,
                }
                for automation in automations
            ],
            "runners": [
                {
                    "id": runner.id,
                    "name": runner.name,
                    "label": runner.label or runner.name,
                }
                for runner in runners
            ],
            "statuses": [status for status in TaskStatus],
        }

    def list_tasks(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        statuses: list[TaskStatus] | None = None,
        automation_ids: list[int] | None = None,
        runner_ids: list[int] | None = None,
        created_by: int | None = None,
    ):
        items, total = self.repository.list_all(
            skip=skip,
            limit=limit,
            statuses=statuses,
            automation_ids=automation_ids,
            runner_ids=runner_ids,
            created_by=created_by,
        )

        result = []
        for task in items:
            result.append(
                {
                    "id": task.id,
                    "automation_id": task.automation_id,
                    "automation_name": self._get_automation_name(task),
                    "bot_version_id": task.bot_version_id,
                    "bot_version_label": self._get_bot_version_label(task),
                    "runner_id": task.runner_id,
                    "runner_name": self._get_runner_name(task),
                    "runner_label": self._get_runner_label(task),
                    "runner_display_name": self._get_runner_display_name(task),
                    "created_by": task.created_by,
                    "created_by_name": self._get_created_by_name(task),
                    "schedule_id": task.schedule_id,
                    "schedule_name": self._get_schedule_name(task),
                    "priority": task.priority,
                    "status": task.status,
                    "requested_start_at": task.requested_start_at,
                    "started_at": task.started_at,
                    "finished_at": task.finished_at,
                    "last_update_at": task.last_update_at,
                    "created_at": task.created_at,
                    "items_processed": task.items_processed,
                    "items_failed": task.items_failed,
                    "execution_mode": task.execution_mode,
                    "retry_count": task.retry_count,
                    "parent_task_id": task.parent_task_id,
                    "stop_requested": task.stop_requested,
                    "waiting_reason": task.waiting_reason if task.status == TaskStatus.WAITING else None,
                    "correlation_id": task.correlation_id,
                    "queue_name": task.queue_name,
                    "execution_duration_seconds": _calculate_execution_duration_seconds(task),
                    "final_message": task.final_message,
                    "result_json": task.result_json,
                }
            )

        return result, total

    def get_task(self, task_id: int):
        task = self.repository.get_by_id(task_id)
        if not task:
            raise NotFoundException("Task não encontrada.")
        return self._serialize_task_read(task)

    def get_task_parameters(self, task_id: int):
        task = self.repository.get_by_id(task_id)
        if not task:
            raise NotFoundException("Task não encontrada.")
        return self.repository.get_parameters(task_id)

    def create_manual_task(self, payload: TaskCreate, created_by: int | None = None):
        automation = self.repository.get_automation_by_id(payload.automation_id)
        if not automation:
            raise NotFoundException("Automação não encontrada.")

        if not automation.active:
            raise ValidationException("Não é permitido criar task para automação inativa.")

        bot = automation.bot
        if not bot:
            raise ValidationException("Bot da automação não encontrado.")

        if not bot.active:
            raise ValidationException("Não é permitido criar task para bot inativo.")

        # Credencial inválida (senha expirada etc.): recusa com 409 para não bloquear o usuário no destino.
        CredentialHealthService(self.db).ensure_automation_credentials_usable(automation)

        bot_version_id = payload.bot_version_id
        if bot_version_id is None:
            latest_bot_version = self.repository.get_latest_bot_version_for_bot(automation.bot_id)
            if not latest_bot_version:
                raise ValidationException(
                    "A automação não possui bot version disponível para execução."
                )
            bot_version_id = latest_bot_version.id

        if payload.runner_id is not None:
            has_link = self.repository.automation_has_runner_link(
                payload.automation_id,
                payload.runner_id,
            )
            if not has_link:
                raise ValidationException(
                    "O runner informado não está vinculado à automação."
                )
            pinned_runner = self.db.get(Runner, payload.runner_id)
            if runner_in_maintenance(pinned_runner):
                raise ValidationException(
                    "Essa máquina está em modo manutenção e não recebe tasks novas. Escolha outra ou deixe sem máquina."
                )

        automation_parameters = self.repository.get_automation_parameters(payload.automation_id)
        provided_parameters = {p.parameter_name: p for p in payload.parameters}
        self._validate_json_parameter_if_present(provided_parameters, "parameters_json")
        self._validate_json_parameter_if_present(provided_parameters, "runtime_parameters_json")
        # O que o chamador não mandou vem do padrão da automação (o agendador e o MCP já faziam isso;
        # a API e a tela não). Assim o dados_acesso fica cadastrado na automação, não em quem chama.
        self._merge_automation_defaults(provided_parameters, automation, "parameters_json", "default_parameters_json")
        self._merge_automation_defaults(
            provided_parameters, automation, "runtime_parameters_json", "default_runtime_parameters_json"
        )
        self._validate_json_parameter_if_present(provided_parameters, "runtime_parameters_json")
        runtime_parameters = self._extract_runtime_parameters(provided_parameters)

        missing_required = [
            param.name
            for param in automation_parameters
            if getattr(param, "required", False)
            and param.name not in provided_parameters
            and param.name not in runtime_parameters
            and getattr(param, "default_value", None) in (None, "")
        ]
        if missing_required:
            raise ValidationException(
                f"Parâmetros obrigatórios ausentes: {', '.join(missing_required)}."
            )

        requested_start_at = payload.requested_start_at
        if requested_start_at and requested_start_at.tzinfo is None:
            raise ValidationException("requested_start_at deve possuir timezone.")

        if payload.parent_task_id is None:
            open_task = self.repository.get_open_task_for_automation(payload.automation_id)
            if open_task:
                raise ValidationException(
                    "Ja existe task aberta para esta automacao "
                    f"(task_id={open_task.id}, status={open_task.status.value})."
                )

        timeout_seconds = payload.timeout_seconds or bot.timeout_default or 3600
        now = datetime.now(UTC)

        status = TaskStatus.SCHEDULED if requested_start_at else TaskStatus.WAITING

        task_data = {
            "automation_id": payload.automation_id,
            "bot_version_id": bot_version_id,
            "runner_id": payload.runner_id,
            "created_by": created_by,
            "schedule_id": payload.schedule_id,
            "parent_task_id": payload.parent_task_id,
            "priority": payload.priority,
            "status": status,
            "requested_start_at": requested_start_at,
            "timeout_seconds": timeout_seconds,
            "execution_mode": payload.execution_mode or ExecutionMode.MANUAL,
            "correlation_id": payload.correlation_id,
            "queue_name": payload.queue_name,
            "inactivity_timeout_seconds": payload.inactivity_timeout_seconds,
            "last_update_at": now,
            "created_at": now,
        }

        task = self.repository.create(task_data)

        final_parameters: list[dict] = []
        automation_param_names = {ap.name for ap in automation_parameters}

        for param in automation_parameters:
            if param.name in provided_parameters:
                incoming = provided_parameters[param.name]
                final_parameters.append(
                    {
                        "parameter_name": incoming.parameter_name,
                        "parameter_value": incoming.parameter_value,
                        "is_secret": incoming.is_secret,
                        "resolved_from_credential_item_id": incoming.resolved_from_credential_item_id,
                    }
                )
            elif getattr(param, "default_value", None) not in (None, ""):
                final_parameters.append(
                    {
                        "parameter_name": param.name,
                        "parameter_value": param.default_value,
                        "is_secret": False,
                        "resolved_from_credential_item_id": None,
                    }
                )

        extra_parameters = [
            p for p in provided_parameters.values()
            if p.parameter_name not in automation_param_names
        ]
        for extra in extra_parameters:
            final_parameters.append(
                {
                    "parameter_name": extra.parameter_name,
                    "parameter_value": extra.parameter_value,
                    "is_secret": extra.is_secret,
                    "resolved_from_credential_item_id": extra.resolved_from_credential_item_id,
                }
            )

        if final_parameters:
            self.repository.create_parameters_bulk(task.id, final_parameters)

        self.db.commit()
        return self.get_task(task.id)

    @staticmethod
    def _merge_automation_defaults(provided: dict, automation, param_name: str, default_attr: str) -> None:
        defaults = getattr(automation, default_attr, None)
        if not isinstance(defaults, dict) or not defaults:
            return
        incoming = provided.get(param_name)
        if incoming is None:
            provided[param_name] = TaskParameterCreate(
                parameter_name=param_name,
                parameter_value=json.dumps(defaults, ensure_ascii=False),
                is_secret=False,
                resolved_from_credential_item_id=None,
            )
            return
        try:
            current = json.loads(incoming.parameter_value or "{}")
        except Exception:  # noqa: BLE001
            return
        if not isinstance(current, dict):
            return
        merged = {**defaults, **current}
        if merged != current:
            provided[param_name] = incoming.model_copy(
                update={"parameter_value": json.dumps(merged, ensure_ascii=False)}
            )

    def _extract_runtime_parameters(self, provided_parameters: dict) -> dict:
        runtime_param = provided_parameters.get("runtime_parameters_json")
        if not runtime_param:
            return {}

        raw_value = getattr(runtime_param, "parameter_value", None)
        if not raw_value:
            return {}

        try:
            parsed_value = json.loads(raw_value)
        except Exception:
            return {}

        return parsed_value if isinstance(parsed_value, dict) else {}

    def _validate_json_parameter_if_present(
        self,
        provided_parameters: dict,
        parameter_name: str,
    ) -> None:
        parameter = provided_parameters.get(parameter_name)
        if not parameter:
            return

        raw_value = getattr(parameter, "parameter_value", None)
        if raw_value in (None, ""):
            return

        try:
            parsed_value = json.loads(raw_value)
        except Exception:
            raise ValidationException(f"Parametro {parameter_name} precisa ser JSON valido.")

        if parameter_name == "runtime_parameters_json" and not isinstance(parsed_value, dict):
            raise ValidationException("Parametro runtime_parameters_json precisa ser objeto JSON.")

    def update_task(self, task_id: int, payload: TaskUpdate):
        task = self.repository.get_by_id(task_id)
        if not task:
            raise NotFoundException("Task não encontrada.")

        data = payload.model_dump(exclude_unset=True)

        if "runner_id" in data and data["runner_id"] is not None:
            has_link = self.repository.automation_has_runner_link(task.automation_id, data["runner_id"])
            if not has_link:
                raise ValidationException("O runner informado não está vinculado à automação da task.")

        data["last_update_at"] = datetime.now(UTC)

        self.repository.update(task, data)
        self.db.commit()
        return self.get_task(task.id)

    def request_stop(self, task_id: int):
        task = self.repository.get_by_id(task_id)
        if not task:
            raise NotFoundException("Task não encontrada.")

        if task.status in FINAL_STATUSES:
            raise ValidationException("Não é permitido solicitar parada para task finalizada.")

        if task.status not in STOP_ALLOWED_STATUSES:
            raise ValidationException("A task não está em um estado válido para solicitar parada.")

        now = datetime.now(UTC)

        # WAITING ainda não foi assumida por nenhum worker: cancela direto.
        if task.status == TaskStatus.WAITING:
            task = self.repository.update(
                task,
                {
                    "status": TaskStatus.CANCELED,
                    "finished_at": now,
                    "last_update_at": now,
                    "final_message": task.final_message or "Task cancelada antes de iniciar (parada solicitada).",
                },
            )
            add_task_log(
                self.db,
                task.id,
                "Parada solicitada com a task ainda em WAITING: task cancelada diretamente.",
                level=TaskLogLevel.INFO,
                source=TaskLogSource.PANEL,
                event_code="STOP_REQUESTED_WAITING_CANCELED",
            )
            self._release_after_final(task)
            self.db.commit()
            return task

        task = self.repository.update(
            task,
            {
                "stop_requested": True,
                "status": TaskStatus.STOP_REQUESTED,
                "last_update_at": now,
            },
        )
        self.db.commit()
        return task

    def force_stop(self, task_id: int):
        task = self.repository.get_by_id(task_id)
        if not task:
            raise NotFoundException("Task não encontrada.")

        if task.status in FINAL_STATUSES:
            raise ValidationException("Não é permitido forçar parada em task finalizada.")

        if task.status not in FORCE_STOP_ALLOWED_STATUSES:
            raise ValidationException("A task não está em um estado válido para parada forçada.")

        now = datetime.now(UTC)
        runner_id = task.runner_id

        task = self.repository.update(
            task,
            {
                "stop_requested": True,
                "status": TaskStatus.FORCED_STOP,
                "finished_at": now,
                "last_update_at": now,
                "final_message": task.final_message or "Task interrompida por parada forçada.",
            },
        )
        self._release_after_final(task)
        self.db.commit()
        return task

    def cancel_task(self, task_id: int):
        task = self.repository.get_by_id(task_id)
        if not task:
            raise NotFoundException("Task não encontrada.")

        if task.status in FINAL_STATUSES:
            raise ValidationException("Não é permitido cancelar task finalizada.")

        if task.status not in CANCEL_ALLOWED_STATUSES:
            raise ValidationException("Somente tasks ainda não processadas podem ser canceladas.")

        now = datetime.now(UTC)
        runner_id = task.runner_id

        task = self.repository.update(
            task,
            {
                "status": TaskStatus.CANCELED,
                "finished_at": now,
                "last_update_at": now,
                "final_message": task.final_message or "Task cancelada manualmente.",
            },
        )
        self._release_after_final(task)
        self.db.commit()
        return task

    def update_status(self, task_id: int, payload: TaskStatusUpdate):
        task = self.repository.get_by_id(task_id)
        if not task:
            raise NotFoundException("Task não encontrada.")

        previous_status = task.status
        data = payload.model_dump(exclude_unset=True)

        if "last_update_at" not in data:
            data["last_update_at"] = datetime.now(UTC)

        if payload.status in FINAL_STATUSES and "finished_at" not in data:
            data["finished_at"] = datetime.now(UTC)

        task = self.repository.update(task, data)
        if previous_status not in FINAL_STATUSES and payload.status == TaskStatus.FINISHED:
            try:
                CredentialHealthService(self.db).mark_valid_from_task(task)
            except Exception:  # noqa: BLE001
                logger.exception("Falha ao marcar credenciais como válidas para a task %s", task.id)
            self.automation_trigger_service.create_success_followups(task)
        if task.status in FINAL_STATUSES:
            self._release_after_final(task)
        self.db.commit()
        return task

