# app/api/v1/worker_registration.py

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.worker import WorkerRegisterRequest, WorkerRegisterResponse
from app.services.worker_service import WorkerService

router = APIRouter(prefix="/worker/registration", tags=["Worker Registration"])


@router.post("/", response_model=WorkerRegisterResponse)
def register_worker(payload: WorkerRegisterRequest, db: Session = Depends(get_db)):
    service = WorkerService(db)
    return service.register_runner(payload)
