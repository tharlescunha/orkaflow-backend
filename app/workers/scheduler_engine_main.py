# app/workers/scheduler_engine_main.py
"""Loop do scheduler engine (gera tasks a partir de schedules).

Executado como thread por ``app.workers.main``. Rodar isoladamente só para depuração
e nunca junto com ``app.workers.main``.
"""
import threading

from app.services.scheduler_engine_service import SchedulerEngineService
from app.workers._loop import run_service_loop


def _cycle(db, logger):
    total = SchedulerEngineService(db).process_schedules()
    if total:
        logger.info("tasks criadas no ciclo: %s", total)


def run_scheduler_engine(interval_seconds: int = 5, stop_event: threading.Event | None = None):
    run_service_loop("scheduler_engine", interval_seconds, _cycle, stop_event)


if __name__ == "__main__":
    import os

    os.environ.setdefault("ORKAFLOW_LOG_NAME", "workers")
    run_scheduler_engine()
