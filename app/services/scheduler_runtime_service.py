from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import TaskStatus
from app.models.automation import Automation
from app.models.task import Task


class SchedulerRuntimeService:
    def __init__(self, db: Session):
        self.db = db

    def promote_scheduled_tasks(self) -> int:
        now = datetime.now(UTC)

        stmt = (
            select(Task)
            .join(Automation, Automation.id == Task.automation_id)
            .where(Task.status == TaskStatus.SCHEDULED)
            .where(Task.requested_start_at.is_not(None))
            .where(Task.requested_start_at <= now)
            .where(Automation.active == True)
            .order_by(Task.requested_start_at.asc(), Task.id.asc())
        )

        tasks = list(self.db.execute(stmt).scalars().all())
        promoted = 0

        for task in tasks:
            task.status = TaskStatus.WAITING
            task.last_update_at = now
            self.db.add(task)
            promoted += 1

        if promoted:
            self.db.commit()

        return promoted
    