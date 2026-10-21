# app/api/v1/notifications.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.database import get_db
from app.schemas.notification import (
    NotificationChannelRead,
    NotificationChannelUpdate,
    NotificationLogRead,
    NotificationTestResult,
    NotificationVariableRead,
)
from app.services import notification_service as service

router = APIRouter(
    prefix="/notifications",
    tags=["Notifications"],
    dependencies=[Depends(require_admin)],
)


@router.get("/channel", response_model=NotificationChannelRead)
def get_channel(db: Session = Depends(get_db)):
    return service.channel_to_read(service.get_or_create_channel(db))


@router.put("/channel", response_model=NotificationChannelRead)
def update_channel(payload: NotificationChannelUpdate, db: Session = Depends(get_db)):
    channel = service.update_channel(db, payload.model_dump(exclude_unset=True))
    return service.channel_to_read(channel)


@router.post("/channel/test", response_model=NotificationTestResult)
def test_channel(db: Session = Depends(get_db)):
    """Envia a configuração SALVA com dados de exemplo. Não pausa nada."""
    return service.send_test(db)


@router.get("/logs", response_model=list[NotificationLogRead])
def list_logs(limit: int = Query(default=50, ge=1, le=500), db: Session = Depends(get_db)):
    return service.list_logs(db, limit)


@router.get("/variables", response_model=list[NotificationVariableRead])
def list_variables():
    return [
        {"name": name, "description": description, "example": example}
        for name, description, example in service.VARIABLES
    ]
