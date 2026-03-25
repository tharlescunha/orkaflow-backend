from sqlalchemy.orm import Session

from app.core.exceptions import ConflictException, NotFoundException, ValidationException
from app.models.bot import Bot
from app.models.repository import Repository
from app.repositories.automation_repository import AutomationRepository


class AutomationService:
    @staticmethod
    def list(
        db: Session,
        *,
        active: bool | None = None,
        repository_id: int | None = None,
        bot_id: int | None = None,
    ):
        return AutomationRepository.list(
            db,
            active=active,
            repository_id=repository_id,
            bot_id=bot_id,
        )

    @staticmethod
    def get(db: Session, automation_id: int):
        automation = AutomationRepository.get_by_id(db, automation_id)
        if not automation:
            raise NotFoundException("Automação não encontrada")
        return automation

    @staticmethod
    def create(db: Session, data: dict):
        repository = db.query(Repository).filter(Repository.id == data["repository_id"]).first()
        if not repository:
            raise NotFoundException("Repositório não encontrado")

        bot = db.query(Bot).filter(Bot.id == data["bot_id"]).first()
        if not bot:
            raise NotFoundException("Bot não encontrado")

        if bot.repository_id != data["repository_id"]:
            raise ValidationException("O bot informado não pertence ao repositório informado")

        existing = AutomationRepository.get_by_repository_and_name(
            db,
            repository_id=data["repository_id"],
            name=data["name"],
        )
        if existing:
            raise ConflictException("Já existe uma automação com esse nome nesse repositório")

        return AutomationRepository.create(db, data)

    @staticmethod
    def update(db: Session, automation_id: int, data: dict):
        automation = AutomationService.get(db, automation_id)

        new_repository_id = data.get("repository_id", automation.repository_id)
        new_bot_id = data.get("bot_id", automation.bot_id)
        new_name = data.get("name", automation.name)

        repository = db.query(Repository).filter(Repository.id == new_repository_id).first()
        if not repository:
            raise NotFoundException("Repositório não encontrado")

        bot = db.query(Bot).filter(Bot.id == new_bot_id).first()
        if not bot:
            raise NotFoundException("Bot não encontrado")

        if bot.repository_id != new_repository_id:
            raise ValidationException("O bot informado não pertence ao repositório informado")

        existing = AutomationRepository.get_by_repository_and_name(
            db,
            repository_id=new_repository_id,
            name=new_name,
        )
        if existing and existing.id != automation.id:
            raise ConflictException("Já existe uma automação com esse nome nesse repositório")

        return AutomationRepository.update(db, automation, data)

    @staticmethod
    def activate(db: Session, automation_id: int):
        automation = AutomationService.get(db, automation_id)
        return AutomationRepository.update(db, automation, {"active": True})

    @staticmethod
    def deactivate(db: Session, automation_id: int):
        automation = AutomationService.get(db, automation_id)
        return AutomationRepository.update(db, automation, {"active": False})
    