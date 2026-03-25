import time

from app.core.database import SessionLocal
from app.services.watchdog_service import WatchdogService


def run_watchdog(interval_seconds: int = 10):
    while True:
        db = SessionLocal()
        try:
            service = WatchdogService(db)

            offline = service.mark_offline_runners()
            expired_locks = service.release_expired_locks()
            timed_out = service.mark_timed_out_tasks()

            if offline or expired_locks or timed_out:
                print(
                    "[WATCHDOG] "
                    f"offline={offline} "
                    f"expired_locks={expired_locks} "
                    f"timed_out={timed_out}"
                )
        except Exception as exc:
            print(f"[WATCHDOG] erro: {exc}")
            db.rollback()
        finally:
            db.close()

        time.sleep(interval_seconds)


if __name__ == "__main__":
    run_watchdog()
    