# app/api/router.py

from fastapi import APIRouter

from app.api.v1.health import router as health_router
from app.api.v1.repositories import router as repositories_router
from app.api.v1.runners import router as runners_router
from app.api.v1.users import router as users_router
from app.api.v1.auth import router as auth_router
from app.api.v1.bots import router as bots_router
from app.api.v1.bot_versions import router as bot_versions_router
from app.api.v1.automations import router as automations_router
from app.api.v1.schedules import router as schedules_router
from app.api.v1.tasks import router as tasks_router
from app.api.v1.task_logs import router as task_logs_router
from app.api.v1.task_errors import router as task_errors_router
from app.api.v1.worker_registration import router as worker_registration_router
from app.api.v1.worker_auth import router as worker_auth_router
from app.api.v1.worker_heartbeat import router as worker_heartbeat_router
from app.api.v1.worker_tasks import router as worker_tasks_router
from app.api.v1.worker_logs import router as worker_logs_router
from app.api.v1.worker_errors import router as worker_errors_router
from app.api.v1.worker_sync import router as worker_sync_router
from app.api.v1.credentials import router as credentials_router

api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(repositories_router)
api_router.include_router(runners_router)
api_router.include_router(bots_router)
api_router.include_router(bot_versions_router)
api_router.include_router(automations_router)
api_router.include_router(schedules_router)
api_router.include_router(tasks_router)
api_router.include_router(task_logs_router)
api_router.include_router(task_errors_router)
api_router.include_router(worker_registration_router)
api_router.include_router(worker_auth_router)
api_router.include_router(worker_heartbeat_router)
api_router.include_router(worker_tasks_router)
api_router.include_router(worker_logs_router)
api_router.include_router(worker_errors_router)
api_router.include_router(worker_sync_router)
api_router.include_router(credentials_router)
