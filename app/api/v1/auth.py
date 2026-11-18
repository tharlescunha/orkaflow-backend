from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.schemas.auth import (
    AuthConfigRead,
    LoginRequest,
    MeResponse,
    MicrosoftLoginRequest,
    RefreshTokenRequest,
    TokenResponse,
)
from app.schemas.common import MessageResponse
from app.services.auth_service import AuthService
from app.services.microsoft_sso_service import MicrosoftSsoService

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
):
    service = AuthService(db)
    return service.login(payload.login, payload.password)


@router.get("/config", response_model=AuthConfigRead)
def auth_config(db: Session = Depends(get_db)):
    """O que a tela de entrada precisa saber: se o login com a conta Microsoft está ligado (só identificadores públicos)."""
    return {"microsoft": MicrosoftSsoService(db).public_config()}


@router.post("/microsoft", response_model=TokenResponse)
def login_with_microsoft(
    payload: MicrosoftLoginRequest,
    db: Session = Depends(get_db),
):
    """Troca o id_token da Microsoft (já validado aqui: assinatura, cliente, locatário, validade e nonce) pelos tokens do Regente."""
    return MicrosoftSsoService(db).login(payload.id_token, payload.nonce)


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
