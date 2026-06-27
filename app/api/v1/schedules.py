# app\api\v1\schedules.py

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.schedule import ScheduleCreate, ScheduleResponse, ScheduleUpdate
from app.services.schedule_service import ScheduleService

router = APIRouter(prefix="/schedules", tags=["Schedules"])


@router.get("/", response_model=list[ScheduleResponse])
def list_schedules(
    automation_id: int | None = Query(default=None),
    active: bool | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
):
    return ScheduleService.list(
        db,
        automation_id=automation_id,
        active=active,
        status=status_filter,
    )


@router.get("/{schedule_id}", response_model=ScheduleResponse)
def get_schedule(schedule_id: int, db: Session = Depends(get_db)):
    return ScheduleService.get(db, schedule_id)


@router.post("/", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
def create_schedule(payload: ScheduleCreate, db: Session = Depends(get_db)):
    return ScheduleService.create(db, payload.model_dump())


@router.put("/{schedule_id}", response_model=ScheduleResponse)
def update_schedule(
    schedule_id: int,
    payload: ScheduleUpdate,
    db: Session = Depends(get_db),
):
    return ScheduleService.update(
        db,
        schedule_id,
        payload.model_dump(exclude_unset=True),
    )


@router.post("/{schedule_id}/pause", response_model=ScheduleResponse)
def pause_schedule(schedule_id: int, db: Session = Depends(get_db)):
    return ScheduleService.pause(db, schedule_id)


@router.post("/{schedule_id}/reactivate", response_model=ScheduleResponse)
def reactivate_schedule(schedule_id: int, db: Session = Depends(get_db)):
    return ScheduleService.reactivate(db, schedule_id)


@router.post("/{schedule_id}/deactivate", response_model=ScheduleResponse)
def deactivate_schedule(schedule_id: int, db: Session = Depends(get_db)):
    return ScheduleService.deactivate(db, schedule_id)
