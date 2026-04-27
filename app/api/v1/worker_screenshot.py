from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.worker import (
    WorkerScreenshotUploadRequest,
    WorkerScreenshotUploadResponse,
)
from app.services.worker_service import WorkerService


router = APIRouter(prefix="/worker/screenshot", tags=["Worker Screenshot"])


@router.post("/", response_model=WorkerScreenshotUploadResponse)
def upload_worker_screenshot(
    payload: WorkerScreenshotUploadRequest,
    db: Session = Depends(get_db),
):
    service = WorkerService(db)
    return service.upload_runner_screenshot(payload)
