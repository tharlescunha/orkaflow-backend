# app\services\schedule_service.py

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictException, NotFoundException, ValidationException
from app.domain.enums import ScheduleStatus, ScheduleType
from app.models.automation import Automation
from app.repositories.schedule_repository import ScheduleRepository


class ScheduleService:
    @staticmethod
    def list(
        db: Session,
        *,
        automation_id: int | None = None,
        active: bool | None = None,
        status: str | None = None,
    ):
        return ScheduleRepository.list(
            db,
            automation_id=automation_id,
            active=active,
            status=status,
        )

    @staticmethod
    def get(db: Session, schedule_id: int):
        schedule = ScheduleRepository.get_by_id(db, schedule_id)
        if not schedule:
            raise NotFoundException("Agendamento não encontrado")
        return schedule

    @staticmethod
    def _validate_timezone(timezone_name: str):
        try:
            ZoneInfo(timezone_name.strip())
        except Exception:
            raise ValidationException("Timezone inválido")

    @staticmethod
    def _validate_payload(data: dict):
        schedule_type = data.get("schedule_type")
        calendar_type = data.get("calendar_type")
        cron_expression = data.get("cron_expression")

        if "timezone" in data and data["timezone"]:
            ScheduleService._validate_timezone(data["timezone"])

        if schedule_type == ScheduleType.CRON:
            if not cron_expression:
                raise ValidationException("cron_expression é obrigatório para schedule do tipo cron")

        if schedule_type == ScheduleType.CALENDAR:
            if not calendar_type:
                raise ValidationException("calendar_type é obrigatório para schedule do tipo calendar")

    @staticmethod
    def create(db: Session, data: dict):
        automation = db.query(Automation).filter(Automation.id == data["automation_id"]).first()
        if not automation:
            raise NotFoundException("Automação não encontrada")

        existing = ScheduleRepository.get_by_automation_and_name(
            db,
            automation_id=data["automation_id"],
            name=data["name"],
        )
        if existing:
            raise ConflictException("Já existe um agendamento com esse nome para essa automação")

        ScheduleService._validate_payload(data)

        if "status" not in data:
            data["status"] = ScheduleStatus.ACTIVE if data.get("active", True) else ScheduleStatus.INACTIVE

        return ScheduleRepository.create(db, data)

    @staticmethod
    def update(db: Session, schedule_id: int, data: dict):
        schedule = ScheduleService.get(db, schedule_id)

        new_automation_id = data.get("automation_id", schedule.automation_id)
        new_name = data.get("name", schedule.name)

        automation = db.query(Automation).filter(Automation.id == new_automation_id).first()
        if not automation:
            raise NotFoundException("Automação não encontrada")

        existing = ScheduleRepository.get_by_automation_and_name(
            db,
            automation_id=new_automation_id,
            name=new_name,
        )
        if existing and existing.id != schedule.id:
            raise ConflictException("Já existe um agendamento com esse nome para essa automação")

        merged = {
            "schedule_type": data.get("schedule_type", schedule.schedule_type),
            "calendar_type": data.get("calendar_type", getattr(schedule, "calendar_type", None)),
            "cron_expression": data.get("cron_expression", getattr(schedule, "cron_expression", None)),
            "timezone": data.get("timezone", getattr(schedule, "timezone", "UTC")),
        }
        ScheduleService._validate_payload(merged)

        return ScheduleRepository.update(db, schedule, data)

    @staticmethod
    def pause(db: Session, schedule_id: int):
        schedule = ScheduleService.get(db, schedule_id)
        payload = {"status": ScheduleStatus.PAUSED, "active": False}
        return ScheduleRepository.update(db, schedule, payload)

    @staticmethod
    def reactivate(db: Session, schedule_id: int):
        schedule = ScheduleService.get(db, schedule_id)
        payload = {"status": ScheduleStatus.ACTIVE, "active": True}
        return ScheduleRepository.update(db, schedule, payload)

    @staticmethod
    def deactivate(db: Session, schedule_id: int):
        schedule = ScheduleService.get(db, schedule_id)
        payload = {"status": ScheduleStatus.INACTIVE, "active": False}
        return ScheduleRepository.update(db, schedule, payload)
    