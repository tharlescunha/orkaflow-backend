# app\api\v1\repositories.py

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.repository import (
    RepositoryCreate,
    RepositoryRead,
    RepositoryUpdate,
)
from app.services.repository_service import RepositoryService

router = APIRouter(prefix="/repositories", tags=["Repositories"])


@router.get("/", response_model=list[RepositoryRead])
def list_repositories(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    active: bool | None = Query(None),
    db: Session = Depends(get_db),
):
    service = RepositoryService(db)
    return service.list(skip=skip, limit=limit, active=active)


@router.get("/{repository_id}", response_model=RepositoryRead)
def get_repository(
    repository_id: int,
    db: Session = Depends(get_db),
):
    service = RepositoryService(db)
    return service.get(repository_id)


@router.post(
    "/",
    response_model=RepositoryRead,
    status_code=status.HTTP_201_CREATED,
)
def create_repository(
    payload: RepositoryCreate,
    db: Session = Depends(get_db),
):
    service = RepositoryService(db)
    return service.create(payload)


@router.put("/{repository_id}", response_model=RepositoryRead)
def update_repository(
    repository_id: int,
    payload: RepositoryUpdate,
    db: Session = Depends(get_db),
):
    service = RepositoryService(db)
    return service.update(repository_id, payload)


@router.delete("/{repository_id}", response_model=RepositoryRead)
def delete_repository(
    repository_id: int,
    db: Session = Depends(get_db),
):
    service = RepositoryService(db)
    return service.delete(repository_id)
