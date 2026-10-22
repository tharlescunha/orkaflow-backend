"""Tela de Logs: recebe as linhas do worker.log das máquinas e entrega ao painel."""
import logging
import re
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import NotFoundException
from app.repositories.runner_log_repository import RunnerLogRepository
from app.repositories.runner_repository import RunnerRepository
from app.schemas.runner_log import MAX_MESSAGE_LENGTH, WorkerLogBatchRequest
from app.services.task_rules import as_aware
from app.services.worker_service import WorkerService

logger = logging.getLogger(__name__)

SOURCE_WORKER = "worker"
SOURCE_BOT = "bot"
SOURCES = (SOURCE_WORKER, SOURCE_BOT)

# O worker grava a saída do robô como "[BOT][task_id=123] linha".
BOT_LINE_RE = re.compile(r"^\[BOT\]\[task_id=(\d+)\]\s?")

KNOWN_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}

PANEL_DEFAULT_LIMIT = 300
PANEL_MAX_LIMIT = 1000


def _parse_line(message: str) -> tuple[str, int | None, str]:
    match = BOT_LINE_RE.match(message)
    if not match:
        return SOURCE_WORKER, None, message
    return SOURCE_BOT, int(match.group(1)), message[match.end():]


class RunnerLogService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = RunnerLogRepository(db)
        self.runner_repo = RunnerRepository(db)

    def ingest(self, payload: WorkerLogBatchRequest) -> dict:
        runner = WorkerService(self.db)._authenticate_runner(payload.uuid, payload.token)

        rows = []
        for line in payload.lines:
            source, task_id, message = _parse_line(line.message or "")
            level = (line.level or "INFO").upper()
            rows.append(
                {
                    "runner_id": runner.id,
                    "logged_at": as_aware(line.logged_at) or datetime.now(UTC),
                    "level": level if level in KNOWN_LEVELS else "INFO",
                    "source": source,
                    "task_id": task_id,
                    "message": message[:MAX_MESSAGE_LENGTH],
                }
            )

        return {"accepted": self.repo.add_many(rows)}

    def list_lines(
        self,
        runner_id: int,
        after_id: int | None = None,
        limit: int = PANEL_DEFAULT_LIMIT,
        source: str | None = None,
        task_id: int | None = None,
        level: str | None = None,
        search: str | None = None,
    ) -> dict:
        if not self.runner_repo.get_by_id(runner_id):
            raise NotFoundException("Runner não encontrado.")

        limit = max(1, min(limit, PANEL_MAX_LIMIT))
        items = self.repo.list_lines(
            runner_id=runner_id,
            after_id=after_id,
            limit=limit,
            source=source if source in SOURCES else None,
            task_id=task_id,
            level=level.upper() if level else None,
            search=(search or "").strip() or None,
        )

        # last_id acompanha o fim do log mesmo com filtro, para o polling não reler o que foi pulado.
        if items:
            last_id = items[-1].id
        elif after_id is not None:
            last_id = after_id
        else:
            last_id = self.repo.last_id(runner_id)

        return {
            "items": items,
            "last_id": last_id,
            "retention_days": settings.runner_log_retention_days,
        }

    def purge_expired(self, max_batches: int = 20) -> int:
        cutoff = datetime.now(UTC) - timedelta(days=settings.runner_log_retention_days)
        total = 0
        for _ in range(max_batches):
            deleted = self.repo.delete_older_than(cutoff)
            total += deleted
            if deleted == 0:
                break
        return total
