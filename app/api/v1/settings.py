"""Configurações gerais (admin). Por enquanto: ambientes de Git (token por prefixo de URL)."""
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
from app.services.git_environment_service import GitEnvironmentService

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
