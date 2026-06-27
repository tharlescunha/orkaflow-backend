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

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    debug=settings.app_debug,
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
# STARTUP
# ==========================================================
@app.on_event("startup")
def on_startup():
    seed_default_permissions()


# ==========================================================
# MIDDLEWARE
# ==========================================================
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"HTTP {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(
        f"HTTP {request.method} {request.url.path} -> {response.status_code}"
    )
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
