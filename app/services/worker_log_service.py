# app/services/worker_log_service.py

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenException, NotFoundException
from app.models.task_log import TaskLog
from app.repositories.task_repository import TaskRepository
from app.services.worker_service import WorkerService


class WorkerLogService:
    def __init__(self, db: Session):
        self.db = db
        self.task_repository = TaskRepository(db)
        self.worker_service = WorkerService(db)

    def create_task_log(self, task_id: int, payload):
        runner = self.worker_service._authenticate_runner(payload.uuid, payload.token)
        task = self.task_repository.get_by_id(task_id)

        if not task:
            raise NotFoundException("Task não encontrada.")

        if task.runner_id != runner.id:
            raise ForbiddenException("Esta task não pertence a este runner.")

        log = TaskLog(
            task_id=task.id,
            level=payload.level,
            message=payload.message,
            source=payload.source,
            reference=payload.reference,
            error_type=payload.error_type,
            sequence_number=payload.sequence_number,
            event_code=payload.event_code,
            runner_id=runner.id,
        )

        self.db.add(log)

        # atualiza atividade da task
        task.last_update_at = datetime.now(UTC)
        self.db.add(task)

        self.db.commit()
        self.db.refresh(log)

        return {
            "message": "Log registrado com sucesso.",
            "task_id": task.id,
        }
    