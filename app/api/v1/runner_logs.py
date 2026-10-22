from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.runner_log import RunnerLogPage
from app.services.runner_log_service import PANEL_DEFAULT_LIMIT, PANEL_MAX_LIMIT, RunnerLogService

router = APIRouter(prefix="/runner-logs", tags=["Runner Logs"])


@router.get("/", response_model=RunnerLogPage)
def list_runner_log_lines(
    runner_id: int = Query(...),
    after_id: int | None = Query(None, description="Só linhas depois deste id (polling)."),
    limit: int = Query(PANEL_DEFAULT_LIMIT, ge=1, le=PANEL_MAX_LIMIT),
    source: str | None = Query(None, description="worker ou bot"),
    task_id: int | None = Query(None),
    level: str | None = Query(None),
    search: str | None = Query(None),
    db: Session = Depends(get_db),
):
    service = RunnerLogService(db)
    return service.list_lines(
        runner_id=runner_id,
        after_id=after_id,
        limit=limit,
        source=source,
        task_id=task_id,
        level=level,
        search=search,
    )
