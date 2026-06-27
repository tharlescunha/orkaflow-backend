import time

from app.core.database import SessionLocal
from app.services.scheduler_runtime_service import SchedulerRuntimeService


def run_scheduler_runtime(interval_seconds: int = 5):
    while True:
        db = SessionLocal()
        try:
            service = SchedulerRuntimeService(db)
            promoted = service.promote_scheduled_tasks()
            if promoted:
                print(f"[SCHEDULER_RUNTIME] tasks promovidas no ciclo: {promoted}")
        except Exception as exc:
            print(f"[SCHEDULER_RUNTIME] erro: {exc}")
            try:
                db.rollback()
            except Exception:
                pass
        finally:
            try:
                db.close()
            except Exception:
                pass

        time.sleep(interval_seconds)


if __name__ == "__main__":
    run_scheduler_runtime()
    