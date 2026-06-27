from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.task import Task
from app.models.task_error import TaskError


class TaskErrorRepository:
    def __init__(self, db: Session):
        self.db = db

    def task_exists(self, task_id: int) -> bool:
        stmt = select(Task.id).where(Task.id == task_id)
        return self.db.execute(stmt).scalar_one_or_none() is not None

    def get_by_id(self, error_id: int) -> TaskError | None:
        stmt = select(TaskError).where(TaskError.id == error_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def list_by_task(
        self,
        task_id: int,
        *,
        skip: int = 0,
        limit: int = 100,
        error_type: str | None = None,
    ) -> tuple[Sequence[TaskError], int]:
        stmt = select(TaskError).where(TaskError.task_id == task_id)
        count_stmt = select(func.count(TaskError.id)).where(TaskError.task_id == task_id)

        if error_type:
            stmt = stmt.where(TaskError.error_type == error_type)
            count_stmt = count_stmt.where(TaskError.error_type == error_type)

        stmt = stmt.order_by(TaskError.created_at.desc(), TaskError.id.desc()).offset(skip).limit(limit)

        items = self.db.execute(stmt).scalars().all()
        total = self.db.execute(count_stmt).scalar_one()

        return items, total

    def create(self, data: dict) -> TaskError:
        error = TaskError(**data)
        self.db.add(error)
        self.db.flush()
        self.db.refresh(error)
        return error
    