from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundException
from app.repositories.task_log_repository import TaskLogRepository
from app.schemas.task_log import TaskLogCreate


class TaskLogService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = TaskLogRepository(db)

    def list_by_task(
        self,
        task_id: int,
        *,
        skip: int = 0,
        limit: int = 100,
        level=None,
    ):
        if not self.repository.task_exists(task_id):
            raise NotFoundException("Task não encontrada.")

        return self.repository.list_by_task(
            task_id,
            skip=skip,
            limit=limit,
            level=level,
        )

    def get_log(self, log_id: int):
        log = self.repository.get_by_id(log_id)
        if not log:
            raise NotFoundException("Log não encontrado.")
        return log

    def create_log(self, payload: TaskLogCreate):
        if not self.repository.task_exists(payload.task_id):
            raise NotFoundException("Task não encontrada.")

        log = self.repository.create(payload.model_dump())
        self.db.commit()
        return log
    