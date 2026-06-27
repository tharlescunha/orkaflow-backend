from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.schemas.auth import (
    LoginRequest,
    MeResponse,
    RefreshTokenRequest,
    TokenResponse,
)
from app.schemas.common import MessageResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
):
    service = AuthService(db)
    return service.login(payload.login, payload.password)


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(
    payload: RefreshTokenRequest,
    db: Session = Depends(get_db),
):
    service = AuthService(db)
    return service.refresh_token(payload.refresh_token)


@router.get("/me", response_model=MeResponse)
def me(current_user=Depends(get_current_user)):
    return current_user


@router.post("/logout", response_model=MessageResponse)
def logout():
    return {"message": "Logout lógico realizado com sucesso."}
