import base64
from fastapi import APIRouter, Depends, Query, status, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import NotFoundException
from app.schemas.runner import (
    RunnerConfigRead,
    RunnerConfigUpdate,
    RunnerCreate,
    RunnerRead,
    RunnerUpdate,
)
from app.services.runner_service import RunnerService

from datetime import datetime
from app.domain.enums import TaskStatus
from app.schemas.runner_overview import RunnerOverviewListResponse, RunnerOverviewResponse

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


@router.get("/{runner_id}/screenshot")
def get_runner_screenshot(
    runner_id: int,
    db: Session = Depends(get_db),
):
    service = RunnerService(db)
    runner = service.repo.get_by_id(runner_id)

    if not runner:
        raise NotFoundException("Runner não encontrado.")

    if not runner.last_screenshot_image:
        raise NotFoundException("Screenshot do runner não encontrado.")

    image_data = runner.last_screenshot_image

    if isinstance(image_data, memoryview):
        image_bytes = image_data.tobytes()
    elif isinstance(image_data, bytes):
        image_bytes = image_data
    elif isinstance(image_data, str):
        if image_data.startswith("data:image"):
            image_data = image_data.split(",", 1)[1]
        image_bytes = base64.b64decode(image_data)
    else:
        raise NotFoundException("Formato da imagem inválido.")

    return Response(
        content=image_bytes,
        media_type="image/png",
        headers={"Cache-Control": "no-store"},
    )

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


@router.get("/overview", response_model=RunnerOverviewListResponse)
def list_runners_overview(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    enabled: bool | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    task_status: TaskStatus | None = Query(None, alias="task_status"),
    automation_id: int | None = Query(None),
    db: Session = Depends(get_db),
):
    service = RunnerService(db)
    return service.list_overview(
        skip=skip,
        limit=limit,
        enabled=enabled,
        status=status_filter,
        date_from=date_from,
        date_to=date_to,
        task_status=task_status,
        automation_id=automation_id,
    )


@router.get("/{runner_id}/overview", response_model=RunnerOverviewResponse)
def get_runner_overview(
    runner_id: int,
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    task_status: TaskStatus | None = Query(None, alias="task_status"),
    automation_id: int | None = Query(None),
    db: Session = Depends(get_db),
):
    service = RunnerService(db)
    return service.get_overview(
        runner_id=runner_id,
        date_from=date_from,
        date_to=date_to,
        status=task_status,
        automation_id=automation_id,
    )
