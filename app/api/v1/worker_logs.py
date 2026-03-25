from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.worker import WorkerTaskLogCreate, WorkerTaskLogResponse
from app.services.worker_service import WorkerService

router = APIRouter(prefix="/worker/tasks", tags=["Worker Logs"])


@router.post("/{task_id}/logs", response_model=WorkerTaskLogResponse)
def create_worker_task_log(
    task_id: int,
    payload: WorkerTaskLogCreate,
    db: Session = Depends(get_db),
):
    service = WorkerService(db)
    return service.create_task_log(task_id, payload)
