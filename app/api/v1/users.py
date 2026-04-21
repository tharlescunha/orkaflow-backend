from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.core.database import get_db
from app.schemas.user import UserChangeStatus, UserCreate, UserRead, UserUpdate
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/", response_model=list[UserRead])
def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    active: bool | None = Query(None),
    profile_id: int | None = Query(None),
    search: str | None = Query(None, min_length=1, max_length=150),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    service = UserService(db)
    return service.list(
        skip=skip,
        limit=limit,
        active=active,
        profile_id=profile_id,
        search=search,
    )


@router.get("/{user_id}", response_model=UserRead)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    service = UserService(db)
    return service.get(user_id)


@router.post(
    "/",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
):
    service = UserService(db)
    return service.create(payload)


@router.put(
    "/{user_id}",
    response_model=UserRead,
    dependencies=[Depends(require_admin)],
)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
):
    service = UserService(db)
    return service.update(user_id, payload)


@router.patch(
    "/{user_id}/status",
    response_model=UserRead,
    dependencies=[Depends(require_admin)],
)
def change_user_status(
    user_id: int,
    payload: UserChangeStatus,
    db: Session = Depends(get_db),
):
    service = UserService(db)
    return service.change_status(user_id, payload)


@router.post(
    "/{user_id}/block",
    response_model=UserRead,
    dependencies=[Depends(require_admin)],
)
def block_user(
    user_id: int,
    db: Session = Depends(get_db),
):
    service = UserService(db)
    return service.block(user_id)


@router.post(
    "/{user_id}/unblock",
    response_model=UserRead,
    dependencies=[Depends(require_admin)],
)
def unblock_user(
    user_id: int,
    db: Session = Depends(get_db),
):
    service = UserService(db)
    return service.unblock(user_id)


@router.delete(
    "/{user_id}",
    response_model=UserRead,
    dependencies=[Depends(require_admin)],
)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
):
    service = UserService(db)
    return service.delete(user_id)
