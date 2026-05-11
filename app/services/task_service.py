from datetime import UTC, datetime

from app.core.exceptions import NotFoundException, ValidationException
from app.domain.enums import ExecutionMode, TaskStatus
from app.repositories.runner_repository import RunnerRepository
from app.repositories.task_repository import TaskRepository
from app.schemas.task import TaskCreate, TaskStatusUpdate, TaskUpdate

FINAL_STATUSES = {
    TaskStatus.FINISHED,
    TaskStatus.ERROR,
    TaskStatus.CANCELED,
    TaskStatus.TIMEOUT,
}

STOP_ALLOWED_STATUSES = {
    TaskStatus.WAITING,
    TaskStatus.READY,
    TaskStatus.RUNNING,
    TaskStatus.STOP_REQUESTED,
}

FORCE_STOP_ALLOWED_STATUSES = {
    TaskStatus.RUNNING,
    TaskStatus.STOP_REQUESTED,
    TaskStatus.TIMEOUT,
}

CANCEL_ALLOWED_STATUSES = {
    TaskStatus.WAITING,
    TaskStatus.SCHEDULED,
    TaskStatus.READY,
}


def _calculate_execution_duration_seconds(task) -> int | None:
    if task.started_at and task.finished_at:
        return int((task.finished_at - task.started_at).total_seconds())

    if task.started_at and task.status == TaskStatus.RUNNING:
        now = datetime.now(UTC)
        return int((now - task.started_at).total_seconds())

    return None


class TaskService:
    def __init__(self, db):
        self.db = db
        self.repository = TaskRepository(db)
        self.runner_repository = RunnerRepository(db)

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
            "items_processed": task.items_processed,
            "items_failed": task.items_failed,
            "timeout_seconds": task.timeout_seconds,
            "retry_count": task.retry_count,
            "execution_mode": task.execution_mode,
            "dispatch_attempts": task.dispatch_attempts,
            "stop_requested": task.stop_requested,
            "correlation_id": task.correlation_id,
            "queue_name": task.queue_name,
            "inactivity_timeout_seconds": task.inactivity_timeout_seconds,
            "runner_claimed_at": task.runner_claimed_at,
            "created_at": task.created_at,
            "updated_at": getattr(task, "updated_at", None),
            "parameters": list(task.parameters or []),
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
                    "stop_requested": task.stop_requested,
                    "correlation_id": task.correlation_id,
                    "queue_name": task.queue_name,
                    "execution_duration_seconds": _calculate_execution_duration_seconds(task),
                    "final_message": task.final_message,
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

        automation_parameters = self.repository.get_automation_parameters(payload.automation_id)
        provided_parameters = {p.parameter_name: p for p in payload.parameters}

        missing_required = [
            param.name
            for param in automation_parameters
            if getattr(param, "required", False)
            and param.name not in provided_parameters
            and getattr(param, "default_value", None) in (None, "")
        ]
        if missing_required:
            raise ValidationException(
                f"Parâmetros obrigatórios ausentes: {', '.join(missing_required)}."
            )

        requested_start_at = payload.requested_start_at
        if requested_start_at and requested_start_at.tzinfo is None:
            raise ValidationException("requested_start_at deve possuir timezone.")

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
            p for p in payload.parameters
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

        task = self.repository.update(
            task,
            {
                "stop_requested": True,
                "status": TaskStatus.STOP_REQUESTED,
                "last_update_at": datetime.now(UTC),
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

        task = self.repository.update(
            task,
            {
                "stop_requested": True,
                "status": TaskStatus.FORCED_STOP,
                "finished_at": datetime.now(UTC),
                "last_update_at": datetime.now(UTC),
                "final_message": task.final_message or "Task interrompida por parada forçada.",
            },
        )
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

        task = self.repository.update(
            task,
            {
                "status": TaskStatus.CANCELED,
                "finished_at": datetime.now(UTC),
                "last_update_at": datetime.now(UTC),
                "final_message": task.final_message or "Task cancelada manualmente.",
            },
        )
        self.db.commit()
        return task

    def update_status(self, task_id: int, payload: TaskStatusUpdate):
        task = self.repository.get_by_id(task_id)
        if not task:
            raise NotFoundException("Task não encontrada.")

        data = payload.model_dump(exclude_unset=True)

        if "last_update_at" not in data:
            data["last_update_at"] = datetime.now(UTC)

        if payload.status in FINAL_STATUSES and "finished_at" not in data:
            data["finished_at"] = datetime.now(UTC)

        task = self.repository.update(task, data)
        self.db.commit()
        return task

