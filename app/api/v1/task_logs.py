from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.domain.enums import TaskLogLevel
from app.schemas.task_log import TaskLogListResponse, TaskLogRead
from app.services.task_log_service import TaskLogService

router = APIRouter(prefix="/task-logs", tags=["Task Logs"])


def get_task_log_service(db: Session = Depends(get_db)) -> TaskLogService:
    return TaskLogService(db)


@router.get("/task/{task_id}", response_model=TaskLogListResponse)
def list_task_logs(
    task_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    level: TaskLogLevel | None = Query(None),
    service: TaskLogService = Depends(get_task_log_service),
):
    items, total = service.list_by_task(
        task_id,
        skip=skip,
        limit=limit,
        level=level,
    )
    return TaskLogListResponse(items=items, total=total)


@router.get("/{log_id}", response_model=TaskLogRead)
def get_task_log(
    log_id: int,
    service: TaskLogService = Depends(get_task_log_service),
):
    return service.get_log(log_id)
