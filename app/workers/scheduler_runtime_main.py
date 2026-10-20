# app/workers/scheduler_runtime_main.py
"""Loop do scheduler runtime (promove tasks agendadas).

Executado como thread por ``app.workers.main``. Rodar isoladamente só para depuração
e nunca junto com ``app.workers.main``.
"""
import threading

from app.services.scheduler_runtime_service import SchedulerRuntimeService
from app.workers._loop import run_service_loop


def _cycle(db, logger):
    promoted = SchedulerRuntimeService(db).promote_scheduled_tasks()
    if promoted:
        logger.info("tasks promovidas no ciclo: %s", promoted)


def run_scheduler_runtime(interval_seconds: int = 5, stop_event: threading.Event | None = None):
    run_service_loop("scheduler_runtime", interval_seconds, _cycle, stop_event)


if __name__ == "__main__":
    import os

    os.environ.setdefault("ORKAFLOW_LOG_NAME", "workers")
    run_scheduler_runtime()
