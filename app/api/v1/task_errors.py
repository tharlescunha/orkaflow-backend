from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.task_error import TaskErrorListResponse, TaskErrorRead
from app.services.task_error_service import TaskErrorService

router = APIRouter(prefix="/task-errors", tags=["Task Errors"])


def get_task_error_service(db: Session = Depends(get_db)) -> TaskErrorService:
    return TaskErrorService(db)


@router.get("/task/{task_id}", response_model=TaskErrorListResponse)
def list_task_errors(
    task_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    error_type: str | None = Query(None),
    service: TaskErrorService = Depends(get_task_error_service),
):
    items, total = service.list_by_task(
        task_id,
        skip=skip,
        limit=limit,
        error_type=error_type,
    )
    return TaskErrorListResponse(items=items, total=total)


@router.get("/{error_id}", response_model=TaskErrorRead)
def get_task_error(
    error_id: int,
    service: TaskErrorService = Depends(get_task_error_service),
):
    return service.get_error(error_id)
