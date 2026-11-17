from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.access_release import AccessReleaseCreate, AccessReleaseRead
from app.services.access_release_service import AccessReleaseService

router = APIRouter(prefix="/access-releases", tags=["Access releases"])


@router.get("/", response_model=list[AccessReleaseRead])
def list_access_releases(db: Session = Depends(get_db)):
    """Histórico das liberações de acesso, da mais nova para a mais antiga."""
    return AccessReleaseService(db).list()


@router.post("/", response_model=AccessReleaseRead, status_code=status.HTTP_201_CREATED)
def create_access_release(
    payload: AccessReleaseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Avisa os robôs que o usuário já está ok (ver LIBERACOES_DE_ACESSO)."""
    item = AccessReleaseService(db).release(
        payload.login, current_user, system=payload.system, note=payload.note
    )
    return {**item, "active": True}
