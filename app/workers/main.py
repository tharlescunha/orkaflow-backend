import threading
import time

from app.workers.scheduler_runtime_main import run_scheduler_runtime
from app.workers.watchdog_main import run_watchdog
from app.workers.dispatcher_main import run_dispatcher
from app.workers.scheduler_engine_main import run_scheduler_engine


def start_thread(target, name: str):
    thread = threading.Thread(target=target, name=name, daemon=True)
    thread.start()
    print(f"[SYSTEM] {name} iniciado")
    return thread


def run_all_workers():
    start_thread(run_scheduler_runtime, "scheduler_runtime")
    start_thread(run_watchdog, "watchdog")
    start_thread(run_scheduler_engine, "scheduler_engine")
    start_thread(run_dispatcher, "dispatcher")

    print("[SYSTEM] Todos os workers iniciados")

    while True:
        time.sleep(1)


if __name__ == "__main__":
    run_all_workers()
    