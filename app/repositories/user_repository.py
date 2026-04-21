from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.user import User
from app.models.access_control import Profile


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, user_id: int) -> User | None:
        stmt = (
            select(User)
            .options(
                selectinload(User.profile).selectinload(Profile.permissions),
            )
            .where(User.id == user_id)
        )
        return self.db.scalar(stmt)

    def get_by_login(self, login: str) -> User | None:
        stmt = (
            select(User)
            .options(
                selectinload(User.profile).selectinload(Profile.permissions),
            )
            .where(User.login == login)
        )
        return self.db.scalar(stmt)

    def get_by_email(self, email: str) -> User | None:
        stmt = (
            select(User)
            .options(
                selectinload(User.profile).selectinload(Profile.permissions),
            )
            .where(User.email == email)
        )
        return self.db.scalar(stmt)

    def get_by_login_or_email(self, value: str) -> User | None:
        stmt = (
            select(User)
            .options(
                selectinload(User.profile).selectinload(Profile.permissions),
            )
            .where(
                or_(
                    User.login == value,
                    User.email == value,
                )
            )
        )
        return self.db.scalar(stmt)

    def list_all(
        self,
        skip: int = 0,
        limit: int = 100,
        active: bool | None = None,
        profile_id: int | None = None,
        search: str | None = None,
    ) -> list[User]:
        stmt = (
            select(User)
            .options(
                selectinload(User.profile).selectinload(Profile.permissions),
            )
            .order_by(User.name)
        )

        if active is not None:
            stmt = stmt.where(User.active == active)

        if profile_id is not None:
            stmt = stmt.where(User.profile_id == profile_id)

        if search:
            like_term = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    User.name.ilike(like_term),
                    User.login.ilike(like_term),
                    User.email.ilike(like_term),
                )
            )

        stmt = stmt.offset(skip).limit(limit)
        return list(self.db.scalars(stmt).all())

    def create(self, **data) -> User:
        user = User(**data)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return self.get_by_id(user.id) or user

    def update(self, user: User, **data) -> User:
        for field, value in data.items():
            if value is not None:
                setattr(user, field, value)

        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return self.get_by_id(user.id) or user

    def set_active(self, user: User, active: bool) -> User:
        user.active = active
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return self.get_by_id(user.id) or user

    def soft_delete(self, user: User) -> User:
        return self.set_active(user, False)
    