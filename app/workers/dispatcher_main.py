import logging
import time
import traceback

from app.core.database import SessionLocal
from app.services.dispatch_service import DispatchService

logger = logging.getLogger("dispatcher")

_CONSECUTIVE_ERRORS = 0
_MAX_CONSECUTIVE_ERRORS = 10
_ERROR_BACKOFF_SECONDS = 30


def run_dispatcher(interval_seconds: int = 5):
    global _CONSECUTIVE_ERRORS

    logger.info("[DISPATCHER] iniciado.")

    while True:
        db = SessionLocal()
        try:
            service = DispatchService(db)
            total = service.dispatch_pending_tasks()

            if total:
                logger.info("[DISPATCHER] tasks despachadas: %s", total)

            _CONSECUTIVE_ERRORS = 0

        except Exception as exc:
            _CONSECUTIVE_ERRORS += 1
            logger.error(
                "[DISPATCHER] erro (consecutivo=%s): %s\n%s",
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
                    "[DISPATCHER] %s erros consecutivos — pausando %ss para evitar flood.",
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
    run_dispatcher()
