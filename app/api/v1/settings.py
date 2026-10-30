"""Configurações gerais (admin): ambientes de Git (token por prefixo de URL) e versão dos workers."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.core.database import get_db
from app.models.user import User
from app.schemas.git_environment import (
    GitEnvironmentCreate,
    GitEnvironmentRead,
    GitEnvironmentUpdate,
    GitUrlCheck,
    GitUrlCheckResult,
)
from app.schemas.worker_release import (
    WorkerReleaseOverview,
    WorkerReleaseSettings,
    WorkerUpdateRequest,
    WorkerUpdateResult,
)
from app.services.git_environment_service import GitEnvironmentService
from app.services.worker_release_service import WorkerReleaseService

router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get("/git-environments", response_model=list[GitEnvironmentRead])
def list_git_environments(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return GitEnvironmentService(db).list()


@router.post("/git-environments", response_model=GitEnvironmentRead, status_code=status.HTTP_201_CREATED)
def create_git_environment(payload: GitEnvironmentCreate, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    service = GitEnvironmentService(db)
    return service.to_read(service.create(payload.model_dump(), user_id=getattr(user, "id", None)))


@router.put("/git-environments/{environment_id}", response_model=GitEnvironmentRead)
def update_git_environment(
    environment_id: int, payload: GitEnvironmentUpdate, db: Session = Depends(get_db), user: User = Depends(require_admin)
):
    service = GitEnvironmentService(db)
    return service.to_read(service.update(environment_id, payload.model_dump(), user_id=getattr(user, "id", None)))


@router.delete("/git-environments/{environment_id}")
def delete_git_environment(environment_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    GitEnvironmentService(db).delete(environment_id)
    return {"message": "Ambiente removido."}


@router.post("/git-environments/check-url", response_model=GitUrlCheckResult)
def check_git_url(payload: GitUrlCheck, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Formulário do bot: diz de onde vem o token para esse link (link, ambiente ou nenhum)."""
    return GitEnvironmentService(db).check(payload.url)


@router.get("/workers", response_model=WorkerReleaseOverview)
def get_workers_overview(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """Link do repositório do worker, commit publicado e o commit de cada máquina."""
    return WorkerReleaseService(db).overview()


@router.put("/workers", response_model=WorkerReleaseOverview)
def save_workers_settings(payload: WorkerReleaseSettings, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    service = WorkerReleaseService(db)
    service.set_repo_url(payload.repo_url)
    return service.overview()


@router.post("/workers/check", response_model=WorkerReleaseOverview)
def check_workers_latest(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """Consulta o Git agora e guarda o commit publicado na main."""
    return WorkerReleaseService(db).check_latest()


@router.post("/workers/update", response_model=WorkerUpdateResult)
def request_workers_update(payload: WorkerUpdateRequest, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """Pede atualização: o worker ocioso sai e o launcher baixa o código novo e abre de novo."""
    return WorkerUpdateResult(requested=WorkerReleaseService(db).request_update(payload.runner_ids))


@router.delete("/workers/update/{runner_id}")
def cancel_worker_update(runner_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    WorkerReleaseService(db).cancel_update(runner_id)
    return {"message": "Pedido cancelado."}
