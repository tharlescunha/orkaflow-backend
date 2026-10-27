"""Calendários (out/2026): dias úteis, feriados e janelas proibidas.

Um agendamento pode apontar para um calendário e dizer o que fazer num horário não permitido:
``skip`` (não roda, anota o motivo) ou ``defer`` (roda no próximo horário permitido, mesmo horário
do dia). Quem não escolhe calendário continua exatamente como antes.

As regras de data são funções puras (sem banco) para dar para testar com qualquer data.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictException, NotFoundException, ValidationException
from app.models.calendar import Calendar
from app.models.schedule import Schedule

DEFAULT_WEEKDAYS = [0, 1, 2, 3, 4]  # segunda a sexta
WEEKDAY_LABELS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]
POLICIES = ("skip", "defer")
MAX_SEARCH_DAYS = 60


@dataclass
class CalendarCheck:
    allowed: bool
    reason: str | None
    next_allowed_at: datetime | None


# ------------------------------------------------------------------ feriados nacionais
def _easter(year: int) -> date:
    """Domingo de Páscoa (algoritmo de Meeus/Jones/Butcher)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7  # noqa: E741
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def brazilian_national_holidays(year: int) -> list[str]:
    """Feriados nacionais fixos + móveis (Carnaval, Sexta-feira Santa, Corpus Christi)."""
    easter = _easter(year)
    fixed = [(1, 1), (4, 21), (5, 1), (9, 7), (10, 12), (11, 2), (11, 15), (11, 20), (12, 25)]
    days = [date(year, m, d) for m, d in fixed]
    days += [
        easter - timedelta(days=48),  # segunda de Carnaval
        easter - timedelta(days=47),  # terça de Carnaval
        easter - timedelta(days=2),  # Sexta-feira Santa
        easter + timedelta(days=60),  # Corpus Christi
    ]
    return sorted(d.isoformat() for d in days)


# ------------------------------------------------------------------ leitura do calendário
def calendar_weekdays(calendar: Calendar) -> list[int]:
    raw = calendar.weekdays_json
    if isinstance(raw, list) and raw:
        return sorted({int(v) for v in raw if 0 <= int(v) <= 6})
    return list(DEFAULT_WEEKDAYS)


def calendar_holidays(calendar: Calendar) -> set[str]:
    raw = calendar.holidays_json
    return {str(v) for v in raw} if isinstance(raw, list) else set()


def calendar_blackouts(calendar: Calendar) -> list[dict]:
    raw = calendar.blackouts_json
    return [b for b in raw if isinstance(b, dict)] if isinstance(raw, list) else []


def _parse_hhmm(value: str) -> time:
    hours, minutes = str(value).split(":")[:2]
    return time(int(hours), int(minutes))


def _weekdays_label(weekdays: list[int]) -> str:
    if weekdays == DEFAULT_WEEKDAYS:
        return "seg a sex"
    if weekdays == list(range(7)):
        return "todos os dias"
    return ", ".join(WEEKDAY_LABELS[d] for d in weekdays)


# ------------------------------------------------------------------ regras (puras)
def day_blocked_reason(calendar: Calendar, local_day: date) -> str | None:
    if local_day.isoformat() in calendar_holidays(calendar):
        return f"feriado ({local_day.strftime('%d/%m')})"
    if local_day.weekday() not in calendar_weekdays(calendar):
        return f"{WEEKDAY_LABELS[local_day.weekday()]} não é dia útil no calendário '{calendar.name}'"
    return None


def blackout_for(calendar: Calendar, local_dt: datetime) -> dict | None:
    """Janela proibida que contém o horário, ou None."""
    for window in calendar_blackouts(calendar):
        try:
            start = _parse_hhmm(window.get("start", ""))
            end = _parse_hhmm(window.get("end", ""))
        except (ValueError, AttributeError):
            continue
        weekdays = window.get("weekdays") or []
        if weekdays and local_dt.weekday() not in [int(w) for w in weekdays]:
            continue
        current = local_dt.time().replace(second=0, microsecond=0)
        if start <= current < end:
            return window
    return None


def check_at(calendar: Calendar, local_dt: datetime) -> CalendarCheck:
    """Diz se o horário é permitido e, se não for, quando é o próximo permitido (política 'adiar')."""
    reason = day_blocked_reason(calendar, local_dt.date())
    if reason is None:
        window = blackout_for(calendar, local_dt)
        if window is None:
            return CalendarCheck(True, None, None)
        label = window.get("label") or "janela proibida"
        reason = f"{label} ({window.get('start')}–{window.get('end')})"
    return CalendarCheck(False, reason, next_allowed_at(calendar, local_dt))


