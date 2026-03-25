from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.bot import BotCreate, BotUpdate, BotResponse
from app.services.bot_service import BotService

router = APIRouter(prefix="/bots", tags=["Bots"])


@router.get("/", response_model=list[BotResponse])
def list_bots(db: Session = Depends(get_db)):
    service = BotService(db)
    return service.list()


@router.get("/{bot_id}", response_model=BotResponse)
def get_bot(bot_id: int, db: Session = Depends(get_db)):
    service = BotService(db)
    return service.get(bot_id)


@router.post("/", response_model=BotResponse)
def create_bot(payload: BotCreate, db: Session = Depends(get_db)):
    service = BotService(db)
    return service.create(payload.model_dump())


@router.put("/{bot_id}", response_model=BotResponse)
def update_bot(bot_id: int, payload: BotUpdate, db: Session = Depends(get_db)):
    service = BotService(db)
    return service.update(bot_id, payload.model_dump(exclude_unset=True))


@router.delete("/{bot_id}")
def delete_bot(bot_id: int, db: Session = Depends(get_db)):
    service = BotService(db)
    service.delete(bot_id)
    return {"message": "Bot removido com sucesso."}
