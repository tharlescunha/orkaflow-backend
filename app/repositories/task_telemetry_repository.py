from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.task_telemetry import TaskTelemetry


class TaskTelemetryRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_task_id(self, task_id: int) -> TaskTelemetry | None:
        stmt = select(TaskTelemetry).where(TaskTelemetry.task_id == task_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def create(self, data: dict) -> TaskTelemetry:
        telemetry = TaskTelemetry(**data)
        self.db.add(telemetry)
        self.db.flush()
        self.db.refresh(telemetry)
        return telemetry

    def update(self, telemetry: TaskTelemetry, data: dict) -> TaskTelemetry:
        for key, value in data.items():
            setattr(telemetry, key, value)

        self.db.add(telemetry)
        self.db.flush()
        self.db.refresh(telemetry)
        return telemetry
    