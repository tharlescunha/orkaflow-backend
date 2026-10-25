# app/api/v1/health.py
"""GET /health

- 503 se o banco falhar OU se algum serviço de fundo estiver "stale"
  (sem ciclo ok há mais de 3x seu intervalo).
- 200 "degraded" se não há heartbeat de algum serviço de fundo ("unknown":
  workers não iniciados ou em outro host) -- não derruba para 503.
- 200 "ok" caso contrário.

O estado dos serviços de fundo vem de arquivos JSON em ``runtime/heartbeats/``
(ver ``app.services.system_heartbeat_service``), gravados pelos loops de
``app.workers`` -- API e workers são processos separados.
"""
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.system_heartbeat_service import get_services_status

router = APIRouter()


@router.get("/health")
def health_check():
    db_status = "ok"
    db_error = None

    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        db_status = "error"
        db_error = type(exc).__name__
    finally:
        try:
            db.close()
        except Exception:
            pass

    # Cópia "só painel" (HEALTH_CHECK_BACKGROUND_WORKERS=false): os processos de fundo rodam
    # em outro servidor; aqui só o banco conta.
    check_background = settings.health_check_background_workers

    if check_background:
        try:
            background = get_services_status()
        except Exception as exc:  # leitura de heartbeat nunca deve quebrar o endpoint
            background = {"services": {}, "supervisor": None, "error": type(exc).__name__}
    else:
        background = {"services": {}, "supervisor": None}

    services = background["services"]
    statuses = [s["status"] for s in services.values()]

    if db_status != "ok" or "stale" in statuses:
        overall, http_status = "unhealthy", 503
    elif check_background and (not services or "unknown" in statuses):
        overall, http_status = "degraded", 200
    else:
        overall, http_status = "ok", 200

    body = {
        "status": overall,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "app_name": settings.app_name,
        "environment": settings.app_env,
        "mode": "full" if check_background else "panel_only",
        "database": db_status,
        "components": {
            "database": {"status": db_status, **({"error": db_error} if db_error else {})},
            **{name: info for name, info in services.items()},
        },
        "last_cycle": {name: info.get("last_ok_at") for name, info in services.items()},
        "supervisor": background.get("supervisor"),
    }
    return JSONResponse(status_code=http_status, content=body)
