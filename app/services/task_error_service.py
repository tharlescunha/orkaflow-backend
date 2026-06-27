from datetime import datetime

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundException
from app.repositories.task_error_repository import TaskErrorRepository
from app.repositories.task_error_repository_extended import TaskErrorRepositoryExtended
from app.schemas.task_error import TaskErrorCreate


class TaskErrorService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = TaskErrorRepository(db)
        self.extended_repository = TaskErrorRepositoryExtended(db)

    def list_all(
        self,
        *,
        skip: int = 0,
        limit: int = 10,
        q: str | None = None,
        task_id: int | None = None,
        automation_id: int | None = None,
        error_type: str | None = None,
        error_category: str | None = None,
        source: str | None = None,
        code: str | None = None,
        is_retryable: bool | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ):
        return self.extended_repository.list_all(
            skip=skip,
            limit=limit,
            q=q,
            task_id=task_id,
            automation_id=automation_id,
            error_type=error_type,
            error_category=error_category,
            source=source,
            code=code,
            is_retryable=is_retryable,
            start_date=start_date,
            end_date=end_date,
        )

    def get_rich_error(self, error_id: int):
        error = self.extended_repository.get_rich_error(error_id)
        if not error:
            raise NotFoundException("Erro não encontrado.")
        return error

    def list_by_task(
        self,
        task_id: int,
        *,
        skip: int = 0,
        limit: int = 100,
        error_type: str | None = None,
    ):
        if not self.repository.task_exists(task_id):
            raise NotFoundException("Task não encontrada.")

        return self.repository.list_by_task(
            task_id,
            skip=skip,
            limit=limit,
            error_type=error_type,
        )

    def get_error(self, error_id: int):
        error = self.repository.get_by_id(error_id)
        if not error:
            raise NotFoundException("Erro não encontrado.")
        return error

    def create_error(self, payload: TaskErrorCreate):
        if not self.repository.task_exists(payload.task_id):
            raise NotFoundException("Task não encontrada.")

        error = self.repository.create(payload.model_dump())
        self.db.commit()
        return error
    