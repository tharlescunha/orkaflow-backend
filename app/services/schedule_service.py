# app\services\schedule_service.py

from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictException, NotFoundException, ValidationException
from app.domain.enums import CalendarType, ScheduleStatus, ScheduleType
from app.models.automation import Automation
from app.models.calendar import Calendar
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
    def _normalize_calendar_interval(data: dict):
        schedule_type = data.get("schedule_type")
        calendar_type = data.get("calendar_type")
        interval_value = data.get("interval_value")
        interval_unit = data.get("interval_unit")

        if schedule_type != ScheduleType.CALENDAR:
            data["interval_value"] = None
            data["interval_unit"] = None
            return data

        if not calendar_type:
            return data

        if calendar_type == CalendarType.ONCE:
            data["interval_value"] = None
            data["interval_unit"] = None
            return data

        unit_map = {
            CalendarType.SECOND: "seconds",
            CalendarType.MINUTE: "minutes",
            CalendarType.HOUR: "hours",
            CalendarType.DAY: "days",
            CalendarType.WEEK: "weeks",
            CalendarType.MONTH: "months",
        }

        if interval_value in (None, "", 0):
            raise ValidationException("interval_value é obrigatório para calendário recorrente")

        if int(interval_value) <= 0:
            raise ValidationException("interval_value deve ser maior que zero")

        data["interval_value"] = int(interval_value)
        data["interval_unit"] = interval_unit or unit_map.get(calendar_type)

        return data

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

        ScheduleService._normalize_calendar_interval(data)

    @staticmethod
    def _map_retry(data: dict) -> None:
        """A API fala `retry_on` (lista); o modelo guarda `retry_on_json`."""
        if "retry_on" in data:
            value = data.pop("retry_on")
            if value is not None:
                data["retry_on_json"] = list(value)

    @staticmethod
    def _validate_retry_fits_interval(merged: dict, retry_max, retry_delay_seconds) -> None:
        """Tentativas × espera precisa caber dentro do intervalo do agendamento; senão uma tentativa
        encavala na execução seguinte (o despacho até segura, mas a fila vira bagunça)."""
        retry_max = int(retry_max or 0)
        delay = int(retry_delay_seconds or 0)
        if retry_max <= 0:
            return
        interval = ScheduleService._interval_seconds(merged)
        if interval is None:
            return  # execução única ou cron irregular: não dá para garantir, não bloqueia
        needed = retry_max * delay
        if needed >= interval:
            raise ValidationException(
                f"Retentativa não cabe no agendamento: {retry_max} tentativa(s) × {delay}s = {needed}s, "
                f"e o agendamento roda a cada {interval}s. Diminua as tentativas ou a espera."
            )

    @staticmethod
    def _interval_seconds(merged: dict) -> int | None:
        schedule_type = merged.get("schedule_type")
        if schedule_type == ScheduleType.CALENDAR:
            calendar_type = merged.get("calendar_type")
            if calendar_type in (None, CalendarType.ONCE):
                return None
            multiplier = {
                CalendarType.SECOND: 1,
                CalendarType.MINUTE: 60,
                CalendarType.HOUR: 3600,
                CalendarType.DAY: 86400,
                CalendarType.WEEK: 604800,
                CalendarType.MONTH: 2592000,
            }.get(calendar_type)
            value = merged.get("interval_value")
            return int(value) * multiplier if multiplier and value else None
        if schedule_type == ScheduleType.CRON and merged.get("cron_expression"):
            try:
                from datetime import datetime

                from croniter import croniter

                itr = croniter(merged["cron_expression"], datetime.now(ZoneInfo(merged.get("timezone") or "UTC")))
                first = itr.get_next(datetime)
                second = itr.get_next(datetime)
                seconds = int((second - first).total_seconds())
                return seconds if seconds > 0 else None
            except Exception:  # noqa: BLE001
                return None
        return None

    @staticmethod
    def _normalize_business_day(data: dict) -> None:
        """'No N-ésimo dia útil do mês': exige calendar_type=month, intervalo 1 e hora HH:MM."""
        n = data.get("business_day_of_month")
        if n in (None, "", 0):
            if "business_day_of_month" in data:
                data["business_day_of_month"] = None
            return
        n = int(n)
        if n < 1 or n > 23:
            raise ValidationException("O dia útil do mês precisa estar entre 1 e 23.")
        if data.get("schedule_type", ScheduleType.CALENDAR) != ScheduleType.CALENDAR:
            raise ValidationException("'Dia útil do mês' só vale para agendamento do tipo calendário.")
        time_of_day = str(data.get("time_of_day") or "").strip()
        try:
            hours, minutes = time_of_day.split(":")
            if not (0 <= int(hours) <= 23 and 0 <= int(minutes) <= 59):
                raise ValueError
        except ValueError as exc:
            raise ValidationException("Informe o horário do dia útil no formato HH:MM.") from exc
        data["business_day_of_month"] = n
        data["time_of_day"] = time_of_day
        data["calendar_type"] = CalendarType.MONTH
        data["interval_value"] = 1
        data["interval_unit"] = "months"
        # O motor recalcula a primeira ocorrência (senão rodaria na hora, como calendário comum).
        data["next_run_at"] = None

    @staticmethod
    def _validate_calendar(db: Session, data: dict) -> None:
        calendar_id = data.get("calendar_id")
        if calendar_id in (None, "", 0):
            if "calendar_id" in data:
                data["calendar_id"] = None
            return
        calendar = db.get(Calendar, int(calendar_id))
        if calendar is None:
            raise NotFoundException("Calendário não encontrado")
        if not calendar.active:
            raise ValidationException("Esse calendário está inativo.")

    @staticmethod
    def create(db: Session, data: dict):
        ScheduleService._map_retry(data)
        ScheduleService._validate_calendar(db, data)
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
        ScheduleService._normalize_business_day(data)
        ScheduleService._validate_retry_fits_interval(data, data.get("retry_max"), data.get("retry_delay_seconds"))

        if "status" not in data:
            data["status"] = ScheduleStatus.ACTIVE if data.get("active", True) else ScheduleStatus.INACTIVE

        return ScheduleRepository.create(db, data)

    @staticmethod
    def update(db: Session, schedule_id: int, data: dict):
        ScheduleService._map_retry(data)
        ScheduleService._validate_calendar(db, data)
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
            "interval_value": data.get("interval_value", getattr(schedule, "interval_value", None)),
            "interval_unit": data.get("interval_unit", getattr(schedule, "interval_unit", None)),
        }

        ScheduleService._validate_payload(merged)
        if "business_day_of_month" in data or "time_of_day" in data:
            merged_bd = {
                **merged,
                "business_day_of_month": data.get("business_day_of_month", getattr(schedule, "business_day_of_month", None)),
                "time_of_day": data.get("time_of_day", getattr(schedule, "time_of_day", None)),
            }
            ScheduleService._normalize_business_day(merged_bd)
            for key in ("business_day_of_month", "time_of_day", "calendar_type", "interval_value", "interval_unit", "next_run_at"):
                if key in merged_bd:
                    data[key] = merged_bd[key]
                    merged[key] = merged_bd[key]
        ScheduleService._validate_retry_fits_interval(
            merged,
            data.get("retry_max", getattr(schedule, "retry_max", 0)),
            data.get("retry_delay_seconds", getattr(schedule, "retry_delay_seconds", 300)),
        )

        if merged["schedule_type"] == ScheduleType.CALENDAR:
            data["interval_value"] = merged["interval_value"]
            data["interval_unit"] = merged["interval_unit"]

            if merged["calendar_type"] == CalendarType.ONCE:
                data["interval_value"] = None
                data["interval_unit"] = None
        else:
            data["interval_value"] = None
            data["interval_unit"] = None
            data["calendar_type"] = None

        if merged["schedule_type"] == ScheduleType.CALENDAR:
            data["cron_expression"] = None

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
    