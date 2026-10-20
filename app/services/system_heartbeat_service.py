"""Heartbeat dos serviços de fundo (dispatcher, watchdog, scheduler_engine, scheduler_runtime).

Mecanismo escolhido: arquivos JSON em ``<projeto>/runtime/heartbeats/<servico>.json``
(ou ``$ORKAFLOW_RUNTIME_DIR/heartbeats``), gravados de forma atômica
(arquivo temporário + ``os.replace``) pelos loops de ``app.workers`` a cada ciclo.
A API (``/health``) apenas lê esses arquivos.

Por que arquivo: API e workers rodam em processos distintos (dois serviços systemd)
no mesmo host; não exige migration nem tabela nova. Limitação: só funciona se API e
workers compartilham o mesmo diretório. Se não houver arquivos (workers não iniciados
ou em outro host) o health reporta "unknown" (degraded, HTTP 200) e não 503.

Cada arquivo contém: service, interval_seconds, pid, started_at, last_attempt_at,
last_ok_at, consecutive_failures, last_error (todos os horários em UTC ISO-8601).
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("orkaflow.heartbeat")

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Serviços de fundo esperados e seu intervalo padrão (segundos).
EXPECTED_SERVICES: dict[str, int] = {
    "dispatcher": 5,
    "watchdog": 10,
    "scheduler_engine": 5,
    "scheduler_runtime": 5,
}
STALE_FACTOR = 3
SUPERVISOR_NAME = "_supervisor"


def heartbeat_dir() -> Path:
    base = os.environ.get("ORKAFLOW_RUNTIME_DIR")
    root = Path(base) if base else PROJECT_ROOT / "runtime"
    return root / "heartbeats"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def write_json_atomic(name: str, data: dict[str, Any]) -> None:
    """Grava ``<name>.json`` atomicamente. Nunca levanta exceção (heartbeat não pode derrubar o loop)."""
    try:
        directory = heartbeat_dir()
        directory.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=f".{name}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh)
            os.replace(tmp_path, directory / f"{name}.json")
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
    except Exception:
        logger.warning("Falha ao gravar heartbeat de %s", name, exc_info=True)


class HeartbeatWriter:
    """Mantém o estado em memória de um serviço e o persiste a cada ciclo."""

    def __init__(self, service: str, interval_seconds: float):
        self.service = service
        self.interval_seconds = interval_seconds
        self.started_at = _now()
        self.last_ok_at: datetime | None = None
        self.consecutive_failures = 0
        self.last_error: str | None = None

    def _write(self) -> None:
        write_json_atomic(
            self.service,
            {
                "service": self.service,
                "interval_seconds": self.interval_seconds,
                "pid": os.getpid(),
                "started_at": _iso(self.started_at),
                "last_attempt_at": _iso(_now()),
                "last_ok_at": _iso(self.last_ok_at),
                "consecutive_failures": self.consecutive_failures,
                "last_error": self.last_error,
            },
        )

    def start(self) -> None:
        self._write()

    def ok(self) -> None:
        self.last_ok_at = _now()
        self.consecutive_failures = 0
        self.last_error = None
        self._write()

    def fail(self, exc: BaseException) -> None:
        self.consecutive_failures += 1
        self.last_error = f"{type(exc).__name__}: {exc}"[:500]
        self._write()

    def remove(self) -> None:
        try:
            (heartbeat_dir() / f"{self.service}.json").unlink()
        except OSError:
            pass


def _read_file(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def get_services_status() -> dict[str, Any]:
    """Avalia cada serviço esperado.

    status por serviço: ok | stale | unknown
      - ok: ciclo ok há <= 3x o intervalo
      - stale: sem ciclo ok há > 3x o intervalo (ou nunca teve ciclo ok e já passou o prazo)
      - unknown: sem arquivo de heartbeat
    """
    now = _now()
    directory = heartbeat_dir()
    services: dict[str, Any] = {}

    for name, default_interval in EXPECTED_SERVICES.items():
        data = _read_file(directory / f"{name}.json")
        if data is None:
            services[name] = {"status": "unknown", "last_ok_at": None, "detail": "sem heartbeat"}
            continue

        interval = float(data.get("interval_seconds") or default_interval)
        last_ok = _parse(data.get("last_ok_at"))
        reference = last_ok or _parse(data.get("started_at"))
        age = (now - reference).total_seconds() if reference else None
        limit = STALE_FACTOR * interval

        status = "ok" if (last_ok and age is not None and age <= limit) else "stale"
        if not last_ok and age is not None and age <= limit:
            status = "ok"  # recém-iniciado, ainda dentro do prazo do primeiro ciclo

        services[name] = {
            "status": status,
            "last_ok_at": data.get("last_ok_at"),
            "last_attempt_at": data.get("last_attempt_at"),
            "age_seconds": round(age, 1) if age is not None else None,
            "max_age_seconds": limit,
            "interval_seconds": interval,
            "consecutive_failures": data.get("consecutive_failures", 0),
            "last_error": data.get("last_error"),
            "pid": data.get("pid"),
        }

    supervisor = _read_file(directory / f"{SUPERVISOR_NAME}.json")
    return {"services": services, "supervisor": supervisor}
