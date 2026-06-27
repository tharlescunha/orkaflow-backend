from sqlalchemy.orm import Session, object_session

from app.core.exceptions import ConflictException, NotFoundException, ValidationException
from app.models.bot import Bot
from app.models.repository import Repository
from app.repositories.automation_exclusive_group_repository import (
    AutomationExclusiveGroupRepository,
)
from app.repositories.automation_repository import AutomationRepository
from app.repositories.automation_success_trigger_repository import (
    AutomationSuccessTriggerRepository,
)


class AutomationService:
    @staticmethod
    def _serialize_exclusive_group(group):
        return {
            "id": group.id,
            "name": group.name,
            "label": group.label,
            "description": group.description,
            "capacity": group.capacity,
            "active": group.active,
            "automation_ids": [
                link.automation_id for link in getattr(group, "automation_links", [])
            ],
            "created_at": group.created_at,
            "updated_at": group.updated_at,
        }

    @staticmethod
    def _serialize_success_trigger(trigger):
        target = getattr(trigger, "target_automation", None)
        return {
            "id": trigger.id,
            "source_automation_id": trigger.source_automation_id,
            "target_automation_id": trigger.target_automation_id,
            "target_automation_name": target.name if target else None,
            "priority_override": trigger.priority_override,
            "inherit_parent_parameters": trigger.inherit_parent_parameters,
            "active": trigger.active,
            "created_at": trigger.created_at,
            "updated_at": trigger.updated_at,
        }

    @staticmethod
    def _serialize(automation):
        db = object_session(automation)
        exclusive_groups = []
        if db is not None:
            exclusive_groups = AutomationExclusiveGroupRepository.list_for_automation(
                db,
                automation.id,
            )
            success_triggers = AutomationSuccessTriggerRepository.list_for_source(
                db,
                automation.id,
                active=True,
            )
        else:
            success_triggers = []
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
            "default_parameters_json": getattr(automation, "default_parameters_json", None),
            "default_runtime_parameters_json": getattr(automation, "default_runtime_parameters_json", None),
            "exclusive_group_ids": [group.id for group in exclusive_groups],
            "exclusive_groups": [
                AutomationService._serialize_exclusive_group(group)
                for group in exclusive_groups
            ],
            "success_trigger_automation_ids": [
                trigger.target_automation_id for trigger in success_triggers
            ],
            "success_triggers": [
                AutomationService._serialize_success_trigger(trigger)
                for trigger in success_triggers
            ],
            "created_at": automation.created_at,
            "updated_at": automation.updated_at,
        }

    @staticmethod
    def list_exclusive_groups(db: Session, active: bool | None = None):
        groups = AutomationExclusiveGroupRepository.list(db, active=active)
        return [AutomationService._serialize_exclusive_group(group) for group in groups]

    @staticmethod
    def create_exclusive_group(db: Session, data: dict):
        normalized_name = data["name"].strip()
        if not normalized_name:
            raise ValidationException("Nome do grupo exclusivo é obrigatório")

        existing = AutomationExclusiveGroupRepository.get_by_name(db, normalized_name)
        if existing:
            raise ConflictException("Já existe um grupo exclusivo com esse nome")

        if (data.get("capacity") or 1) != 1:
            raise ValidationException("Grupo exclusivo suporta apenas capacidade 1 nesta versão")

        data = {
            **data,
            "name": normalized_name,
            "label": (data.get("label") or None),
            "capacity": data.get("capacity") or 1,
        }
        group = AutomationExclusiveGroupRepository.create(db, data)
        return AutomationService._serialize_exclusive_group(group)

    @staticmethod
    def _validate_exclusive_group_ids(db: Session, group_ids: list[int]) -> list[int]:
        normalized_ids = sorted({int(group_id) for group_id in group_ids})
        for group_id in normalized_ids:
            group = AutomationExclusiveGroupRepository.get_by_id(db, group_id)
            if not group:
                raise NotFoundException("Grupo exclusivo não encontrado")
            if not group.active:
                raise ValidationException("Grupo exclusivo inativo não pode ser vinculado")

        return normalized_ids

    @staticmethod
    def _validate_success_trigger_ids(
        db: Session,
        source_automation_id: int | None,
        target_automation_ids: list[int],
    ) -> list[int]:
        normalized_ids = sorted({int(automation_id) for automation_id in target_automation_ids})
        for target_automation_id in normalized_ids:
            if source_automation_id is not None and target_automation_id == source_automation_id:
                raise ValidationException("Automação não pode disparar ela mesma no sucesso")

            target = AutomationRepository.get_by_id(db, target_automation_id)
            if not target:
                raise NotFoundException("Automação de destino do gatilho não encontrada")

        return normalized_ids

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
        exclusive_group_ids = data.pop("exclusive_group_ids", [])
        success_trigger_automation_ids = data.pop("success_trigger_automation_ids", [])
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

        exclusive_group_ids = AutomationService._validate_exclusive_group_ids(
            db,
            exclusive_group_ids,
        )
        success_trigger_automation_ids = AutomationService._validate_success_trigger_ids(
            db,
            None,
            success_trigger_automation_ids,
        )

        automation = AutomationRepository.create(db, data)
        AutomationExclusiveGroupRepository.replace_for_automation(
            db,
            automation.id,
            exclusive_group_ids,
        )
        success_trigger_automation_ids = [
            target_id
            for target_id in success_trigger_automation_ids
            if target_id != automation.id
        ]
        AutomationSuccessTriggerRepository.replace_for_source(
            db,
            automation.id,
            success_trigger_automation_ids,
        )
        db.commit()
        automation = AutomationRepository.get_by_id(db, automation.id)
        return AutomationService._serialize(automation)

    @staticmethod
    def update(db: Session, automation_id: int, data: dict):
        automation = AutomationService.get(db, automation_id)
        exclusive_group_ids = data.pop("exclusive_group_ids", None)
        success_trigger_automation_ids = data.pop("success_trigger_automation_ids", None)

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

        if exclusive_group_ids is not None:
            exclusive_group_ids = AutomationService._validate_exclusive_group_ids(
                db,
                exclusive_group_ids,
            )
        if success_trigger_automation_ids is not None:
            success_trigger_automation_ids = AutomationService._validate_success_trigger_ids(
                db,
                automation.id,
                success_trigger_automation_ids,
            )

        updated = AutomationRepository.update(db, automation, data)
        if exclusive_group_ids is not None:
            AutomationExclusiveGroupRepository.replace_for_automation(
                db,
                updated.id,
                exclusive_group_ids,
            )
        if success_trigger_automation_ids is not None:
            AutomationSuccessTriggerRepository.replace_for_source(
                db,
                updated.id,
                success_trigger_automation_ids,
            )
        if exclusive_group_ids is not None or success_trigger_automation_ids is not None:
            db.commit()
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
    
