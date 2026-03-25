# app\workers\dispatcher_main.py

import time

from app.core.database import SessionLocal
from app.services.dispatch_service import DispatchService


def run_dispatcher(interval_seconds: int = 5):
    while True:
        db = SessionLocal()
        try:
            service = DispatchService(db)
            total = service.dispatch_pending_tasks()
            print(f"[DISPATCHER] tasks despachadas: {total}")
        except Exception as exc:
            print(f"[DISPATCHER] erro: {exc}")
        finally:
            db.close()

        time.sleep(interval_seconds)


if __name__ == "__main__":
    run_dispatcher()