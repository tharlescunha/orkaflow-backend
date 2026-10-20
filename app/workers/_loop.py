"""Loop supervisionável compartilhado pelos workers de fundo.

Cada ciclo: abre sessão, executa ``cycle_fn(db, logger)``, grava heartbeat de sucesso.
Qualquer exceção é logada (logger.exception), a sessão sofre rollback/close sem
nunca derrubar a thread, e o loop continua com backoff curto.
"""
from __future__ import annotations

import logging
import threading
from typing import Callable

from app.core.database import SessionLocal
from app.services.system_heartbeat_service import HeartbeatWriter

MAX_BACKOFF_SECONDS = 60


def run_service_loop(
    name: str,
    interval_seconds: float,
    cycle_fn: Callable,
    stop_event: threading.Event | None = None,
) -> None:
    logger = logging.getLogger(f"orkaflow.workers.{name}")
    stop = stop_event or threading.Event()
    heartbeat = HeartbeatWriter(name, interval_seconds)
    heartbeat.start()
    logger.info("%s iniciado (intervalo=%ss)", name, interval_seconds)
    failures = 0

    while not stop.is_set():
        db = None
        try:
            db = SessionLocal()
            cycle_fn(db, logger)
            failures = 0
            heartbeat.ok()
        except Exception as exc:
            failures += 1
            logger.exception("%s: erro no ciclo (falhas consecutivas=%s)", name, failures)
            if db is not None:
                try:
                    db.rollback()
                except Exception:
                    logger.exception("%s: falha no rollback", name)
            heartbeat.fail(exc)
        finally:
            if db is not None:
                try:
                    db.close()
                except Exception:
                    logger.exception("%s: falha ao fechar sessão", name)

        delay = interval_seconds
        if failures:
            delay = min(interval_seconds * (2 ** min(failures, 4)), MAX_BACKOFF_SECONDS)
        stop.wait(delay)

    logger.info("%s encerrado", name)
