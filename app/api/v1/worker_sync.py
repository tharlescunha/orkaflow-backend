from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.worker import WorkerSyncRequest, WorkerSyncResponse
from app.services.worker_service import WorkerService

router = APIRouter(prefix="/worker", tags=["Worker Sync"])


@router.post("/sync", response_model=WorkerSyncResponse)
def sync_worker(
    payload: WorkerSyncRequest,
    db: Session = Depends(get_db),
):
    service = WorkerService(db)
    return service.sync_runner(payload)
