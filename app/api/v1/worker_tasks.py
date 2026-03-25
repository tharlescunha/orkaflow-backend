# app/api/v1/worker_tasks.py

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.task import TaskRead
from app.schemas.worker import (
    WorkerTaskClaimRequest,
    WorkerTaskClaimResponse,
    WorkerTaskFinishRequest,
    WorkerTaskNextRequest,
    WorkerTaskNextResponse,
    WorkerTaskStatusUpdateRequest,
)
from app.services.worker_service import WorkerService

router = APIRouter(prefix="/worker/tasks", tags=["Worker Tasks"])


@router.post("/next", response_model=WorkerTaskNextResponse)
def get_next_task(payload: WorkerTaskNextRequest, db: Session = Depends(get_db)):
    service = WorkerService(db)
    return service.get_next_task(payload)


@router.post("/{task_id}/claim", response_model=WorkerTaskClaimResponse)
def claim_task(task_id: int, payload: WorkerTaskClaimRequest, db: Session = Depends(get_db)):
    service = WorkerService(db)
    return service.claim_task(task_id, payload)


@router.patch("/{task_id}/status", response_model=TaskRead)
def update_task_status(
    task_id: int,
    payload: WorkerTaskStatusUpdateRequest,
    db: Session = Depends(get_db),
):
    service = WorkerService(db)
    return service.update_task_status(task_id, payload)


@router.post("/{task_id}/finish", response_model=TaskRead)
def finish_task(
    task_id: int,
    payload: WorkerTaskFinishRequest,
    db: Session = Depends(get_db),
):
    service = WorkerService(db)
    return service.finish_task(task_id, payload)
