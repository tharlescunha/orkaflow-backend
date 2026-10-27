# app/api/v1/worker_tasks.py

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.env_variable import WorkerTaskEnvResponse
from app.schemas.task import TaskRead
from app.schemas.worker import (
    WorkerTaskActiveListRequest,
    WorkerTaskActiveListResponse,
    WorkerTaskClaimRequest,
    WorkerTaskClaimResponse,
    WorkerCredentialAlertRequest,
    WorkerCredentialAlertResponse,
    WorkerTaskFinishRequest,
    WorkerTaskNextRequest,
    WorkerTaskAttachmentCreate,
    WorkerTaskAttachmentResponse,
    WorkerTaskProgressRequest,
    WorkerTaskProgressResponse,
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


@router.post("/{task_id}/env", response_model=WorkerTaskEnvResponse)
def get_task_env(
    task_id: int,
    payload: WorkerTaskStatusCheckRequest,
    db: Session = Depends(get_db),
):
    """Variáveis de ambiente finais da task (herança aplicada) para o worker injetar no robô."""
    service = WorkerService(db)
    return service.resolve_task_env(task_id, payload)


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


@router.post("/{task_id}/progress", response_model=WorkerTaskProgressResponse)
def update_task_progress(task_id: int, payload: WorkerTaskProgressRequest, db: Session = Depends(get_db)):
    """Etapa atual do robô (maestro.step): aparece na lista e no detalhe da task."""
    service = WorkerService(db)
    return service.update_task_progress(task_id, payload)


@router.post("/{task_id}/attachments", response_model=WorkerTaskAttachmentResponse)
def create_task_attachment(task_id: int, payload: WorkerTaskAttachmentCreate, db: Session = Depends(get_db)):
    """Arquivo anexado pelo robô (maestro.attach): aparece no detalhe da task para download."""
    service = WorkerService(db)
    return service.create_task_attachment(task_id, payload)


@router.post("/{task_id}/credential-alert", response_model=WorkerCredentialAlertResponse)
def report_credential_alert(task_id: int, payload: WorkerCredentialAlertRequest, db: Session = Depends(get_db)):
    """Robô avisou que a credencial não serve mais (senha expirada, incorreta ou usuário bloqueado)."""
    service = WorkerService(db)
    return service.report_credential_alert(task_id, payload)
