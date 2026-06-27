from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.bot_version import (
    BotVersionCreate,
    BotVersionResponse,
    BotVersionUpdate,
)
from app.services.bot_version_service import BotVersionService
from app.api.deps import get_current_user

router = APIRouter(prefix="/bot-versions", tags=["Bot Versions"])


@router.get("/", response_model=list[BotVersionResponse])
def list_bot_versions(db: Session = Depends(get_db)):
    service = BotVersionService(db)
    return service.list()


@router.get("/{bot_version_id}", response_model=BotVersionResponse)
def get_bot_version(bot_version_id: int, db: Session = Depends(get_db)):
    service = BotVersionService(db)
    return service.get(bot_version_id)


@router.post("/", response_model=BotVersionResponse)
def create_bot_version(
    payload: BotVersionCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    service = BotVersionService(db)
    data = payload.model_dump()

    data["created_by"] = current_user.id

    return service.create(data)


@router.put("/{bot_version_id}", response_model=BotVersionResponse)
def update_bot_version(
    bot_version_id: int,
    payload: BotVersionUpdate,
    db: Session = Depends(get_db),
):
    service = BotVersionService(db)
    return service.update(
        bot_version_id,
        payload.model_dump(exclude_unset=True),
    )


@router.delete("/{bot_version_id}")
def delete_bot_version(bot_version_id: int, db: Session = Depends(get_db)):
    service = BotVersionService(db)
    service.delete(bot_version_id)
    return {"message": "Versão do bot removida com sucesso."}
