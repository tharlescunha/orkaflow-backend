from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictException, NotFoundException
from app.core.security import get_password_hash
from app.models.access_control import Profile
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserChangeStatus, UserCreate, UserUpdate


class UserService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = UserRepository(db)

    def _get_profile_or_none(self, profile_id: int | None) -> Profile | None:
        if profile_id is None:
            return None

        profile = self.db.get(Profile, profile_id)
        if not profile:
            raise NotFoundException("Perfil não encontrado.")

        return profile

    def create(self, data: UserCreate):
        existing_login = self.repo.get_by_login(data.login)
        if existing_login:
            raise ConflictException("Já existe um usuário com esse login.")

        existing_email = self.repo.get_by_email(data.email)
        if existing_email:
            raise ConflictException("Já existe um usuário com esse e-mail.")

        self._get_profile_or_none(data.profile_id)

        user_data = data.model_dump()
        password = user_data.pop("password")
        user_data["password_hash"] = get_password_hash(password)

        return self.repo.create(**user_data)

    def list(
        self,
        skip: int = 0,
        limit: int = 100,
        active: bool | None = None,
        profile_id: int | None = None,
        search: str | None = None,
    ):
        if profile_id is not None:
            self._get_profile_or_none(profile_id)

        return self.repo.list_all(
            skip=skip,
            limit=limit,
            active=active,
            profile_id=profile_id,
            search=search,
        )

    def get(self, user_id: int):
        user = self.repo.get_by_id(user_id)
        if not user:
            raise NotFoundException("Usuário não encontrado.")
        return user

    def update(self, user_id: int, data: UserUpdate):
        user = self.get(user_id)
        update_data = data.model_dump(exclude_unset=True)

        if "login" in update_data and update_data["login"] != user.login:
            existing_login = self.repo.get_by_login(update_data["login"])
            if existing_login:
                raise ConflictException("Já existe um usuário com esse login.")

        if "email" in update_data and update_data["email"] != user.email:
            existing_email = self.repo.get_by_email(update_data["email"])
            if existing_email:
                raise ConflictException("Já existe um usuário com esse e-mail.")

        if "profile_id" in update_data:
            self._get_profile_or_none(update_data["profile_id"])

        if "password" in update_data:
            password = update_data.pop("password")
            update_data["password_hash"] = get_password_hash(password)

        return self.repo.update(user, **update_data)

    def change_status(self, user_id: int, data: UserChangeStatus):
        user = self.get(user_id)
        return self.repo.set_active(user, data.active)

    def block(self, user_id: int):
        user = self.get(user_id)
        return self.repo.set_active(user, False)

    def unblock(self, user_id: int):
        user = self.get(user_id)
        return self.repo.set_active(user, True)

    def delete(self, user_id: int):
        user = self.get(user_id)
        return self.repo.soft_delete(user)
    