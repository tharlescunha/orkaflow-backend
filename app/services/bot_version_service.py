from sqlalchemy.orm import Session

from app.core.exceptions import ConflictException, NotFoundException
from app.models.bot import Bot
from app.models.user import User
from app.repositories.bot_version_repository import BotVersionRepository


class BotVersionService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = BotVersionRepository

    def list(self):
        return self.repo.get_all(self.db)

    def get(self, bot_version_id: int):
        bot_version = self.repo.get_by_id(self.db, bot_version_id)
        if not bot_version:
            raise NotFoundException("Versão do bot não encontrada.")
        return bot_version

    def create(self, data: dict):
        bot = self.db.query(Bot).filter(Bot.id == data["bot_id"]).first()
        if not bot:
            raise NotFoundException("Bot não encontrado.")

        if not bot.active:
            raise ConflictException("Não é permitido criar versão para bot inativo.")

        existing = self.repo.get_by_bot_and_version(
            self.db,
            bot_id=data["bot_id"],
            version=data["version"],
        )
        if existing:
            raise ConflictException("Já existe uma versão com esse número para esse bot.")

        if not data.get("created_by"):
            data["created_by"] = 1

        user = self.db.query(User).filter(User.id == data["created_by"]).first()
        if not user:
            raise NotFoundException("Usuário criador não encontrado.")

        return self.repo.create(self.db, data)

    def update(self, bot_version_id: int, data: dict):
        bot_version = self.get(bot_version_id)

        if data.get("created_by"):
            user = self.db.query(User).filter(User.id == data["created_by"]).first()
            if not user:
                raise NotFoundException("Usuário criador não encontrado.")

        new_version = data.get("version")
        if new_version and new_version != bot_version.version:
            existing = self.repo.get_by_bot_and_version(
                self.db,
                bot_id=bot_version.bot_id,
                version=new_version,
            )
            if existing:
                raise ConflictException("Já existe uma versão com esse número para esse bot.")

        return self.repo.update(self.db, bot_version, data)

    def delete(self, bot_version_id: int):
        bot_version = self.get(bot_version_id)
        self.repo.delete(self.db, bot_version)
        