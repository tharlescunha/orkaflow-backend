from sqlalchemy.orm import Session

from app.core.exceptions import ConflictException, NotFoundException
from app.core.security import get_password_hash
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate, UserUpdate

class UserService:
    def __init__(self, db: Session):
        self.repo = UserRepository(db)

    def create(self, data: UserCreate):
        existing_login = self.repo.get_by_login(data.login)
        if existing_login:
            raise ConflictException("Já existe um usuário com esse login.")

        existing_email = self.repo.get_by_email(data.email)
        if existing_email:
            raise ConflictException("Já existe um usuário com esse e-mail.")

        user_data = data.model_dump()
        password = user_data.pop("password")
        user_data["password_hash"] = get_password_hash(password)

        return self.repo.create(**user_data)

    def list(self, skip: int = 0, limit: int = 100, active: bool | None = None):
        return self.repo.list_all(skip=skip, limit=limit, active=active)

    def get(self, user_id: int):
        user = self.repo.get_by_id(user_id)
        if not user:
            raise Exception("Bot não encontrado")
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

        if "password" in update_data:
            password = update_data.pop("password")
            update_data["password_hash"] = get_password_hash(password)

        return self.repo.update(user, **update_data)

    def delete(self, user_id: int):
        user = self.get(user_id)
        return self.repo.soft_delete(user)
    