import logging
import time
import traceback

from app.core.database import SessionLocal
from app.services.watchdog_service import WatchdogService

logger = logging.getLogger("watchdog")

_CONSECUTIVE_ERRORS = 0
_MAX_CONSECUTIVE_ERRORS = 10
_ERROR_BACKOFF_SECONDS = 30


def run_watchdog(interval_seconds: int = 10):
    global _CONSECUTIVE_ERRORS

    logger.info("[WATCHDOG] iniciado.")

    while True:
        db = SessionLocal()

        try:
            service = WatchdogService(db)

            offline = service.mark_offline_runners()
            expired_locks = service.release_expired_locks()
            waiting_requeued = service.requeue_stale_waiting_assignments()
            timed_out = service.mark_timed_out_tasks()
            ready_not_started_failed = service.fail_ready_tasks_not_started()
            orphan_recovered = service.recover_orphan_tasks()
            no_worker_failed = service.fail_tasks_without_online_workers()

            if (
                offline
                or expired_locks
                or waiting_requeued
                or timed_out
                or ready_not_started_failed
                or orphan_recovered
                or no_worker_failed
            ):
                logger.info(
                    "[WATCHDOG] offline=%s expired_locks=%s waiting_requeued=%s "
                    "timed_out=%s ready_not_started_failed=%s orphan_recovered=%s "
                    "no_worker_failed=%s",
                    offline, expired_locks, waiting_requeued,
                    timed_out, ready_not_started_failed, orphan_recovered, no_worker_failed,
                )

            _CONSECUTIVE_ERRORS = 0

        except Exception as exc:
            _CONSECUTIVE_ERRORS += 1
            logger.error(
                "[WATCHDOG] erro (consecutivo=%s): %s\n%s",
                _CONSECUTIVE_ERRORS,
                exc,
                traceback.format_exc(),
            )

            try:
                db.rollback()
            except Exception:
                pass

            if _CONSECUTIVE_ERRORS >= _MAX_CONSECUTIVE_ERRORS:
                logger.critical(
                    "[WATCHDOG] %s erros consecutivos — pausando %ss.",
                    _CONSECUTIVE_ERRORS,
                    _ERROR_BACKOFF_SECONDS,
                )
                time.sleep(_ERROR_BACKOFF_SECONDS)
                _CONSECUTIVE_ERRORS = 0

        finally:
            try:
                db.close()
            except Exception:
                pass

        time.sleep(interval_seconds)


if __name__ == "__main__":
    run_watchdog()
