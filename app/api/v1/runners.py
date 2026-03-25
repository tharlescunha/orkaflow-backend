from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.runner import (
    RunnerConfigRead,
    RunnerConfigUpdate,
    RunnerCreate,
    RunnerRead,
    RunnerUpdate,
)
from app.services.runner_service import RunnerService

router = APIRouter(prefix="/runners", tags=["Runners"])


@router.get("/", response_model=list[RunnerRead])
def list_runners(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    enabled: bool | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
):
    service = RunnerService(db)
    return service.list(skip=skip, limit=limit, enabled=enabled, status=status_filter)


@router.get("/{runner_id}", response_model=RunnerRead)
def get_runner(
    runner_id: int,
    db: Session = Depends(get_db),
):
    service = RunnerService(db)
    return service.get(runner_id)


@router.post("/", response_model=RunnerRead, status_code=status.HTTP_201_CREATED)
def create_runner(
    payload: RunnerCreate,
    db: Session = Depends(get_db),
):
    service = RunnerService(db)
    return service.create(payload)


@router.put("/{runner_id}", response_model=RunnerRead)
def update_runner(
    runner_id: int,
    payload: RunnerUpdate,
    db: Session = Depends(get_db),
):
    service = RunnerService(db)
    return service.update(runner_id, payload)


@router.delete("/{runner_id}", response_model=RunnerRead)
def disable_runner(
    runner_id: int,
    db: Session = Depends(get_db),
):
    service = RunnerService(db)
    return service.disable(runner_id)


@router.get("/{runner_id}/config", response_model=RunnerConfigRead)
def get_runner_config(
    runner_id: int,
    db: Session = Depends(get_db),
):
    service = RunnerService(db)
    return service.get_config(runner_id)


@router.put("/{runner_id}/config", response_model=RunnerConfigRead)
def update_runner_config(
    runner_id: int,
    payload: RunnerConfigUpdate,
    db: Session = Depends(get_db),
):
    service = RunnerService(db)
    return service.update_config(runner_id, payload)
