from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundException
from app.models.repository import Repository
from app.repositories.bot_repository import BotRepository


class BotService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = BotRepository

    def list(self):
        return self.repo.get_all(self.db)

    def get(self, bot_id: int):
        bot = self.repo.get_by_id(self.db, bot_id)
        if not bot:
            raise NotFoundException("Bot não encontrado.")
        return bot

    def create(self, data: dict):
        repository = (
            self.db.query(Repository)
            .filter(Repository.id == data["repository_id"])
            .first()
        )
        if not repository:
            raise NotFoundException("Repositório não encontrado.")

        return self.repo.create(self.db, data)

    def update(self, bot_id: int, data: dict):
        bot = self.get(bot_id)
        return self.repo.update(self.db, bot, data)

    def delete(self, bot_id: int):
        bot = self.get(bot_id)
        self.repo.delete(self.db, bot)
        