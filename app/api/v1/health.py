# app/api/v1/health.py
from sqlalchemy import text

from fastapi import APIRouter

from app.core.config import settings
from app.core.database import SessionLocal

router = APIRouter()


@router.get("/health")
def health_check():
    db_status = "ok"

    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"
    finally:
        db.close()

    overall_status = "ok" if db_status == "ok" else "degraded"

    return {
        "status": overall_status,
        "app_name": settings.app_name,
        "environment": settings.app_env,
        "database": db_status,
    }
