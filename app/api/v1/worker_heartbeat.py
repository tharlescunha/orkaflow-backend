# app/api/v1/worker_heartbeat.py

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.worker import WorkerHeartbeatRequest, WorkerHeartbeatResponse
from app.services.worker_service import WorkerService

router = APIRouter(prefix="/worker/heartbeat", tags=["Worker Heartbeat"])


@router.post("/", response_model=WorkerHeartbeatResponse)
def worker_heartbeat(payload: WorkerHeartbeatRequest, db: Session = Depends(get_db)):
    service = WorkerService(db)
    return service.heartbeat(payload)
