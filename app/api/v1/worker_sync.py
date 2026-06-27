from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.worker import WorkerSyncRequest, WorkerSyncResponse
from app.schemas.bot_version import BotVersionResponse
from app.services.worker_service import WorkerService
from app.services.bot_version_service import BotVersionService

router = APIRouter(prefix="/worker", tags=["Worker Sync"])


@router.post("/sync", response_model=WorkerSyncResponse)
def sync_worker(
    payload: WorkerSyncRequest,
    db: Session = Depends(get_db),
):
    service = WorkerService(db)
    return service.sync_runner(payload)


class WorkerAutoVersionRequest(BaseModel):
    uuid: str
    token: str
    bot_id: int
    commit_hash: str
    branch: str | None = None


@router.post("/bot-versions/auto", response_model=BotVersionResponse)
def auto_create_bot_version(
    payload: WorkerAutoVersionRequest,
    db: Session = Depends(get_db),
):
    worker_service = WorkerService(db)
    try:
        worker_service._authenticate_runner(payload.uuid, payload.token)
    except Exception:
        raise HTTPException(status_code=401, detail="Runner não autorizado.")

    version_service = BotVersionService(db)
    return version_service.auto_create(
        bot_id=payload.bot_id,
        commit_hash=payload.commit_hash,
        branch=payload.branch,
    )
