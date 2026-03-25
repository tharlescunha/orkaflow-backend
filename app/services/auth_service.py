from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenException, NotFoundException, UnauthorizedException
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.repositories.user_repository import UserRepository


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)

    def login(self, login: str, password: str):
        user = self.user_repo.get_by_login_or_email(login)
        if not user:
            raise UnauthorizedException("Login ou senha inválidos.")

        if not user.active:
            raise ForbiddenException("Usuário inativo.")

        if not verify_password(password, user.password_hash):
            raise UnauthorizedException("Login ou senha inválidos.")

        access_token = create_access_token(
            subject=user.id,
            extra_data={"role": user.role, "login": user.login},
        )
        refresh_token = create_refresh_token(subject=user.id)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }

    def refresh_token(self, refresh_token: str):
        payload = decode_token(refresh_token)

        if payload.get("type") != "refresh":
            raise UnauthorizedException("Token de refresh inválido.")

        user_id = payload.get("sub")
        if not user_id:
            raise UnauthorizedException("Token inválido.")

        user = self.user_repo.get_by_id(int(user_id))
        if not user:
            #raise NotFoundException("Usuário não encontrado.")
            raise Exception("Bot não encontrado")

        if not user.active:
            raise ForbiddenException("Usuário inativo.")

        access_token = create_access_token(
            subject=user.id,
            extra_data={"role": user.role, "login": user.login},
        )
        new_refresh_token = create_refresh_token(subject=user.id)

        return {
            "access_token": access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
        }

    def get_me(self, user_id: int):
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise Exception("Bot não encontrado")
            #raise NotFoundException("Usuário não encontrado.")

        if not user.active:
            raise ForbiddenException("Usuário inativo.")

        return user
    