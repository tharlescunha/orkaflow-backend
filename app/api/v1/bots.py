from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.schemas.bot import BotCreate, BotListResponse, BotRead, BotSourceInspect, BotSourceInspection, BotUpdate
from app.services.bot_service import BotService
from app.services.git_repo_service import inspect_source, mask_url_credentials

router = APIRouter(prefix="/bots", tags=["Bots"])


@router.get("/", response_model=BotListResponse)
def list_bots(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    search: str | None = Query(None),
    repository_id: int | None = Query(None),
    active: bool | None = Query(None),
    db: Session = Depends(get_db),
):
    service = BotService(db)
    return service.list(
        skip=skip,
        limit=limit,
        search=search,
        repository_id=repository_id,
        active=active,
    )


@router.post("/inspect-source", response_model=BotSourceInspection)
def inspect_bot_source(payload: BotSourceInspect, _=Depends(get_current_user)):
    """Confere se o link do Git funciona e traz nome, descrição, último commit e última tag (nada é gravado)."""
    info = inspect_source(payload.source_url)
    return {
        "name": info.name,
        "description": info.description,
        "branch": info.branch,
        "repository": mask_url_credentials(payload.source_url.strip()),
        "head": {
            "hash": info.head.hash,
            "short": info.head.short,
            "author": info.head.author,
            "committed_at": info.head.committed_at,
            "message": info.head.message,
        },
        "latest_tag": info.latest_tag,
        "suggested_version": info.suggested_version,
    }


@router.get("/{bot_id}", response_model=BotRead)
def get_bot(bot_id: int, db: Session = Depends(get_db)):
    service = BotService(db)
    return service.get(bot_id)


@router.post("/", response_model=BotRead, status_code=status.HTTP_201_CREATED)
def create_bot(
    payload: BotCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    service = BotService(db)
    data = payload.model_dump()
    data["created_by"] = current_user.id
    return service.create(data)


@router.put("/{bot_id}", response_model=BotRead)
def update_bot(bot_id: int, payload: BotUpdate, db: Session = Depends(get_db)):
    service = BotService(db)
    return service.update(bot_id, payload.model_dump(exclude_unset=True))


@router.delete("/{bot_id}")
def delete_bot(bot_id: int, db: Session = Depends(get_db)):
    service = BotService(db)
    service.delete(bot_id)
    return {"message": "Bot removido com sucesso."}
