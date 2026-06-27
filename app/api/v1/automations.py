from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.automation import (
    AutomationCreate,
    AutomationExclusiveGroupCreate,
    AutomationExclusiveGroupResponse,
    AutomationParameterCreate,
    AutomationParameterResponse,
    AutomationParameterUpdate,
    AutomationResponse,
    AutomationRunnerCreate,
    AutomationRunnerResponse,
    AutomationUpdate,
)
from app.services.automation_parameter_service import AutomationParameterService
from app.services.automation_runner_service import AutomationRunnerService
from app.services.automation_service import AutomationService

router = APIRouter(prefix="/automations", tags=["Automations"])


@router.get("/", response_model=list[AutomationResponse])
def list_automations(
    active: bool | None = Query(default=None),
    repository_id: int | None = Query(default=None),
    bot_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return AutomationService.list(
        db,
        active=active,
        repository_id=repository_id,
        bot_id=bot_id,
    )


@router.get(
    "/exclusive-groups/",
    response_model=list[AutomationExclusiveGroupResponse],
)
def list_exclusive_groups(
    active: bool | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return AutomationService.list_exclusive_groups(db, active=active)


@router.post(
    "/exclusive-groups/",
    response_model=AutomationExclusiveGroupResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_exclusive_group(
    payload: AutomationExclusiveGroupCreate,
    db: Session = Depends(get_db),
):
    return AutomationService.create_exclusive_group(db, payload.model_dump())


@router.get("/{automation_id}", response_model=AutomationResponse)
def get_automation(automation_id: int, db: Session = Depends(get_db)):
    return AutomationService.get_serialized(db, automation_id)


@router.post("/", response_model=AutomationResponse, status_code=status.HTTP_201_CREATED)
def create_automation(payload: AutomationCreate, db: Session = Depends(get_db)):
    return AutomationService.create(db, payload.model_dump())


@router.put("/{automation_id}", response_model=AutomationResponse)
def update_automation(
    automation_id: int,
    payload: AutomationUpdate,
    db: Session = Depends(get_db),
):
    return AutomationService.update(
        db,
        automation_id,
        payload.model_dump(exclude_unset=True),
    )


@router.post("/{automation_id}/activate", response_model=AutomationResponse)
def activate_automation(automation_id: int, db: Session = Depends(get_db)):
    return AutomationService.activate(db, automation_id)


@router.post("/{automation_id}/deactivate", response_model=AutomationResponse)
def deactivate_automation(automation_id: int, db: Session = Depends(get_db)):
    return AutomationService.deactivate(db, automation_id)


@router.get(
    "/{automation_id}/runners",
    response_model=list[AutomationRunnerResponse],
)
def list_automation_runners(automation_id: int, db: Session = Depends(get_db)):
    return AutomationRunnerService.list_by_automation(db, automation_id)


@router.post(
    "/{automation_id}/runners",
    response_model=AutomationRunnerResponse,
    status_code=status.HTTP_201_CREATED,
)
def link_runner_to_automation(
    automation_id: int,
    payload: AutomationRunnerCreate,
    db: Session = Depends(get_db),
):
    return AutomationRunnerService.link_runner(db, automation_id, payload.runner_id)


@router.delete(
    "/{automation_id}/runners/{link_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def unlink_runner_from_automation(
    automation_id: int,
    link_id: int,
    db: Session = Depends(get_db),
):
    AutomationRunnerService.unlink_runner(db, automation_id, link_id)


@router.get(
    "/{automation_id}/parameters",
    response_model=list[AutomationParameterResponse],
)
def list_automation_parameters(automation_id: int, db: Session = Depends(get_db)):
    return AutomationParameterService.list_by_automation(db, automation_id)


@router.post(
    "/{automation_id}/parameters",
    response_model=AutomationParameterResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_automation_parameter(
    automation_id: int,
    payload: AutomationParameterCreate,
    db: Session = Depends(get_db),
):
    return AutomationParameterService.create(db, automation_id, payload.model_dump())


@router.put(
    "/{automation_id}/parameters/{parameter_id}",
    response_model=AutomationParameterResponse,
)
def update_automation_parameter(
    automation_id: int,
    parameter_id: int,
    payload: AutomationParameterUpdate,
    db: Session = Depends(get_db),
):
    return AutomationParameterService.update(
        db,
        automation_id,
        parameter_id,
        payload.model_dump(exclude_unset=True),
    )


@router.delete(
    "/{automation_id}/parameters/{parameter_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_automation_parameter(
    automation_id: int,
    parameter_id: int,
    db: Session = Depends(get_db),
):
    AutomationParameterService.delete(db, automation_id, parameter_id)
    
