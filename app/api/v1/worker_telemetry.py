from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.worker import WorkerTaskTelemetryCreate, WorkerTaskTelemetryResponse
from app.services.worker_service import WorkerService

router = APIRouter(prefix="/worker/tasks", tags=["Worker Telemetry"])


@router.post("/{task_id}/telemetry", response_model=WorkerTaskTelemetryResponse)
def create_worker_task_telemetry(
    task_id: int,
    payload: WorkerTaskTelemetryCreate,
    db: Session = Depends(get_db),
):
    service = WorkerService(db)
    return service.create_task_telemetry(task_id, payload)
