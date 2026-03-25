# app\workers\scheduler_main.py

import time
import traceback

from app.core.database import SessionLocal
from app.services.scheduler_service import SchedulerService


SLEEP_SECONDS = 5


def run():
    print("[Scheduler] iniciado...")

    while True:
        db = SessionLocal()

        try:
            SchedulerService(db).run()
        except Exception as exc:
            print("[Scheduler] erro:")
            traceback.print_exc()
        finally:
            db.close()

        time.sleep(SLEEP_SECONDS)


if __name__ == "__main__":
    run()
