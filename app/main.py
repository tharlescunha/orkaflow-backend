from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import get_settings
from app.core.exceptions import OrkaFlowException
from app.core.logging import logger

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    debug=settings.app_debug,
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"HTTP {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(
        f"HTTP {request.method} {request.url.path} -> {response.status_code}"
    )
    return response


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


app.include_router(api_router, prefix=settings.api_prefix)
