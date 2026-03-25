from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundException
from app.repositories.task_error_repository import TaskErrorRepository
from app.schemas.task_error import TaskErrorCreate


class TaskErrorService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = TaskErrorRepository(db)

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
    