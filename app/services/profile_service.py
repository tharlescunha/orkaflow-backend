from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictException, NotFoundException
from app.models.access_control import Permission, Profile
from app.repositories.profile_repository import ProfileRepository
from app.schemas.profile import ProfileCreate, ProfileUpdate


class ProfileService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ProfileRepository(db)

    def _validate_permissions(self, permission_ids: list[int]) -> None:
        if not permission_ids:
            return

        permissions = self.repo.get_permissions_by_ids(permission_ids)

        if len(permissions) != len(set(permission_ids)):
            raise NotFoundException("Uma ou mais permissões não existem.")

    def create(self, data: ProfileCreate) -> Profile:
        existing = self.repo.get_by_name(data.name)
        if existing:
            raise ConflictException("Já existe um perfil com esse nome.")

        self._validate_permissions(data.permission_ids)

        payload = data.model_dump()

        return self.repo.create(**payload)

    def list(
        self,
        skip: int = 0,
        limit: int = 100,
        active: bool | None = None,
    ) -> list[Profile]:
        return self.repo.list_all(skip=skip, limit=limit, active=active)

    def get(self, profile_id: int) -> Profile:
        profile = self.repo.get_by_id(profile_id)
        if not profile:
            raise NotFoundException("Perfil não encontrado.")
        return profile

    def update(self, profile_id: int, data: ProfileUpdate) -> Profile:
        profile = self.get(profile_id)

        update_data = data.model_dump(exclude_unset=True)

        if "name" in update_data and update_data["name"] != profile.name:
            existing = self.repo.get_by_name(update_data["name"])
            if existing:
                raise ConflictException("Já existe um perfil com esse nome.")

        if "permission_ids" in update_data:
            self._validate_permissions(update_data["permission_ids"])

        return self.repo.update(profile, **update_data)

    def activate(self, profile_id: int) -> Profile:
        profile = self.get(profile_id)
        return self.repo.set_active(profile, True)

    def deactivate(self, profile_id: int) -> Profile:
        profile = self.get(profile_id)
        return self.repo.set_active(profile, False)
    