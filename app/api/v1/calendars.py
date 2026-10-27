# app/api/v1/calendars.py
"""Calendários: dias úteis, feriados e janelas proibidas que os agendamentos seguem."""
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.database import get_db
from app.core.exceptions import ValidationException
from app.schemas.calendar import (
    CalendarCheckResponse,
    CalendarCreate,
    CalendarImportRequest,
    CalendarRead,
    CalendarUpdate,
)
from app.services import calendar_service as service

router = APIRouter(prefix="/calendars", tags=["Calendars"], dependencies=[Depends(require_admin)])


@router.get("/", response_model=list[CalendarRead])
def list_calendars(active: bool | None = Query(default=None), db: Session = Depends(get_db)):
    return service.list_calendars(db, active=active)


@router.post("/", response_model=CalendarRead, status_code=201)
def create_calendar(payload: CalendarCreate, db: Session = Depends(get_db)):
    return service.to_read(db, service.create_calendar(db, payload.model_dump()))


@router.get("/{calendar_id}", response_model=CalendarRead)
def get_calendar(calendar_id: int, db: Session = Depends(get_db)):
    return service.to_read(db, service.get_calendar(db, calendar_id))


@router.put("/{calendar_id}", response_model=CalendarRead)
def update_calendar(calendar_id: int, payload: CalendarUpdate, db: Session = Depends(get_db)):
    return service.to_read(db, service.update_calendar(db, calendar_id, payload.model_dump()))


@router.delete("/{calendar_id}")
def delete_calendar(calendar_id: int, db: Session = Depends(get_db)):
    service.delete_calendar(db, calendar_id)
    return {"message": "Calendário removido."}


@router.post("/{calendar_id}/holidays/import", response_model=CalendarRead)
def import_holidays(calendar_id: int, payload: CalendarImportRequest, db: Session = Depends(get_db)):
    """Adiciona os feriados nacionais brasileiros do ano (fixos + Carnaval, Sexta-feira Santa, Corpus Christi)."""
    return service.to_read(db, service.import_holidays(db, calendar_id, payload.year))


@router.get("/{calendar_id}/check", response_model=CalendarCheckResponse)
def check_calendar(
    calendar_id: int,
    at: datetime = Query(..., description="Data e hora (ISO 8601) no fuso informado"),
    timezone: str = Query(default="America/Sao_Paulo"),
    db: Session = Depends(get_db),
):
    """Diz se o horário é permitido e, se não for, o próximo permitido (política 'adiar')."""
    calendar = service.get_calendar(db, calendar_id)
    try:
        tz = ZoneInfo(timezone)
    except Exception as exc:  # noqa: BLE001
        raise ValidationException("Fuso horário inválido.") from exc
    local = at.astimezone(tz) if at.tzinfo else at.replace(tzinfo=tz)
    result = service.check_at(calendar, local)
    return {"allowed": result.allowed, "reason": result.reason, "next_allowed_at": result.next_allowed_at}
