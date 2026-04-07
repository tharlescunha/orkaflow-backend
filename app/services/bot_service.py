from sqlalchemy.orm import Session

from app.core.exceptions import ConflictException, NotFoundException
from app.models.repository import Repository
from app.repositories.bot_repository import BotRepository

from app.models.bot import Bot
from app.models.bot_version import BotVersion
from app.models.user import User

from app.repositories.bot_version_repository import BotVersionRepository



class BotService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = BotRepository

    def _serialize_bot(self, bot, latest_versions: dict[int, str] | None = None):
        latest_versions = latest_versions or {}

        technology = bot.technology.value if hasattr(bot.technology, "value") else bot.technology
        source_type = bot.source_type.value if hasattr(bot.source_type, "value") else bot.source_type

        effective_current_version = (
            latest_versions.get(bot.id)
            or bot.current_version
            or bot.release_version
        )

        return {
            "id": bot.id,
            "name": bot.name,
            "description": bot.description,
            "technology": technology,
            "repository_id": bot.repository_id,
            "repository_name": bot.repository.name if bot.repository else None,
            "source_type": source_type,
            "source_url": bot.source_url,
            "entrypoint": bot.entrypoint,
            "requirements_file": bot.requirements_file,
            "timeout_default": bot.timeout_default,
            "active": bot.active,
            "current_version": effective_current_version,
            "release_version": bot.release_version,
            "created_at": bot.created_at,
            "updated_at": bot.updated_at,
        }

    def list(
        self,
        *,
        skip: int = 0,
        limit: int = 10,
        search: str | None = None,
        repository_id: int | None = None,
        active: bool | None = None,
    ):
        bots, total = self.repo.list_paginated(
            self.db,
            skip=skip,
            limit=limit,
            search=search,
            repository_id=repository_id,
            active=active,
        )

        latest_versions = self.repo.get_latest_versions_map(
            self.db,
            [bot.id for bot in bots],
        )

        items = [
            {
                "id": bot.id,
                "name": bot.name,
                "description": bot.description,
                "repository_id": bot.repository_id,
                "repository_name": bot.repository.name if bot.repository else None,
                "current_version": latest_versions.get(bot.id) or bot.current_version or bot.release_version,
                "release_version": bot.release_version,
                "active": bot.active,
                "created_at": bot.created_at,
            }
            for bot in bots
        ]

        return {
            "items": items,
            "total": total,
        }

    def get(self, bot_id: int):
        bot = self.repo.get_by_id(self.db, bot_id)
        if not bot:
            raise NotFoundException("Bot não encontrado.")

        latest_versions = self.repo.get_latest_versions_map(self.db, [bot.id])
        return self._serialize_bot(bot, latest_versions)

    def create(self, data: dict):
        initial_version = data.pop("initial_version")
        created_by = data.pop("created_by", None)

        existing_repository = (
            self.db.query(Repository)
            .filter(Repository.id == data["repository_id"])
            .first()
        )
        if not existing_repository:
            raise NotFoundException("Repositório não encontrado.")

        if created_by is None:
            raise NotFoundException("Usuário criador não informado.")

        user = self.db.query(User).filter(User.id == created_by).first()
        if not user:
            raise NotFoundException("Usuário criador não encontrado.")

        existing_bot = (
            self.db.query(Bot)
            .filter(
                Bot.repository_id == data["repository_id"],
                Bot.name == data["name"],
            )
            .first()
        )
        if existing_bot:
            raise ConflictException("Já existe um bot com esse nome nesse repositório.")

        try:
            bot = Bot(**data)
            bot.current_version = initial_version

            self.db.add(bot)
            self.db.flush()

            bot_version = BotVersion(
                bot_id=bot.id,
                version=initial_version,
                storage_type="local",
                artifact_path=bot.source_url,
                changelog="Versão inicial do bot",
                checksum=None,
                is_active=True,
                created_by=created_by,
            )

            self.db.add(bot_version)
            self.db.commit()
            self.db.refresh(bot)

            return bot

        except Exception:
            self.db.rollback()
            raise

    def update(self, bot_id: int, data: dict):
        bot = self.repo.get_by_id(self.db, bot_id)
        if not bot:
            raise NotFoundException("Bot não encontrado.")

        if data.get("repository_id") is not None:
            repository = (
                self.db.query(Repository)
                .filter(Repository.id == data["repository_id"])
                .first()
            )
            if not repository:
                raise NotFoundException("Repositório não encontrado.")

        if "release_version" in data:
            has_versions = self.repo.has_versions(self.db, bot.id)
            if not has_versions:
                data["current_version"] = data["release_version"]

        updated_bot = self.repo.update(self.db, bot, data)
        updated_bot = self.repo.get_by_id(self.db, updated_bot.id)

        latest_versions = self.repo.get_latest_versions_map(self.db, [updated_bot.id])
        return self._serialize_bot(updated_bot, latest_versions)

    def delete(self, bot_id: int):
        bot = self.repo.get_by_id(self.db, bot_id)
        if not bot:
            raise NotFoundException("Bot não encontrado.")

        self.repo.delete(self.db, bot)
        