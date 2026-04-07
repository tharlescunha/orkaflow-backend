from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.worker import (
    WorkerCredentialResolveRequest,
    WorkerCredentialResolveResponse,
)
from app.services.worker_service import WorkerService

router = APIRouter(prefix="/worker/credentials", tags=["Worker Credentials"])


@router.post(
    "/{credential_id}/resolve",
    response_model=WorkerCredentialResolveResponse,
)
def resolve_worker_credential(
    credential_id: int,
    payload: WorkerCredentialResolveRequest,
    db: Session = Depends(get_db),
):
    service = WorkerService(db)
    return service.resolve_credential_for_runner(credential_id, payload)
