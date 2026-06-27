from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.dashboard import (
    DashboardBotsResponse,
    DashboardOverviewResponse,
    DashboardRunnersResponse,
)
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def get_dashboard_service(db: Session = Depends(get_db)) -> DashboardService:
    return DashboardService(db)


@router.get("/overview", response_model=DashboardOverviewResponse)
def get_dashboard_overview(
    period: str = Query("1d", pattern="^(1d|7d|15d|30d)$"),
    repository_id: int | None = Query(None),
    runner_id: int | None = Query(None),
    bot_id: int | None = Query(None),
    service: DashboardService = Depends(get_dashboard_service),
):
    return service.get_overview(
        period=period,
        repository_id=repository_id,
        runner_id=runner_id,
        bot_id=bot_id,
    )


@router.get("/runners", response_model=DashboardRunnersResponse)
def get_dashboard_runners(
    period: str = Query("1d", pattern="^(1d|7d|15d|30d)$"),
    repository_id: int | None = Query(None),
    runner_id: int | None = Query(None),
    bot_id: int | None = Query(None),
    service: DashboardService = Depends(get_dashboard_service),
):
    return service.get_runners_metrics(
        period=period,
        repository_id=repository_id,
        runner_id=runner_id,
        bot_id=bot_id,
    )


@router.get("/bots", response_model=DashboardBotsResponse)
def get_dashboard_bots(
    period: str = Query("1d", pattern="^(1d|7d|15d|30d)$"),
    repository_id: int | None = Query(None),
    runner_id: int | None = Query(None),
    bot_id: int | None = Query(None),
    service: DashboardService = Depends(get_dashboard_service),
):
    return service.get_bots_metrics(
        period=period,
        repository_id=repository_id,
        runner_id=runner_id,
        bot_id=bot_id,
    )
