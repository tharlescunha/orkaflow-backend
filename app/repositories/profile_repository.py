from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.access_control import Permission, Profile


class ProfileRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, profile_id: int) -> Profile | None:
        stmt = (
            select(Profile)
            .options(selectinload(Profile.permissions))
            .where(Profile.id == profile_id)
        )
        return self.db.scalar(stmt)

    def get_by_name(self, name: str) -> Profile | None:
        stmt = (
            select(Profile)
            .options(selectinload(Profile.permissions))
            .where(Profile.name == name)
        )
        return self.db.scalar(stmt)

    def list_all(
        self,
        skip: int = 0,
        limit: int = 100,
        active: bool | None = None,
    ) -> list[Profile]:
        stmt = (
            select(Profile)
            .options(selectinload(Profile.permissions))
            .order_by(Profile.name)
        )

        if active is not None:
            stmt = stmt.where(Profile.active == active)

        stmt = stmt.offset(skip).limit(limit)
        return list(self.db.scalars(stmt).all())

    def get_permissions_by_ids(self, permission_ids: list[int]) -> list[Permission]:
        if not permission_ids:
            return []

        stmt = select(Permission).where(Permission.id.in_(permission_ids))
        return list(self.db.scalars(stmt).all())

    def create(self, **data) -> Profile:
        permissions_ids = data.pop("permission_ids", [])

        profile = Profile(**data)

        if permissions_ids:
            permissions = self.get_permissions_by_ids(permissions_ids)
            profile.permissions = permissions

        self.db.add(profile)
        self.db.commit()
        self.db.refresh(profile)

        return self.get_by_id(profile.id) or profile

    def update(self, profile: Profile, **data) -> Profile:
        permissions_ids = data.pop("permission_ids", None)

        for field, value in data.items():
            if value is not None:
                setattr(profile, field, value)

        if permissions_ids is not None:
            permissions = self.get_permissions_by_ids(permissions_ids)
            profile.permissions = permissions

        self.db.add(profile)
        self.db.commit()
        self.db.refresh(profile)

        return self.get_by_id(profile.id) or profile

    def set_active(self, profile: Profile, active: bool) -> Profile:
        profile.active = active
        self.db.add(profile)
        self.db.commit()
        self.db.refresh(profile)
        return self.get_by_id(profile.id) or profile
    