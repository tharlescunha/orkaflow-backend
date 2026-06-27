from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.worker import (
    WorkerRuntimeEventCreate,
    WorkerRuntimeEventResponse,
)
from app.services.worker_service import WorkerService

router = APIRouter(
    prefix="/worker/runtime-events",
    tags=["Worker Runtime Events"],
)


@router.post("/", response_model=WorkerRuntimeEventResponse)
def create_worker_runtime_event(
    payload: WorkerRuntimeEventCreate,
    db: Session = Depends(get_db),
):
    service = WorkerService(db)
    return service.create_runtime_event(payload)
