# app\services\repository_service.py

from sqlalchemy import select
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictException, NotFoundException
from app.models.automation import Automation
from app.models.bot import Bot
from app.models.automation import Automation
from app.models.bot import Bot
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

        turning_off = update_data.get("active") is False and bool(repository.active)
        updated = self.repo.update(repository, **update_data)
        if turning_off:
            self._deactivate_children(updated)
        return updated

    def delete(self, repository_id: int):
        repository = self.get(repository_id)
        repository = self.repo.soft_delete(repository)
        self._deactivate_children(repository)
        return repository

    def _deactivate_children(self, repository) -> dict:
        """Desativar o repositório desativa os bots e as automações dele (out/2026).

        Assim nada do repositório segue rodando ou sendo sincronizado nas máquinas. Reativar o
        repositório NÃO reativa os bots/automações: isso é decidido um a um na tela."""
        db = self.repo.db
        bots = list(db.scalars(select(Bot).where(Bot.repository_id == repository.id, Bot.active == True)))  # noqa: E712
        automations = list(
            db.scalars(select(Automation).where(Automation.repository_id == repository.id, Automation.active == True))  # noqa: E712
        )
        for bot in bots:
            bot.active = False
            db.add(bot)
        for automation in automations:
            automation.active = False
            db.add(automation)
        if bots or automations:
            db.commit()
        return {"bots": len(bots), "automations": len(automations)}