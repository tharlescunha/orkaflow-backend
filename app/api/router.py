from fastapi import APIRouter, Depends

from app.api.deps import get_current_user

from app.api.v1.health import router as health_router
from app.api.v1.auth import router as auth_router

from app.api.v1.users import router as users_router
from app.api.v1.repositories import router as repositories_router
from app.api.v1.runners import router as runners_router
from app.api.v1.bots import router as bots_router
from app.api.v1.bot_versions import router as bot_versions_router
from app.api.v1.automations import router as automations_router
from app.api.v1.automation_health import router as automation_health_router
from app.api.v1.schedules import router as schedules_router
from app.api.v1.tasks import router as tasks_router
from app.api.v1.task_logs import router as task_logs_router
from app.api.v1.task_errors import router as task_errors_router
from app.api.v1.credentials import router as credentials_router
from app.api.v1.dashboard import router as dashboard_router

from app.api.v1.worker_registration import router as worker_registration_router
from app.api.v1.worker_auth import router as worker_auth_router
from app.api.v1.worker_heartbeat import router as worker_heartbeat_router
from app.api.v1.worker_tasks import router as worker_tasks_router
from app.api.v1.worker_logs import router as worker_logs_router
from app.api.v1.worker_errors import router as worker_errors_router
from app.api.v1.worker_sync import router as worker_sync_router
from app.api.v1.worker_credentials import router as worker_credentials_router

from app.api.v1.profiles import router as profiles_router
from app.api.v1.permissions import router as permissions_router

from app.api.v1.worker_telemetry import router as worker_telemetry_router
from app.api.v1.worker_parameters import router as worker_parameters_router
from app.api.v1.worker_runtime_events import router as worker_runtime_events_router

# 🔥 NOVO IMPORT
from app.api.v1.worker_screenshot import router as worker_screenshot_router

from app.api.v1.public_downloads import router as public_downloads_router


api_router = APIRouter()

public_router = APIRouter()
public_router.include_router(health_router)
public_router.include_router(auth_router)
public_router.include_router(public_downloads_router)

protected_router = APIRouter(
    dependencies=[Depends(get_current_user)]
)
protected_router.include_router(users_router)
protected_router.include_router(repositories_router)
protected_router.include_router(runners_router)
protected_router.include_router(bots_router)
protected_router.include_router(bot_versions_router)
protected_router.include_router(automations_router)
protected_router.include_router(automation_health_router)
protected_router.include_router(schedules_router)
protected_router.include_router(tasks_router)
protected_router.include_router(task_logs_router)
protected_router.include_router(task_errors_router)
protected_router.include_router(credentials_router)
protected_router.include_router(dashboard_router)

worker_router = APIRouter()
worker_router.include_router(worker_registration_router)
worker_router.include_router(worker_auth_router)
worker_router.include_router(worker_heartbeat_router)
worker_router.include_router(worker_tasks_router)
worker_router.include_router(worker_logs_router)
worker_router.include_router(worker_errors_router)
worker_router.include_router(worker_sync_router)
worker_router.include_router(worker_credentials_router)
worker_router.include_router(worker_telemetry_router)
worker_router.include_router(worker_parameters_router)

# 🔥 NOVO ROUTER
worker_router.include_router(worker_screenshot_router)

api_router.include_router(public_router)
api_router.include_router(protected_router)
api_router.include_router(worker_router)
api_router.include_router(profiles_router)
protected_router.include_router(permissions_router)

worker_router.include_router(worker_runtime_events_router)