def next_allowed_at(calendar: Calendar, local_dt: datetime) -> datetime | None:
    """Mesmo horário no próximo dia permitido; dentro de janela proibida, o fim da janela (se o
    dia permitir). Procura até MAX_SEARCH_DAYS dias à frente."""
    candidate = local_dt
    for _ in range(MAX_SEARCH_DAYS * 24):
        if day_blocked_reason(calendar, candidate.date()) is not None:
            candidate = datetime.combine(candidate.date() + timedelta(days=1), local_dt.time(), tzinfo=local_dt.tzinfo)
            continue
        window = blackout_for(calendar, candidate)
        if window is None:
            return candidate
        try:
            end = _parse_hhmm(window.get("end", ""))
        except (ValueError, AttributeError):
            return candidate
        candidate = datetime.combine(candidate.date(), end, tzinfo=local_dt.tzinfo)
        if candidate <= local_dt:  # janela terminando à meia-noite ou mal formada
            candidate = datetime.combine(candidate.date() + timedelta(days=1), local_dt.time(), tzinfo=local_dt.tzinfo)
    return None


def resolve_for_schedule(schedule: Schedule, execution_time_utc: datetime) -> tuple[str, datetime | None, str | None]:
    """Para o agendador: ('ok' | 'skip' | 'defer', novo horário UTC, motivo)."""
    calendar = getattr(schedule, "calendar", None)
    if calendar is None or not calendar.active:
        return "ok", execution_time_utc, None
    try:
        tz = ZoneInfo(schedule.timezone or "UTC")
    except Exception:  # noqa: BLE001
        tz = ZoneInfo("UTC")
    local = execution_time_utc.astimezone(tz)
    result = check_at(calendar, local)
    if result.allowed:
        return "ok", execution_time_utc, None
    if (schedule.calendar_policy or "defer") == "skip" or result.next_allowed_at is None:
        return "skip", None, result.reason
    return "defer", result.next_allowed_at.astimezone(ZoneInfo("UTC")), result.reason


def is_day_allowed_for_schedule(schedule: Schedule, when_utc: datetime) -> bool:
    """Para o Health: num dia não permitido pelo calendário a automação não está 'atrasada'."""
    calendar = getattr(schedule, "calendar", None)
    if calendar is None or not calendar.active:
        return True
    try:
        tz = ZoneInfo(schedule.timezone or "UTC")
    except Exception:  # noqa: BLE001
        tz = ZoneInfo("UTC")
    return day_blocked_reason(calendar, when_utc.astimezone(tz).date()) is None


# ------------------------------------------------------------------ N-ésimo dia útil do mês
def nth_business_day(calendar: Calendar | None, year: int, month: int, n: int) -> date | None:
    """Data do N-ésimo dia útil do mês (1 = primeiro). Sem calendário: segunda a sexta, sem feriados."""
    day = date(year, month, 1)
    count = 0
    while day.month == month:
        blocked = day_blocked_reason(calendar, day) if calendar is not None else (day.weekday() > 4)
        if not blocked:
            count += 1
            if count == n:
                return day
        day += timedelta(days=1)
    return None


def next_business_day_occurrence(
    calendar: Calendar | None, n: int, time_of_day: str, after_local: datetime
) -> datetime | None:
    """Próxima ocorrência estritamente depois de `after_local` (mesmo fuso)."""
    hour, minute = (int(p) for p in time_of_day.split(":")[:2])
    year, month = after_local.year, after_local.month
    for _ in range(24):
        day = nth_business_day(calendar, year, month, n)
        if day is not None:
            candidate = datetime.combine(day, time(hour, minute), tzinfo=after_local.tzinfo)
            if candidate > after_local:
                return candidate
        month += 1
        if month > 12:
            month, year = 1, year + 1
    return None


