"""Configuração central de logging do OrkaFlow.

- Saída em stdout com flush a cada linha (compatível com systemd/journalctl).
- Arquivo rotativo (10MB x 5) em ``<projeto>/logs/`` (pasta ignorada pelo git).
  Cada processo grava em um arquivo próprio para evitar corrida de rotação entre
  processos: ``orkaflow-api.log`` (padrão) e ``orkaflow-workers.log``
  (definido por ``app.workers.main`` via ``ORKAFLOW_LOG_NAME``).

Variáveis de ambiente opcionais:
- ``LOG_LEVEL`` (padrão INFO)
- ``ORKAFLOW_LOG_DIR`` (padrão ``<projeto>/logs``)
- ``ORKAFLOW_LOG_NAME`` (padrão ``api``)

Recomenda-se também ``PYTHONUNBUFFERED=1`` no serviço systemd, para que ``print``
de bibliotecas de terceiros não fiquem presos em buffer.
"""
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"


def _make_handlers() -> list[logging.Handler]:
    formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt=LOG_DATEFMT)
    handlers: list[logging.Handler] = []

    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass

    stream = logging.StreamHandler(sys.stdout)  # StreamHandler faz flush a cada emit
    stream.setFormatter(formatter)
    handlers.append(stream)

    try:
        log_dir = Path(os.environ.get("ORKAFLOW_LOG_DIR") or PROJECT_ROOT / "logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        name = os.environ.get("ORKAFLOW_LOG_NAME", "api")
        file_handler = RotatingFileHandler(
            log_dir / f"orkaflow-{name}.log",
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)
    except Exception as exc:  # sem permissão de escrita etc.: segue só com stdout
        sys.stderr.write(f"[logging] arquivo de log desabilitado: {exc}\n")

    return handlers


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("orkaflow")
    level = getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)
    logger.setLevel(level)

    if logger.handlers:
        return logger

    handlers = _make_handlers()
    # "orkaflow" (logger da aplicação) e "app" (loggers por módulo: app.services.*, app.workers.*)
    for target in (logger, logging.getLogger("app")):
        target.setLevel(level)
        target.propagate = False
        for handler in handlers:
            target.addHandler(handler)

    return logger


logger = setup_logging()
