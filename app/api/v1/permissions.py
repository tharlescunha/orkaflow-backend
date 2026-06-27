from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.schemas.profile import PermissionRead
from app.services.permission_service import PermissionService

router = APIRouter(prefix="/permissions", tags=["Permissions"])


@router.get("/", response_model=list[PermissionRead])
def list_permissions(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    service = PermissionService(db)
    return service.list()
