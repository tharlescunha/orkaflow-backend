"""Database Status (nov/2026): monitoramento dos bancos Azure SQL dentro do Regente. Somente leitura, só administradores."""
import json
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from app.api.deps import require_admin
from app.core.config import get_settings
from app.core.exceptions import NotFoundException, OrkaFlowException
from app.models.user import User

router = APIRouter(prefix="/dbstatus", tags=["Database Status"])


class DbStatusDisabled(OrkaFlowException):
    def __init__(self):
        super().__init__(503, "O Database Status está desligado neste servidor (DBSTATUS_ENABLED).")


@router.get("/{route:path}")
def dbstatus_route(route: str, request: Request, _: User = Depends(require_admin)):
    """Rotas do painel (databases, overview, snapshot, db, db/live, db/queries, db/extra, db/events, db/usage, db/schemas)."""
    if not get_settings().dbstatus_enabled:
        raise DbStatusDisabled()

    from app.dbstatus import service  # import tardio: só carrega onde o recurso está ligado

    handler = service.ROUTES.get("/api/" + route.strip("/"))
    if handler is None:
        raise NotFoundException("Rota do Database Status não encontrada.")

    service.start()
    data = handler(parse_qs(request.url.query))
    return Response(content=json.dumps(data, default=str), media_type="application/json", headers={"Cache-Control": "no-store"})
