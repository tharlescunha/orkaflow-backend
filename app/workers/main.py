import logging
import threading
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field

from app.workers.scheduler_runtime_main import run_scheduler_runtime
from app.workers.watchdog_main import run_watchdog
from app.workers.dispatcher_main import run_dispatcher
from app.workers.scheduler_engine_main import run_scheduler_engine

logger = logging.getLogger("workers.main")

WORKER_MONITOR_INTERVAL_SECONDS = 5
WORKER_RESTART_DELAY_BASE_SECONDS = 3
WORKER_RESTART_DELAY_MAX_SECONDS = 60


@dataclass(frozen=True)
class WorkerSpec:
    name: str
    target: Callable[[], None]


@dataclass
class WorkerState:
    restart_count: int = 0
    last_crash_at: float = field(default_factory=lambda: 0.0)


def _restart_delay(state: WorkerState) -> float:
    """Backoff exponencial no restart: 3s, 6s, 12s ... até 60s."""
    delay = min(
        WORKER_RESTART_DELAY_BASE_SECONDS * (2 ** min(state.restart_count, 8)),
        WORKER_RESTART_DELAY_MAX_SECONDS,
    )
    return delay


def run_worker_with_guard(spec: WorkerSpec, state: WorkerState):
    try:
        spec.target()
        logger.warning("[SYSTEM] %s finalizou inesperadamente (sem exceção).", spec.name)
    except Exception:
        logger.error(
            "[SYSTEM] %s caiu com exceção:\n%s",
            spec.name,
            traceback.format_exc(),
        )
    finally:
        state.restart_count += 1
        state.last_crash_at = time.monotonic()


def start_thread(spec: WorkerSpec, state: WorkerState) -> threading.Thread:
    thread = threading.Thread(
        target=run_worker_with_guard,
        args=(spec, state),
        name=spec.name,
        daemon=False,
    )
    thread.start()
    logger.info("[SYSTEM] %s iniciado (restart #%s).", spec.name, state.restart_count)
    return thread


def run_all_workers():
    specs = [
        WorkerSpec("scheduler_runtime", run_scheduler_runtime),
        WorkerSpec("watchdog", run_watchdog),
        WorkerSpec("scheduler_engine", run_scheduler_engine),
        WorkerSpec("dispatcher", run_dispatcher),
    ]

    states = {spec.name: WorkerState() for spec in specs}
    threads: dict[str, threading.Thread] = {}

    for spec in specs:
        threads[spec.name] = start_thread(spec, states[spec.name])

    logger.info("[SYSTEM] Todos os workers iniciados.")

    while True:
        time.sleep(WORKER_MONITOR_INTERVAL_SECONDS)

        for spec in specs:
            thread = threads.get(spec.name)
            if thread and thread.is_alive():
                continue

            state = states[spec.name]
            delay = _restart_delay(state)

            logger.warning(
                "[SYSTEM] %s parado (crash #%s) — reiniciando em %.0fs.",
                spec.name,
                state.restart_count,
                delay,
            )
            time.sleep(delay)
            threads[spec.name] = start_thread(spec, state)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_all_workers()
