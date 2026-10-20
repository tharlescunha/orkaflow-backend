import re
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.api.router import api_router
from app.core.config import get_settings
from app.core.exceptions import OrkaFlowException
from app.core.logging import logger
from app.core.database import SessionLocal
from app.services.permission_service import PermissionService

settings = get_settings()


# ==========================================================
# LIFESPAN (startup/shutdown)
# ==========================================================
@asynccontextmanager
async def lifespan(_app: FastAPI):
    seed_default_permissions()
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    debug=settings.app_debug,
    lifespan=lifespan,
)

# ==========================================================
# CORS
# ==========================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://10.50.156.202:5173",  # ✅ frontend pela rede
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================================
# SEED DE PERMISSÕES
# ==========================================================
def seed_default_permissions() -> None:
    db: Session = SessionLocal()
    try:
        result = PermissionService(db).seed_defaults()
        logger.info(f"Permissões seed executado: {result}")
    except Exception as e:
        logger.exception(f"Erro ao executar seed de permissões: {e}")
    finally:
        db.close()


# ==========================================================
# MIDDLEWARE (access log)
# ==========================================================
# Endpoints de alta frequência (workers/health): sem linha por request em INFO;
# só DEBUG em sucesso e WARNING/ERROR para status >= 400.
_HIGH_FREQUENCY_RE = re.compile(
    r"/(health|worker/heartbeat|worker/tasks/next|worker/screenshot|worker/tasks/[^/]+/logs)/?$"
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    path = request.url.path
    quiet = bool(_HIGH_FREQUENCY_RE.search(path))
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(f"HTTP {request.method} {path} -> exceção não tratada")
        raise
    elapsed_ms = (time.perf_counter() - started) * 1000
    msg = f"HTTP {request.method} {path} -> {response.status_code} ({elapsed_ms:.0f}ms)"

    if response.status_code >= 500:
        logger.error(msg)
    elif response.status_code >= 400:
        logger.warning(msg)
    elif quiet:
        logger.debug(msg)
    else:
        logger.info(msg)
    return response


# ==========================================================
# EXCEPTION HANDLERS
# ==========================================================
@app.exception_handler(OrkaFlowException)
async def orkaflow_exception_handler(request: Request, exc: OrkaFlowException):
    logger.warning(f"OrkaFlowException em {request.url.path}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Erro interno em {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Erro interno do servidor."},
    )


# ==========================================================
# ROUTES
# ==========================================================
app.include_router(api_router, prefix=settings.api_prefix)
