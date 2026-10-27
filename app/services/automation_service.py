from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session, object_session, selectinload

from app.core.exceptions import ConflictException, NotFoundException, ValidationException
from app.models.automation_exclusive_group import (
    AutomationExclusiveGroup,
    AutomationExclusiveGroupMember,
)
from app.models.automation_success_trigger import AutomationSuccessTrigger
from app.models.automation import Automation
from app.models.bot import Bot
from app.services.credential_health_service import CredentialHealthService
from app.models.repository import Repository
from app.repositories.automation_exclusive_group_repository import (
    AutomationExclusiveGroupRepository,
)
from app.repositories.automation_repository import AutomationRepository
from app.repositories.automation_success_trigger_repository import (
    AutomationSuccessTriggerRepository,
)


@dataclass
class _Related:
    groups_by_automation: dict[int, list] = field(default_factory=dict)
    members_by_group: dict[int, list[int]] = field(default_factory=dict)
    triggers_by_automation: dict[int, list] = field(default_factory=dict)
    # Credenciais inválidas por automação (saúde de credenciais, out/2026).
    credential_alerts_by_automation: dict[int, list[dict]] = field(default_factory=dict)


class AutomationService:
    @staticmethod
    def _serialize_exclusive_group(group, automation_ids: list[int] | None = None):
        if automation_ids is None:
            automation_ids = [link.automation_id for link in getattr(group, "automation_links", [])]
        return {
            "id": group.id,
            "name": group.name,
            "label": group.label,
            "description": group.description,
            "capacity": group.capacity,
            "active": group.active,
            "automation_ids": automation_ids,
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
    def _load_related(db: Session, automation_ids: list[int]) -> "_Related":
        """Grupos exclusivos e gatilhos de várias automações em 3 queries (em vez de 2 por automação)."""
        related = _Related()
        if not automation_ids:
            return related

        automations = db.execute(select(Automation).where(Automation.id.in_(automation_ids))).scalars().all()
        related.credential_alerts_by_automation = CredentialHealthService(db).alerts_by_automation(automations)

        membership_rows = db.execute(
            select(AutomationExclusiveGroupMember.automation_id, AutomationExclusiveGroup)
            .join(AutomationExclusiveGroup, AutomationExclusiveGroup.id == AutomationExclusiveGroupMember.group_id)
            .where(AutomationExclusiveGroupMember.automation_id.in_(automation_ids))
            .order_by(AutomationExclusiveGroup.name.asc())
        ).all()
        for automation_id, group in membership_rows:
            related.groups_by_automation.setdefault(automation_id, []).append(group)

        group_ids = sorted({group.id for _, group in membership_rows})
        if group_ids:
            for group_id, automation_id in db.execute(
                select(AutomationExclusiveGroupMember.group_id, AutomationExclusiveGroupMember.automation_id)
                .where(AutomationExclusiveGroupMember.group_id.in_(group_ids))
                .order_by(AutomationExclusiveGroupMember.id.asc())
            ).all():
                related.members_by_group.setdefault(group_id, []).append(automation_id)

        triggers = db.execute(
            select(AutomationSuccessTrigger)
            .options(selectinload(AutomationSuccessTrigger.target_automation))
            .where(
                AutomationSuccessTrigger.source_automation_id.in_(automation_ids),
                AutomationSuccessTrigger.active == True,  # noqa: E712
            )
            .order_by(
                AutomationSuccessTrigger.priority_override.desc(),
                AutomationSuccessTrigger.id.asc(),
            )
        ).scalars().all()
        for trigger in triggers:
            related.triggers_by_automation.setdefault(trigger.source_automation_id, []).append(trigger)
        return related

    @staticmethod
    def _serialize(automation, related: "_Related | None" = None):
        db = object_session(automation)
        if related is None:
            related = AutomationService._load_related(db, [automation.id]) if db is not None else _Related()
        exclusive_groups = related.groups_by_automation.get(automation.id, [])
        success_triggers = related.triggers_by_automation.get(automation.id, [])
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
                AutomationService._serialize_exclusive_group(group, related.members_by_group.get(group.id, []))
                for group in exclusive_groups
            ],
            "success_trigger_automation_ids": [
                trigger.target_automation_id for trigger in success_triggers
            ],
            "success_triggers": [
                AutomationService._serialize_success_trigger(trigger)
                for trigger in success_triggers
            ],
            "credential_alerts": related.credential_alerts_by_automation.get(automation.id, []),
            "created_at": automation.created_at,
            "updated_at": automation.updated_at,
        }

    # ------------------------------------------------------------ grupos exclusivos
    @staticmethod
    def _enrich_exclusive_groups(db: Session, serialized: list[dict]) -> list[dict]:
        """Completa cada grupo com as automações (nome/ativa) e quem segura o lock agora.

        Duas consultas no total, independentemente de quantos grupos existam."""
        if not serialized:
            return serialized

        automation_ids = sorted({aid for item in serialized for aid in item["automation_ids"]})
        automations_by_id: dict[int, Automation] = {}
        if automation_ids:
            rows = db.execute(select(Automation).where(Automation.id.in_(automation_ids))).scalars().all()
            automations_by_id = {a.id: a for a in rows}

        from app.models.lock import Lock
        from app.models.runner import Runner
        from app.models.task import Task

        lock_keys = [f"exclusive_group:{item['id']}" for item in serialized]
        lock_rows = db.execute(
            select(Lock, Task, Automation, Runner)
            .join(Task, Task.id == Lock.owner_task_id)
            .outerjoin(Automation, Automation.id == Task.automation_id)
            .outerjoin(Runner, Runner.id == Lock.runner_id)
            .where(Lock.lock_key.in_(lock_keys))
            .where(Lock.active == True)  # noqa: E712
            .where(Lock.released_at.is_(None))
            .order_by(Lock.id.desc())
        ).all()
        locks_by_key: dict[str, dict] = {}
        for lock, task, automation, runner in lock_rows:
            locks_by_key.setdefault(
                lock.lock_key,
                {
                    "task_id": task.id,
                    "automation_id": task.automation_id,
                    "automation_name": (automation.label or automation.name) if automation else None,
                    "runner_id": lock.runner_id,
                    "runner_name": (runner.label or runner.name) if runner else None,
                    "acquired_at": lock.acquired_at,
                },
            )

        for item in serialized:
            item["automations"] = [
                {
                    "id": a.id,
                    "name": a.name,
                    "label": a.label,
                    "active": a.active,
                }
                for aid in item["automation_ids"]
                if (a := automations_by_id.get(aid)) is not None
            ]
            item["current_lock"] = locks_by_key.get(f"exclusive_group:{item['id']}")
        return serialized

    @staticmethod
    def list_exclusive_groups(db: Session, active: bool | None = None):
        groups = AutomationExclusiveGroupRepository.list(db, active=active)
        serialized = [AutomationService._serialize_exclusive_group(group) for group in groups]
        return AutomationService._enrich_exclusive_groups(db, serialized)

    @staticmethod
    def get_exclusive_group(db: Session, group_id: int):
        group = AutomationExclusiveGroupRepository.get_by_id(db, group_id)
        if not group:
            raise NotFoundException("Grupo exclusivo não encontrado")
        serialized = [AutomationService._serialize_exclusive_group(group)]
        return AutomationService._enrich_exclusive_groups(db, serialized)[0]

    @staticmethod
    def _validate_member_automation_ids(db: Session, automation_ids: list[int]) -> list[int]:
        normalized = sorted({int(a) for a in automation_ids})
        if not normalized:
            return []
        found = set(
            db.execute(select(Automation.id).where(Automation.id.in_(normalized))).scalars().all()
        )
        missing = [a for a in normalized if a not in found]
        if missing:
            raise NotFoundException(f"Automação não encontrada: {', '.join(str(m) for m in missing)}")
        return normalized

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

        automation_ids = data.pop("automation_ids", None)
        member_ids = AutomationService._validate_member_automation_ids(db, automation_ids or [])

        data = {
            **data,
            "name": normalized_name,
            "label": (data.get("label") or None),
            "capacity": data.get("capacity") or 1,
        }
        group = AutomationExclusiveGroupRepository.create(db, data)
        if member_ids:
            AutomationExclusiveGroupRepository.replace_members_for_group(db, group.id, member_ids)
            db.commit()
        return AutomationService.get_exclusive_group(db, group.id)

    @staticmethod
    def update_exclusive_group(db: Session, group_id: int, data: dict):
        group = AutomationExclusiveGroupRepository.get_by_id(db, group_id)
        if not group:
            raise NotFoundException("Grupo exclusivo não encontrado")

        if "name" in data and data["name"] is not None:
            normalized_name = data["name"].strip()
            if not normalized_name:
                raise ValidationException("Nome do grupo exclusivo é obrigatório")
            existing = AutomationExclusiveGroupRepository.get_by_name(db, normalized_name)
            if existing and existing.id != group.id:
                raise ConflictException("Já existe um grupo exclusivo com esse nome")
            group.name = normalized_name
        if "label" in data:
            group.label = data["label"] or None
        if "description" in data:
            group.description = data["description"] or None
        if "active" in data and data["active"] is not None:
            # Desativar não derruba nada em execução: o lock atual é liberado quando a task termina
            # e, a partir daí, o grupo deixa de ser considerado.
            group.active = bool(data["active"])

        automation_ids = data.get("automation_ids")
        if automation_ids is not None:
            member_ids = AutomationService._validate_member_automation_ids(db, automation_ids)
            AutomationExclusiveGroupRepository.replace_members_for_group(db, group.id, member_ids)

        db.commit()
        return AutomationService.get_exclusive_group(db, group.id)

    @staticmethod
    def delete_exclusive_group(db: Session, group_id: int) -> None:
        group = AutomationExclusiveGroupRepository.get_by_id(db, group_id)
        if not group:
            raise NotFoundException("Grupo exclusivo não encontrado")
        members = list(getattr(group, "automation_links", []) or [])
        if members:
            raise ConflictException(
                f"O grupo ainda tem {len(members)} automação(ões) vinculada(s). "
                "Tire as automações do grupo (ou desative o grupo) antes de excluir."
            )
        AutomationExclusiveGroupRepository.delete(db, group)

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
        related = AutomationService._load_related(db, [item.id for item in automations])
        return [AutomationService._serialize(item, related) for item in automations]

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
    
