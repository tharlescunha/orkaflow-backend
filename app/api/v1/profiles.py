from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.core.database import get_db
from app.schemas.profile import ProfileCreate, ProfileRead, ProfileUpdate
from app.services.profile_service import ProfileService

router = APIRouter(prefix="/profiles", tags=["Profiles"])


@router.get("/", response_model=list[ProfileRead])
def list_profiles(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    active: bool | None = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    service = ProfileService(db)
    return service.list(skip=skip, limit=limit, active=active)


@router.get("/{profile_id}", response_model=ProfileRead)
def get_profile(
    profile_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    service = ProfileService(db)
    return service.get(profile_id)


@router.post(
    "/",
    response_model=ProfileRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
def create_profile(
    payload: ProfileCreate,
    db: Session = Depends(get_db),
):
    service = ProfileService(db)
    return service.create(payload)


@router.put(
    "/{profile_id}",
    response_model=ProfileRead,
    dependencies=[Depends(require_admin)],
)
def update_profile(
    profile_id: int,
    payload: ProfileUpdate,
    db: Session = Depends(get_db),
):
    service = ProfileService(db)
    return service.update(profile_id, payload)


@router.post(
    "/{profile_id}/activate",
    response_model=ProfileRead,
    dependencies=[Depends(require_admin)],
)
def activate_profile(
    profile_id: int,
    db: Session = Depends(get_db),
):
    service = ProfileService(db)
    return service.activate(profile_id)


@router.post(
    "/{profile_id}/deactivate",
    response_model=ProfileRead,
    dependencies=[Depends(require_admin)],
)
def deactivate_profile(
    profile_id: int,
    db: Session = Depends(get_db),
):
    service = ProfileService(db)
    return service.deactivate(profile_id)
