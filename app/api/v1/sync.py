"""Tela Sync (out/2026): preferência por usuário, automações escolhidas e health de sistemas externos."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.sync import SyncCheckPayload, SyncCheckRead, SyncPicks, SyncPreference, SyncState
from app.services.sync_service import SyncService

router = APIRouter(prefix="/sync", tags=["Sync"])


def _service(db: Session, user: User) -> SyncService:
    return SyncService(db, user)


@router.put("/preference", response_model=SyncPreference)
def set_preference(payload: SyncPreference, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Cada pessoa liga ou desliga o Sync no próprio perfil."""
    updated = _service(db, user).set_preference(payload.sync_enabled)
    return SyncPreference(sync_enabled=updated.sync_enabled)


@router.get("/state", response_model=SyncState)
def get_state(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _service(db, user).state()


@router.put("/picks", response_model=SyncPicks)
def set_picks(payload: SyncPicks, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return SyncPicks(automation_ids=_service(db, user).set_picks(payload.automation_ids))


@router.post("/checks", response_model=SyncCheckRead, status_code=status.HTTP_201_CREATED)
def create_check(payload: SyncCheckPayload, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _service(db, user).create_check(payload.model_dump())


@router.put("/checks/{check_id}", response_model=SyncCheckRead)
def update_check(check_id: int, payload: SyncCheckPayload, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _service(db, user).update_check(check_id, payload.model_dump())


@router.delete("/checks/{check_id}")
def delete_check(check_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _service(db, user).delete_check(check_id)
    return {"message": "Sistema removido."}


@router.post("/checks/{check_id}/ping", response_model=SyncCheckRead)
def ping_check(check_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Testa o endereço agora. A tela aberta chama isso no intervalo de cada sistema."""
    return _service(db, user).ping(check_id)
