# app/workers/dispatcher_main.py
"""Loop do dispatcher. Normalmente executado como thread por ``app.workers.main``.

Rodar este arquivo isoladamente serve apenas para depuração e NÃO deve ser feito
junto com ``app.workers.main`` (duplicaria o dispatcher).
"""
import threading

from app.services.dispatch_service import DispatchService
from app.workers._loop import run_service_loop


def _cycle(db, logger):
    total = DispatchService(db).dispatch_pending_tasks()
    if total:
        logger.info("tasks despachadas: %s", total)
    else:
        logger.debug("tasks despachadas: 0")


def run_dispatcher(interval_seconds: int = 5, stop_event: threading.Event | None = None):
    run_service_loop("dispatcher", interval_seconds, _cycle, stop_event)


if __name__ == "__main__":
    import os

    os.environ.setdefault("ORKAFLOW_LOG_NAME", "workers")
    run_dispatcher()
