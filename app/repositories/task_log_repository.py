from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.task import Task
from app.models.task_log import TaskLog


class TaskLogRepository:
    def __init__(self, db: Session):
        self.db = db

    def task_exists(self, task_id: int) -> bool:
        stmt = select(Task.id).where(Task.id == task_id)
        return self.db.execute(stmt).scalar_one_or_none() is not None

    def get_by_id(self, log_id: int) -> TaskLog | None:
        stmt = select(TaskLog).where(TaskLog.id == log_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def list_by_task(
        self,
        task_id: int,
        *,
        skip: int = 0,
        limit: int = 100,
        level=None,
    ) -> tuple[Sequence[TaskLog], int]:
        stmt = select(TaskLog).where(TaskLog.task_id == task_id)
        count_stmt = select(func.count(TaskLog.id)).where(TaskLog.task_id == task_id)

        if level is not None:
            stmt = stmt.where(TaskLog.level == level)
            count_stmt = count_stmt.where(TaskLog.level == level)

        stmt = stmt.order_by(TaskLog.created_at.desc(), TaskLog.id.desc()).offset(skip).limit(limit)

        items = self.db.execute(stmt).scalars().all()
        total = self.db.execute(count_stmt).scalar_one()

        return items, total

    def create(self, data: dict) -> TaskLog:
        log = TaskLog(**data)
        self.db.add(log)
        self.db.flush()
        self.db.refresh(log)
        return log
    