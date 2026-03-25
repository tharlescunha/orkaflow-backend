# app\repositories\repository_repository.py

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.repository import Repository


class RepositoryRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, repository_id: int) -> Repository | None:
        stmt = select(Repository).where(Repository.id == repository_id)
        return self.db.scalar(stmt)

    def get_by_name(self, name: str) -> Repository | None:
        stmt = select(Repository).where(Repository.name == name)
        return self.db.scalar(stmt)

    def list_all(
        self,
        skip: int = 0,
        limit: int = 100,
        active: bool | None = None,
    ) -> list[Repository]:
        stmt = select(Repository).order_by(Repository.name)

        if active is not None:
            stmt = stmt.where(Repository.active == active)

        stmt = stmt.offset(skip).limit(limit)
        return list(self.db.scalars(stmt).all())

    def create(self, **data) -> Repository:
        repository = Repository(**data)
        self.db.add(repository)
        self.db.commit()
        self.db.refresh(repository)
        return repository

    def update(self, repository: Repository, **data) -> Repository:
        for field, value in data.items():
            if value is not None:
                setattr(repository, field, value)

        self.db.add(repository)
        self.db.commit()
        self.db.refresh(repository)
        return repository

    def soft_delete(self, repository: Repository) -> Repository:
        repository.active = False
        self.db.add(repository)
        self.db.commit()
        self.db.refresh(repository)
        return repository
    