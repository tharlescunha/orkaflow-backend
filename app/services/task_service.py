# app/services/task_service.py

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundException, ValidationException
from app.domain.enums import ExecutionMode, TaskStatus
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


class TaskService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = TaskRepository(db)

    def list_tasks(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        status=None,
        automation_id: int | None = None,
        runner_id: int | None = None,
        created_by: int | None = None,
    ):
        return self.repository.list_all(
            skip=skip,
            limit=limit,
            status=status,
            automation_id=automation_id,
            runner_id=runner_id,
            created_by=created_by,
        )

    def get_task(self, task_id: int):
        task = self.repository.get_by_id(task_id)
        if not task:
            raise NotFoundException("Task não encontrada.")
        return task

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

        timeout_seconds = payload.timeout_seconds or 3600
        now = datetime.now(UTC)

        status = TaskStatus.SCHEDULED if requested_start_at else TaskStatus.WAITING

        if status == TaskStatus.WAITING:
            existing_waiting = self.repository.db.query(self.repository.model).filter(
                self.repository.model.automation_id == payload.automation_id,
                self.repository.model.status == TaskStatus.WAITING,
            ).order_by(self.repository.model.id.desc()).first()

            if existing_waiting:
                return self.get_task(existing_waiting.id)

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
    