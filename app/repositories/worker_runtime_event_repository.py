from sqlalchemy.orm import Session

from app.models.worker_runtime_event import WorkerRuntimeEvent


class WorkerRuntimeEventRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, data: dict) -> WorkerRuntimeEvent:
        event = WorkerRuntimeEvent(**data)
        self.db.add(event)
        self.db.flush()
        self.db.refresh(event)
        return event

    def list_by_runner(
        self,
        runner_id: int,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> list[WorkerRuntimeEvent]:
        return (
            self.db.query(WorkerRuntimeEvent)
            .filter(WorkerRuntimeEvent.runner_id == runner_id)
            .order_by(WorkerRuntimeEvent.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def list_by_task(
        self,
        task_id: int,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> list[WorkerRuntimeEvent]:
        return (
            self.db.query(WorkerRuntimeEvent)
            .filter(WorkerRuntimeEvent.task_id == task_id)
            .order_by(WorkerRuntimeEvent.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
    