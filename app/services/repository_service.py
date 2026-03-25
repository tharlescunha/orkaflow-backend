# app\services\repository_service.py

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictException, NotFoundException
from app.repositories.repository_repository import RepositoryRepository
from app.schemas.repository import RepositoryCreate, RepositoryUpdate


class RepositoryService:
    def __init__(self, db: Session):
        self.repo = RepositoryRepository(db)

    def create(self, data: RepositoryCreate):
        existing = self.repo.get_by_name(data.name)
        if existing:
            raise ConflictException("Já existe um repositório com esse nome.")

        return self.repo.create(**data.model_dump())

    def list(self, skip: int = 0, limit: int = 100, active: bool | None = None):
        return self.repo.list_all(skip=skip, limit=limit, active=active)

    def get(self, repository_id: int):
        repository = self.repo.get_by_id(repository_id)
        if not repository:
            raise NotFoundException("Repositório não encontrado.")
        return repository

    def update(self, repository_id: int, data: RepositoryUpdate):
        repository = self.get(repository_id)

        update_data = data.model_dump(exclude_unset=True)

        if "name" in update_data and update_data["name"] != repository.name:
            existing = self.repo.get_by_name(update_data["name"])
            if existing:
                raise ConflictException("Já existe um repositório com esse nome.")

        return self.repo.update(repository, **update_data)

    def delete(self, repository_id: int):
        repository = self.get(repository_id)
        return self.repo.soft_delete(repository)