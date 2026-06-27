from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.automation_health import AutomationHealthListResponse
from app.services.automation_health_service import AutomationHealthService

router = APIRouter(
    prefix="/automation-health",
    tags=["Automation Health"],
)


@router.get("/", response_model=AutomationHealthListResponse)
def list_automation_health(
    repository_id: int | None = Query(default=None),
    bot_id: int | None = Query(default=None),
    active: bool | None = Query(default=True),
    db: Session = Depends(get_db),
):
    return AutomationHealthService.list(
        db,
        repository_id=repository_id,
        bot_id=bot_id,
        active=active,
    )
