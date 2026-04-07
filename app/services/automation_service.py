from sqlalchemy.orm import Session

from app.core.exceptions import ConflictException, NotFoundException, ValidationException
from app.models.bot import Bot
from app.models.repository import Repository
from app.repositories.automation_repository import AutomationRepository


class AutomationService:
    @staticmethod
    def _serialize(automation):
        return {
            "id": automation.id,
            "name": automation.name,
            "label": automation.label,
            "description": automation.description,
            "bot_id": automation.bot_id,
            "bot_name": automation.bot.name if automation.bot else None,
            "repository_id": automation.repository_id,
            "repository_name": automation.repository.name if automation.repository else None,
            "default_priority": automation.default_priority,
            "notification_type": (
                automation.notification_type.value
                if getattr(automation, "notification_type", None) is not None
                and hasattr(automation.notification_type, "value")
                else automation.notification_type
            ),
            "active": automation.active,
            "created_at": automation.created_at,
            "updated_at": automation.updated_at,
        }

    @staticmethod
    def list(
        db: Session,
        *,
        active: bool | None = None,
        repository_id: int | None = None,
        bot_id: int | None = None,
    ):
        automations = AutomationRepository.list(
            db,
            active=active,
            repository_id=repository_id,
            bot_id=bot_id,
        )
        return [AutomationService._serialize(item) for item in automations]

    @staticmethod
    def get(db: Session, automation_id: int):
        automation = AutomationRepository.get_by_id(db, automation_id)
        if not automation:
            raise NotFoundException("Automação não encontrada")
        return automation

    @staticmethod
    def get_serialized(db: Session, automation_id: int):
        automation = AutomationService.get(db, automation_id)
        return AutomationService._serialize(automation)

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

        automation = AutomationRepository.create(db, data)
        automation = AutomationRepository.get_by_id(db, automation.id)
        return AutomationService._serialize(automation)

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

        updated = AutomationRepository.update(db, automation, data)
        updated = AutomationRepository.get_by_id(db, updated.id)
        return AutomationService._serialize(updated)

    @staticmethod
    def activate(db: Session, automation_id: int):
        automation = AutomationService.get(db, automation_id)
        updated = AutomationRepository.update(db, automation, {"active": True})
        updated = AutomationRepository.get_by_id(db, updated.id)
        return AutomationService._serialize(updated)

    @staticmethod
    def deactivate(db: Session, automation_id: int):
        automation = AutomationService.get(db, automation_id)
        updated = AutomationRepository.update(db, automation, {"active": False})
        updated = AutomationRepository.get_by_id(db, updated.id)
        return AutomationService._serialize(updated)
    