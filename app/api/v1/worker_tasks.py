# app/api/v1/worker_tasks.py

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.task import TaskRead
from app.schemas.worker import (
    WorkerTaskActiveListRequest,
    WorkerTaskActiveListResponse,
    WorkerTaskClaimRequest,
    WorkerTaskClaimResponse,
    WorkerTaskFinishRequest,
    WorkerTaskNextRequest,
    WorkerTaskNextResponse,
    WorkerTaskReleaseStartupLocksRequest,
    WorkerTaskReleaseStartupLocksResponse,
    WorkerTaskStatusCheckRequest,
    WorkerTaskStatusCheckResponse,
    WorkerTaskStatusUpdateRequest,
)
from app.services.worker_service import WorkerService

router = APIRouter(prefix="/worker/tasks", tags=["Worker Tasks"])


@router.post("/next", response_model=WorkerTaskNextResponse)
def get_next_task(payload: WorkerTaskNextRequest, db: Session = Depends(get_db)):
    service = WorkerService(db)
    return service.get_next_task(payload)


@router.post("/active", response_model=WorkerTaskActiveListResponse)
def list_active_tasks(payload: WorkerTaskActiveListRequest, db: Session = Depends(get_db)):
    service = WorkerService(db)
    return service.list_active_tasks(payload)


@router.post("/release-startup-locks", response_model=WorkerTaskReleaseStartupLocksResponse)
def release_startup_locks(
    payload: WorkerTaskReleaseStartupLocksRequest,
    db: Session = Depends(get_db),
):
    service = WorkerService(db)
    return service.release_startup_locks(payload)


@router.post("/{task_id}/claim", response_model=WorkerTaskClaimResponse)
def claim_task(task_id: int, payload: WorkerTaskClaimRequest, db: Session = Depends(get_db)):
    service = WorkerService(db)
    return service.claim_task(task_id, payload)


@router.post("/{task_id}/status", response_model=WorkerTaskStatusCheckResponse)
def check_task_status(
    task_id: int,
    payload: WorkerTaskStatusCheckRequest,
    db: Session = Depends(get_db),
):
    service = WorkerService(db)
    return service.check_task_status(task_id, payload)


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
