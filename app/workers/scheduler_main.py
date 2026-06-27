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
            waiting_requeued = watchdog.requeue_stale_waiting_assignments()
            timed_out = watchdog.mark_timed_out_tasks()
            ready_not_started = watchdog.fail_ready_tasks_not_started()
            orphan = watchdog.recover_orphan_tasks()
            no_worker = watchdog.fail_tasks_without_online_workers()

            if created or offline or expired_locks or waiting_requeued or timed_out or ready_not_started or orphan or no_worker:
                print(
                    "[Scheduler] "
                    f"tasks_criadas={created} "
                    f"offline={offline} "
                    f"expired_locks={expired_locks} "
                    f"waiting_requeued={waiting_requeued} "
                    f"timed_out={timed_out} "
                    f"ready_not_started={ready_not_started} "
                    f"orphan={orphan} "
                    f"no_worker={no_worker}"
                )

        except Exception:
            print("[Scheduler] erro:")
            traceback.print_exc()
            try:
                db.rollback()
            except Exception:
                pass
        finally:
            try:
                db.close()
            except Exception:
                pass

        time.sleep(SLEEP_SECONDS)


if __name__ == "__main__":
    run()
    
