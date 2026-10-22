# app/workers/watchdog_main.py
"""Loop do watchdog (runners offline, locks expirados, tasks travadas/órfãs).

Executado como thread por ``app.workers.main``. Rodar isoladamente só para depuração
e nunca junto com ``app.workers.main``.
"""
import threading
import time

from app.services.runner_log_service import RunnerLogService
from app.services.watchdog_service import WatchdogService
from app.workers._loop import run_service_loop

# Limpeza dos logs das máquinas (tela de Logs) não precisa rodar a cada 10s.
RUNNER_LOG_PURGE_INTERVAL_SECONDS = 600
_last_runner_log_purge = 0.0


def _purge_runner_logs(db, logger):
    global _last_runner_log_purge
    now = time.monotonic()
    if now - _last_runner_log_purge < RUNNER_LOG_PURGE_INTERVAL_SECONDS:
        return
    _last_runner_log_purge = now
    try:
        deleted = RunnerLogService(db).purge_expired()
        if deleted:
            logger.info("runner_log_lines expiradas removidas=%s", deleted)
    except Exception:
        # Nunca derruba o ciclo do watchdog por causa dos logs.
        db.rollback()
        logger.exception("Falha ao limpar runner_log_lines expiradas")


def _cycle(db, logger):
    _purge_runner_logs(db, logger)

    service = WatchdogService(db)

    offline = service.mark_offline_runners()
    expired_locks = service.release_expired_locks()
    waiting_requeued = service.requeue_stale_waiting_assignments()
    timed_out = service.mark_timed_out_tasks()
    orphan_recovered = service.recover_orphan_tasks()
    no_worker_failed = service.fail_tasks_without_online_workers()

    if offline or expired_locks or waiting_requeued or timed_out or orphan_recovered or no_worker_failed:
        logger.info(
            "offline=%s expired_locks=%s waiting_requeued=%s timed_out=%s orphan_recovered=%s no_worker_failed=%s",
            offline,
            expired_locks,
            waiting_requeued,
            timed_out,
            orphan_recovered,
            no_worker_failed,
        )


def run_watchdog(interval_seconds: int = 10, stop_event: threading.Event | None = None):
    run_service_loop("watchdog", interval_seconds, _cycle, stop_event)


if __name__ == "__main__":
    import os

    os.environ.setdefault("ORKAFLOW_LOG_NAME", "workers")
    run_watchdog()
