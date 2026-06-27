# app/api/v1/worker_auth.py

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.worker import WorkerAuthRequest, WorkerAuthResponse
from app.services.worker_service import WorkerService

router = APIRouter(prefix="/worker/auth", tags=["Worker Auth"])


@router.post("/login", response_model=WorkerAuthResponse)
def worker_login(payload: WorkerAuthRequest, db: Session = Depends(get_db)):
    service = WorkerService(db)
    return service.authenticate(payload)
