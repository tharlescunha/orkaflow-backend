# app/services/worker_error_service.py

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenException, NotFoundException
from app.models.task_error import TaskError
from app.repositories.task_repository import TaskRepository
from app.services.worker_service import WorkerService


class WorkerErrorService:
    def __init__(self, db: Session):
        self.db = db
        self.task_repository = TaskRepository(db)
        self.worker_service = WorkerService(db)

    def create_task_error(self, task_id: int, payload):
        runner = self.worker_service._authenticate_runner(payload.uuid, payload.token)
        task = self.task_repository.get_by_id(task_id)

        if not task:
            raise NotFoundException("Task não encontrada.")

        if task.runner_id != runner.id:
            raise ForbiddenException("Esta task não pertence a este runner.")

        error = TaskError(
            task_id=task.id,
            error_type=payload.error_type,
            message=payload.message,
            stacktrace=payload.stacktrace,
            error_category=payload.error_category,
            is_retryable=payload.is_retryable,
            source=payload.source,
            code=payload.code,
        )

        self.db.add(error)

        task.last_update_at = datetime.now(UTC)
        self.db.add(task)

        self.db.commit()
        self.db.refresh(error)

        return {
            "message": "Erro registrado com sucesso.",
            "task_id": task.id,
        }
    