# ------------------------------------------------------------------ CRUD
def _validate(data: dict) -> None:
    weekdays = data.get("weekdays")
    if not weekdays:
        raise ValidationException("Escolha ao menos um dia da semana.")
    for value in weekdays:
        if int(value) < 0 or int(value) > 6:
            raise ValidationException("Dia da semana inválido (0 = segunda ... 6 = domingo).")
    for day in data.get("holidays") or []:
        try:
            date.fromisoformat(str(day))
        except ValueError as exc:
            raise ValidationException(f"Feriado inválido: {day} (use AAAA-MM-DD).") from exc
    for window in data.get("blackouts") or []:
        try:
            start = _parse_hhmm(window.get("start", ""))
            end = _parse_hhmm(window.get("end", ""))
        except (ValueError, AttributeError) as exc:
            raise ValidationException("Janela proibida precisa de início e fim no formato HH:MM.") from exc
        if start >= end:
            raise ValidationException("Na janela proibida o início precisa ser antes do fim.")


def _apply(calendar: Calendar, data: dict) -> None:
    calendar.name = data["name"].strip()
    calendar.description = data.get("description") or None
    calendar.active = bool(data.get("active", True))
    calendar.weekdays_json = sorted({int(v) for v in data.get("weekdays") or DEFAULT_WEEKDAYS})
    calendar.holidays_json = sorted({str(v) for v in data.get("holidays") or []})
    calendar.blackouts_json = [
        {
            "label": str(w.get("label") or "").strip(),
            "start": str(w.get("start")),
            "end": str(w.get("end")),
            "weekdays": sorted({int(d) for d in (w.get("weekdays") or [])}),
        }
        for w in data.get("blackouts") or []
    ]


def to_read(db: Session, calendar: Calendar, schedules_count: int | None = None) -> dict:
    if schedules_count is None:
        schedules_count = db.scalar(select(func.count(Schedule.id)).where(Schedule.calendar_id == calendar.id)) or 0
    weekdays = calendar_weekdays(calendar)
    return {
        "id": calendar.id,
        "name": calendar.name,
        "description": calendar.description,
        "active": calendar.active,
        "weekdays": weekdays,
        "weekdays_label": _weekdays_label(weekdays),
        "holidays": sorted(calendar_holidays(calendar)),
        "blackouts": calendar_blackouts(calendar),
        "schedules_count": schedules_count,
        "created_at": calendar.created_at,
        "updated_at": calendar.updated_at,
    }


def list_calendars(db: Session, active: bool | None = None) -> list[dict]:
    stmt = select(Calendar).order_by(Calendar.name.asc())
    if active is not None:
        stmt = stmt.where(Calendar.active == active)  # noqa: E712
    calendars = db.scalars(stmt).all()
    counts = dict(db.execute(select(Schedule.calendar_id, func.count(Schedule.id)).group_by(Schedule.calendar_id)).all())
    return [to_read(db, c, counts.get(c.id, 0)) for c in calendars]


def get_calendar(db: Session, calendar_id: int) -> Calendar:
    calendar = db.get(Calendar, calendar_id)
    if calendar is None:
        raise NotFoundException("Calendário não encontrado.")
    return calendar


def create_calendar(db: Session, data: dict) -> Calendar:
    _validate(data)
    if db.scalar(select(Calendar).where(Calendar.name == data["name"].strip())):
        raise ConflictException("Já existe um calendário com esse nome.")
    calendar = Calendar()
    _apply(calendar, data)
    db.add(calendar)
    db.commit()
    db.refresh(calendar)
    return calendar


def update_calendar(db: Session, calendar_id: int, data: dict) -> Calendar:
    calendar = get_calendar(db, calendar_id)
    _validate(data)
    other = db.scalar(select(Calendar).where(Calendar.name == data["name"].strip(), Calendar.id != calendar_id))
    if other:
        raise ConflictException("Já existe um calendário com esse nome.")
    _apply(calendar, data)
    db.commit()
    db.refresh(calendar)
    return calendar


def delete_calendar(db: Session, calendar_id: int) -> None:
    calendar = get_calendar(db, calendar_id)
    in_use = db.scalar(select(func.count(Schedule.id)).where(Schedule.calendar_id == calendar_id)) or 0
    if in_use:
        raise ConflictException(
            f"Este calendário está em uso por {in_use} agendamento(s). Troque o calendário deles antes de excluir."
        )
    db.delete(calendar)
    db.commit()


def import_holidays(db: Session, calendar_id: int, year: int) -> Calendar:
    calendar = get_calendar(db, calendar_id)
    if year < 2000 or year > 2100:
        raise ValidationException("Ano inválido.")
    merged = set(calendar_holidays(calendar)) | set(brazilian_national_holidays(year))
    calendar.holidays_json = sorted(merged)
    db.commit()
    db.refresh(calendar)
    return calendar
