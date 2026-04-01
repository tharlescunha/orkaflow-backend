import time
import traceback

from app.core.database import SessionLocal
from app.services.scheduler_engine_service import SchedulerEngineService

from app.services.watchdog_service import WatchdogService

SLEEP_SECONDS = 5


def run():
    print("[Scheduler] iniciado...")

    while True:
        db = SessionLocal()

        try:
            created = SchedulerEngineService(db).process_schedules()

            watchdog = WatchdogService(db)
            offline = watchdog.mark_offline_runners()
            expired_locks = watchdog.release_expired_locks()
            timed_out = watchdog.mark_timed_out_tasks()
            orphan = watchdog.recover_orphan_tasks()
            no_worker = watchdog.fail_tasks_without_online_workers()

            if created or offline or expired_locks or timed_out or orphan or no_worker:
                print(
                    "[Scheduler] "
                    f"tasks_criadas={created} "
                    f"offline={offline} "
                    f"expired_locks={expired_locks} "
                    f"timed_out={timed_out} "
                    f"orphan={orphan} "
                    f"no_worker={no_worker}"
                )

        except Exception:
            print("[Scheduler] erro:")
            traceback.print_exc()
        finally:
            db.close()

        time.sleep(SLEEP_SECONDS)


if __name__ == "__main__":
    run()
    