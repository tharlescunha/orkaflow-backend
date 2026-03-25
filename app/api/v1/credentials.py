from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.credential import (
    CredentialCreate,
    CredentialItemCreate,
    CredentialItemRead,
    CredentialItemSecretRead,
    CredentialItemUpdate,
    CredentialRead,
    CredentialWithItemsRead,
    CredentialUpdate,
)
from app.services.credential_service import CredentialService

router = APIRouter(prefix="/credentials", tags=["Credentials"])


@router.get("/", response_model=list[CredentialRead])
def list_credentials(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    active: bool | None = Query(None),
    repository_id: int | None = Query(None, ge=1),
    db: Session = Depends(get_db),
):
    service = CredentialService(db)
    return service.list(
        skip=skip,
        limit=limit,
        active=active,
        repository_id=repository_id,
    )


@router.get("/{credential_id}", response_model=CredentialWithItemsRead)
def get_credential(
    credential_id: int,
    db: Session = Depends(get_db),
):
    service = CredentialService(db)
    return service.get(credential_id)


@router.post("/", response_model=CredentialRead, status_code=status.HTTP_201_CREATED)
def create_credential(
    payload: CredentialCreate,
    db: Session = Depends(get_db),
):
    service = CredentialService(db)
    return service.create(payload)


@router.put("/{credential_id}", response_model=CredentialRead)
def update_credential(
    credential_id: int,
    payload: CredentialUpdate,
    db: Session = Depends(get_db),
):
    service = CredentialService(db)
    return service.update(credential_id, payload)


@router.delete("/{credential_id}", response_model=CredentialRead)
def delete_credential(
    credential_id: int,
    db: Session = Depends(get_db),
):
    service = CredentialService(db)
    return service.delete(credential_id)


@router.get("/{credential_id}/items", response_model=list[CredentialItemRead])
def list_credential_items(
    credential_id: int,
    active: bool | None = Query(None),
    db: Session = Depends(get_db),
):
    service = CredentialService(db)
    return service.list_items(credential_id, active=active)


@router.post(
    "/{credential_id}/items",
    response_model=CredentialItemRead,
    status_code=status.HTTP_201_CREATED,
)
def create_credential_item(
    credential_id: int,
    payload: CredentialItemCreate,
    db: Session = Depends(get_db),
):
    service = CredentialService(db)
    return service.create_item(credential_id, payload)


@router.put("/{credential_id}/items/{item_id}", response_model=CredentialItemRead)
def update_credential_item(
    credential_id: int,
    item_id: int,
    payload: CredentialItemUpdate,
    db: Session = Depends(get_db),
):
    service = CredentialService(db)
    return service.update_item(credential_id, item_id, payload)


@router.delete("/{credential_id}/items/{item_id}", response_model=CredentialItemRead)
def delete_credential_item(
    credential_id: int,
    item_id: int,
    db: Session = Depends(get_db),
):
    service = CredentialService(db)
    return service.delete_item(credential_id, item_id)


@router.get(
    "/{credential_id}/items/{item_id}/reveal",
    response_model=CredentialItemSecretRead,
)
def reveal_credential_item_secret(
    credential_id: int,
    item_id: int,
    db: Session = Depends(get_db),
):
    service = CredentialService(db)
    return service.reveal_item_secret(credential_id, item_id)
