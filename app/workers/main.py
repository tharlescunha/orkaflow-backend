# app/workers/main.py
"""ENTRYPOINT ÚNICO dos workers de fundo:  ``python -m app.workers.main``

Sobe 5 threads (scheduler_runtime, watchdog, scheduler_engine, dispatcher, notifications) e as
SUPERVISIONA: se alguma morrer, é reiniciada (com log e contador). Cada loop grava
heartbeat em ``runtime/heartbeats/*.json``, lido por ``GET /health`` na API.

Não execute outros entrypoints (scheduler_main, dispatcher_main, ...) em paralelo:
duplicariam os serviços. Recomenda-se ``PYTHONUNBUFFERED=1`` no serviço systemd.
"""
import os

os.environ.setdefault("ORKAFLOW_LOG_NAME", "workers")  # antes de importar app.core.logging

import logging  # noqa: E402
import signal  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402
from datetime import datetime, timezone  # noqa: E402

from app.core.logging import logger as _root_logger  # noqa: E402,F401  (configura handlers)
from app.services.system_heartbeat_service import (  # noqa: E402
    SUPERVISOR_NAME,
    heartbeat_dir,
    write_json_atomic,
)
from app.workers.dispatcher_main import run_dispatcher  # noqa: E402
from app.workers.notifications_main import run_notifications  # noqa: E402
from app.workers.scheduler_engine_main import run_scheduler_engine  # noqa: E402
from app.workers.scheduler_runtime_main import run_scheduler_runtime  # noqa: E402
from app.workers.watchdog_main import run_watchdog  # noqa: E402

logger = logging.getLogger("orkaflow.workers.main")

SUPERVISE_INTERVAL_SECONDS = 2
MIN_RESTART_DELAY_SECONDS = 5


def _spawn(target, name: str, stop_event: threading.Event) -> threading.Thread:
    thread = threading.Thread(
        target=target, kwargs={"stop_event": stop_event}, name=name, daemon=True
    )
    thread.start()
    return thread


def run_all_workers():
    stop_event = threading.Event()

    def _request_stop(signum, _frame):
        logger.info("Sinal %s recebido; encerrando workers", signum)
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _request_stop)
        except (ValueError, OSError):
            pass

    targets = {
        "scheduler_runtime": run_scheduler_runtime,
        "watchdog": run_watchdog,
        "scheduler_engine": run_scheduler_engine,
        "dispatcher": run_dispatcher,
        "notifications": run_notifications,
    }
    started_at = datetime.now(timezone.utc).isoformat()
    threads: dict[str, threading.Thread] = {}
    restarts = {name: 0 for name in targets}
    last_restart: dict[str, float] = {}

    for name, target in targets.items():
        threads[name] = _spawn(target, name, stop_event)
        logger.info("%s iniciado", name)
    logger.info("Todos os workers iniciados (pid=%s)", os.getpid())

    while not stop_event.is_set():
        for name, thread in list(threads.items()):
            if thread.is_alive():
                continue
            since = time.monotonic() - last_restart.get(name, -MIN_RESTART_DELAY_SECONDS)
            if since < MIN_RESTART_DELAY_SECONDS:
                continue
            restarts[name] += 1
            last_restart[name] = time.monotonic()
            logger.error("Thread %s morreu; reiniciando (reinício nº %s)", name, restarts[name])
            threads[name] = _spawn(targets[name], name, stop_event)

        write_json_atomic(
            SUPERVISOR_NAME,
            {
                "pid": os.getpid(),
                "started_at": started_at,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "restarts": restarts,
                "threads_alive": {n: t.is_alive() for n, t in threads.items()},
            },
        )
        stop_event.wait(SUPERVISE_INTERVAL_SECONDS)

    for thread in threads.values():
        thread.join(timeout=10)
    # Parada limpa: remove heartbeats para o /health reportar "unknown" (e não 503 por stale).
    for name in list(targets) + [SUPERVISOR_NAME]:
        try:
            (heartbeat_dir() / f"{name}.json").unlink()
        except OSError:
            pass
    logger.info("Workers encerrados")


if __name__ == "__main__":
    run_all_workers()
