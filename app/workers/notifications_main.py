# app/workers/notifications_main.py
"""Loop das notificações: procura agendamentos com N falhas seguidas, notifica e pausa.

Executado como thread por ``app.workers.main``. Roda separado do watchdog porque o envio
HTTP (com tentativas) pode demorar e não deve atrasar o watchdog.
"""
import threading

from app.services.event_service import process_pending
from app.services.notification_service import evaluate_failures
from app.workers._loop import run_service_loop


def _cycle(db, logger):
    handled = evaluate_failures(db)
    if handled:
        logger.info("notificações: %s agendamento(s) notificado(s)/pausado(s)", handled)
    # Eventos "Quando → Então": executa os disparos deixados pendentes ao fim das tasks.
    fired = process_pending(db)
    if fired:
        logger.info("eventos: %s disparo(s) executado(s)", fired)


def run_notifications(interval_seconds: int = 30, stop_event: threading.Event | None = None):
    run_service_loop("notifications", interval_seconds, _cycle, stop_event)


if __name__ == "__main__":
    import os

    os.environ.setdefault("ORKAFLOW_LOG_NAME", "workers")
    run_notifications()
