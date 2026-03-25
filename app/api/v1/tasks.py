# app/api/v1/tasks.py

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.domain.enums import TaskStatus
from app.schemas.task import (
    TaskActionResponse,
    TaskCreate,
    TaskListResponse,
    TaskManualCreateResponse,
    TaskParameterListResponse,
    TaskRead,
)
from app.services.task_service import TaskService

router = APIRouter(prefix="/tasks", tags=["Tasks"])


def get_task_service(db: Session = Depends(get_db)) -> TaskService:
    return TaskService(db)


@router.get("/", response_model=TaskListResponse)
def list_tasks(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    status_filter: TaskStatus | None = Query(None, alias="status"),
    automation_id: int | None = Query(None),
    runner_id: int | None = Query(None),
    created_by: int | None = Query(None),
    service: TaskService = Depends(get_task_service),
):
    items, total = service.list_tasks(
        skip=skip,
        limit=limit,
        status=status_filter,
        automation_id=automation_id,
        runner_id=runner_id,
        created_by=created_by,
    )
    return TaskListResponse(items=items, total=total)


@router.get("/{task_id}", response_model=TaskRead)
def get_task(
    task_id: int,
    service: TaskService = Depends(get_task_service),
):
    return service.get_task(task_id)


@router.post(
    "/",
    response_model=TaskManualCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_task(
    payload: TaskCreate,
    service: TaskService = Depends(get_task_service),
):
    task = service.create_manual_task(payload=payload, created_by=None)
    return TaskManualCreateResponse(
        message="Task criada com sucesso.",
        task=task,
    )


@router.get("/{task_id}/parameters", response_model=TaskParameterListResponse)
def list_task_parameters(
    task_id: int,
    service: TaskService = Depends(get_task_service),
):
    items = service.get_task_parameters(task_id)
    return TaskParameterListResponse(items=items, total=len(items))


@router.post("/{task_id}/request-stop", response_model=TaskActionResponse)
def request_stop(
    task_id: int,
    service: TaskService = Depends(get_task_service),
):
    task = service.request_stop(task_id)
    return TaskActionResponse(
        message="Solicitação de parada registrada com sucesso.",
        task_id=task.id,
        status=task.status,
    )


@router.post("/{task_id}/force-stop", response_model=TaskActionResponse)
def force_stop(
    task_id: int,
    service: TaskService = Depends(get_task_service),
):
    task = service.force_stop(task_id)
    return TaskActionResponse(
        message="Parada forçada aplicada com sucesso.",
        task_id=task.id,
        status=task.status,
    )


@router.post("/{task_id}/cancel", response_model=TaskActionResponse)
def cancel_task(
    task_id: int,
    service: TaskService = Depends(get_task_service),
):
    task = service.cancel_task(task_id)
    return TaskActionResponse(
        message="Task cancelada com sucesso.",
        task_id=task.id,
        status=task.status,
    )
