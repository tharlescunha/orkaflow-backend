# app/main.py
from fastapi import FastAPI

from app.api.router import router as api_router
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    debug=settings.app_debug,
)

app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/")
def root():
    return {
        "message": f"{settings.app_name} está no ar"
    }