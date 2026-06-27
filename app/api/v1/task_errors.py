from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.task_error import (
    TaskErrorListResponse,
    TaskErrorRichListResponse,
    TaskErrorRichListItem,
)
from app.services.task_error_service import TaskErrorService

router = APIRouter(prefix="/task-errors", tags=["Task Errors"])


def get_task_error_service(db: Session = Depends(get_db)) -> TaskErrorService:
    return TaskErrorService(db)


@router.get("", response_model=TaskErrorRichListResponse)
def list_task_errors(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=500),
    q: str | None = Query(None),
    task_id: int | None = Query(None),
    automation_id: int | None = Query(None),
    error_type: str | None = Query(None),
    error_category: str | None = Query(None),
    source: str | None = Query(None),
    code: str | None = Query(None),
    is_retryable: bool | None = Query(None),
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    service: TaskErrorService = Depends(get_task_error_service),
):
    items, total = service.list_all(
        skip=skip,
        limit=limit,
        q=q,
        task_id=task_id,
        automation_id=automation_id,
        error_type=error_type,
        error_category=error_category,
        source=source,
        code=code,
        is_retryable=is_retryable,
        start_date=start_date,
        end_date=end_date,
    )
    return TaskErrorRichListResponse(items=items, total=total)


@router.get("/task/{task_id}", response_model=TaskErrorListResponse)
def list_task_errors_by_task(
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


@router.get("/{error_id}", response_model=TaskErrorRichListItem)
def get_task_error(
    error_id: int,
    service: TaskErrorService = Depends(get_task_error_service),
):
    return service.get_rich_error(error_id)
