from __future__ import annotations

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.core.security import decode_token
from app.models.user import User
from app.repositories.user_repository import UserRepository


bearer_scheme = HTTPBearer(
    auto_error=True,
    bearerFormat="JWT",
    description="Informe o token no header Authorization no formato: Bearer <seu_access_token>",
)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials

    try:
        payload = decode_token(token)
    except ValueError as exc:
        raise UnauthorizedException(str(exc)) from exc

    if payload.get("type") != "access":
        raise UnauthorizedException("Token de acesso inválido.")

    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedException("Token inválido.")

    user = UserRepository(db).get_by_id(int(user_id))
    if not user:
        raise UnauthorizedException("Usuário não encontrado.")

    if not user.active:
        raise ForbiddenException("Usuário inativo.")

    if user.profile_id is not None and user.profile and not user.profile.active:
        raise ForbiddenException("O perfil vinculado ao usuário está inativo.")

    return user


def _is_legacy_admin(user: User) -> bool:
    role_value = getattr(user, "role", None)

    if role_value is None:
        return False

    if hasattr(role_value, "value"):
        role_value = role_value.value

    return str(role_value).lower() == "admin"


def _user_has_permission(user: User, module: str, action: str) -> bool:
    if _is_legacy_admin(user):
        return True

    if not user.profile or not user.profile.active:
        return False

    normalized_module = module.strip().lower()
    normalized_action = action.strip().lower()

    for permission in user.profile.permissions or []:
        permission_module = (permission.module or "").strip().lower()
        permission_action = (permission.action or "").strip().lower()

        if permission_module == normalized_module and permission_action == normalized_action:
            return True

    return False


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if _is_legacy_admin(current_user):
        return current_user

    if _user_has_permission(current_user, "users", "admin"):
        return current_user

    raise ForbiddenException("Acesso permitido apenas para administradores.")


def require_permission(module: str, action: str):
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if _user_has_permission(current_user, module, action):
            return current_user

        raise ForbiddenException(
            f"Você não possui permissão para executar '{action}' no módulo '{module}'."
        )

    return dependency
