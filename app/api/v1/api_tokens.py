from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.core.database import get_db
from app.core.exceptions import NotFoundException
from app.models.user import User
from app.schemas.api_token import ApiTokenCreate, ApiTokenCreated, ApiTokenRead
from app.services import api_token_service as service

# Tokens do próprio usuário (tela de Perfil / Integração).
router = APIRouter(prefix="/api-tokens", tags=["Tokens de integração"])

# Tokens de outro usuário (tela de Usuários, só admin).
admin_router = APIRouter(prefix="/users", tags=["Tokens de integração"])


@router.get("/", response_model=list[ApiTokenRead])
def list_my_tokens(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Tokens de integração do usuário logado (o valor completo nunca volta)."""
    return [service.to_read(t) for t in service.list_tokens(db, user.id)]


@router.post("/", response_model=ApiTokenCreated, status_code=201)
def create_my_token(payload: ApiTokenCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Gera um token para MCP/IA/scripts. Copie o valor: ele aparece só nesta resposta."""
    token, raw = service.create_token(db, user, payload.name, payload.expires_in_days)
    return {**service.to_read(token), "token": raw}


@router.delete("/{token_id}", response_model=ApiTokenRead)
def revoke_my_token(token_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Revoga o token: ele para de funcionar na hora."""
    return service.to_read(service.revoke_token(db, user.id, token_id))


def _user_or_404(db: Session, user_id: int) -> User:
    target = db.get(User, user_id)
    if target is None:
        raise NotFoundException("Usuário não encontrado.")
    return target


@admin_router.get("/{user_id}/api-tokens", response_model=list[ApiTokenRead])
def list_user_tokens(user_id: int, db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    """Tokens de integração de um usuário (administrador)."""
    _user_or_404(db, user_id)
    return [service.to_read(t) for t in service.list_tokens(db, user_id)]


@admin_router.post("/{user_id}/api-tokens", response_model=ApiTokenCreated, status_code=201)
def create_user_token(
    user_id: int,
    payload: ApiTokenCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Gera um token para outro usuário (administrador). Vale com as permissões desse usuário."""
    target = _user_or_404(db, user_id)
    token, raw = service.create_token(db, target, payload.name, payload.expires_in_days)
    return {**service.to_read(token), "token": raw}


@admin_router.delete("/{user_id}/api-tokens/{token_id}", response_model=ApiTokenRead)
def revoke_user_token(
    user_id: int,
    token_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Revoga um token de outro usuário (administrador)."""
    _user_or_404(db, user_id)
    return service.to_read(service.revoke_token(db, user_id, token_id))
