from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, user_id: int) -> User | None:
        stmt = select(User).where(User.id == user_id)
        return self.db.scalar(stmt)

    def get_by_login(self, login: str) -> User | None:
        stmt = select(User).where(User.login == login)
        return self.db.scalar(stmt)

    def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        return self.db.scalar(stmt)

    def get_by_login_or_email(self, value: str) -> User | None:
        stmt = select(User).where(
            or_(User.login == value, User.email == value)
        )
        return self.db.scalar(stmt)

    def list_all(
        self,
        skip: int = 0,
        limit: int = 100,
        active: bool | None = None,
    ) -> list[User]:
        stmt = select(User).order_by(User.name)

        if active is not None:
            stmt = stmt.where(User.active == active)

        stmt = stmt.offset(skip).limit(limit)
        return list(self.db.scalars(stmt).all())

    def create(self, **data) -> User:
        user = User(**data)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update(self, user: User, **data) -> User:
        for field, value in data.items():
            if value is not None:
                setattr(user, field, value)

        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def soft_delete(self, user: User) -> User:
        user.active = False
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
    