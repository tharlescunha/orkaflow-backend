import time

from app.core.database import SessionLocal
from app.services.scheduler_engine_service import SchedulerEngineService


def run_scheduler_engine(interval_seconds: int = 5):
    while True:
        db = SessionLocal()
        try:
            service = SchedulerEngineService(db)
            total = service.process_schedules()
            if total:
                print(f"[SCHEDULER_ENGINE] tasks criadas no ciclo: {total}")
        except Exception as exc:
            print(f"[SCHEDULER_ENGINE] erro: {exc}")
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
    run_scheduler_engine()
    