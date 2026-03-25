from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.worker import WorkerTaskErrorCreate, WorkerTaskErrorResponse
from app.services.worker_service import WorkerService

router = APIRouter(prefix="/worker/tasks", tags=["Worker Errors"])


@router.post("/{task_id}/errors", response_model=WorkerTaskErrorResponse)
def create_worker_task_error(
    task_id: int,
    payload: WorkerTaskErrorCreate,
    db: Session = Depends(get_db),
):
    service = WorkerService(db)
    return service.create_task_error(task_id, payload)
