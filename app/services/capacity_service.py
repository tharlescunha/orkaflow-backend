"""Capacidade de execução por runner e por modo (background/foreground).

Contrato:
- Por runner: até N tasks BACKGROUND simultâneas (N = runner_config.max_concurrency,
  mínimo 1, teto 5) e no máximo 1 task FOREGROUND por host (runners com o mesmo
  host_name se excluem). FOREGROUND roda junto com BACKGROUND.
- Só READY/RUNNING/STOP_REQUESTED ocupam capacidade. WAITING pré-vinculada não ocupa.
- O status BUSY/ONLINE do runner deriva das tasks abertas no banco.
"""
from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.enums import RunnerStatus
from app.models.bot import Bot
from app.models.bot_version import BotVersion
from app.models.runner import Runner
from app.models.runner_status_history import RunnerStatusHistory
from app.models.task import Task
from app.services.task_rules import (
    EXECUTING_STATUSES,
    MAX_CONCURRENCY_CAP,
    MIN_CONCURRENCY,
    MODE_BACKGROUND,
    MODE_FOREGROUND,
    normalize_mode,
)


def is_foreground_condition():
    """Condição SQL: o bot da versão da task é FOREGROUND (join com Bot necessário)."""
    return func.lower(func.coalesce(Bot.execution_mode, "")) == MODE_FOREGROUND


def is_background_condition():
    return func.lower(func.coalesce(Bot.execution_mode, "")) != MODE_FOREGROUND


def clamp_concurrency(value) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = MIN_CONCURRENCY
    return max(MIN_CONCURRENCY, min(MAX_CONCURRENCY_CAP, number))


def runner_max_concurrency(runner) -> int:
    config = getattr(runner, "config", None)
    return clamp_concurrency(getattr(config, "max_concurrency", MIN_CONCURRENCY))


def normalize_host(host_name: str | None) -> str | None:
    host = (host_name or "").strip().lower()
    return host or None


class CapacityService:
    def __init__(self, db: Session):
        self.db = db

    # ---- contagens -------------------------------------------------
    def count_by_runner_and_mode(
        self,
        statuses,
        *,
        runner_ids: list[int] | None = None,
        exclude_task_id: int | None = None,
    ) -> dict[tuple[int, str], int]:
        stmt = (
            select(Task.runner_id, Bot.execution_mode, func.count(Task.id))
            .join(BotVersion, BotVersion.id == Task.bot_version_id)
            .join(Bot, Bot.id == BotVersion.bot_id)
            .where(Task.status.in_(list(statuses)))
            .where(Task.runner_id.is_not(None))
            .group_by(Task.runner_id, Bot.execution_mode)
        )
        if runner_ids is not None:
            stmt = stmt.where(Task.runner_id.in_(runner_ids))
        if exclude_task_id is not None:
            stmt = stmt.where(Task.id != exclude_task_id)

        result: dict[tuple[int, str], int] = defaultdict(int)
        for runner_id, raw_mode, total in self.db.execute(stmt).all():
            result[(runner_id, normalize_mode(raw_mode))] += int(total)
        return result

    def host_runner_ids(self, runner) -> list[int]:
        host = normalize_host(runner.host_name)
        if host is None:
            return [runner.id]
        stmt = select(Runner.id).where(func.lower(func.trim(Runner.host_name)) == host)
        ids = [row for row in self.db.execute(stmt).scalars().all()]
        if runner.id not in ids:
            ids.append(runner.id)
        return ids

    def executing_count(
        self,
        runner,
        mode: str,
        *,
        exclude_task_id: int | None = None,
    ) -> int:
        """Quantas tasks do modo estão em execução (foreground conta no host inteiro)."""
        runner_ids = self.host_runner_ids(runner) if mode == MODE_FOREGROUND else [runner.id]
        counts = self.count_by_runner_and_mode(
            EXECUTING_STATUSES,
            runner_ids=runner_ids,
            exclude_task_id=exclude_task_id,
        )
        return sum(total for (_, m), total in counts.items() if m == mode)

    def capacity_limit(self, runner, mode: str) -> int:
        return 1 if mode == MODE_FOREGROUND else runner_max_concurrency(runner)

    def has_capacity(
        self,
        runner,
        mode: str,
        *,
        exclude_task_id: int | None = None,
    ) -> bool:
        return self.executing_count(runner, mode, exclude_task_id=exclude_task_id) < self.capacity_limit(
            runner, mode
        )

    def runner_has_executing_tasks(self, runner_id: int) -> bool:
        stmt = (
            select(func.count(Task.id))
            .where(Task.runner_id == runner_id)
            .where(Task.status.in_(list(EXECUTING_STATUSES)))
        )
        return int(self.db.execute(stmt).scalar_one() or 0) > 0

    # ---- status derivado do runner --------------------------------
    def set_runner_status(self, runner, status: RunnerStatus, reason: str | None = None) -> None:
        if runner.status == status:
            return
        runner.status = status
        self.db.add(runner)

        last = (
            self.db.execute(
                select(RunnerStatusHistory)
                .where(RunnerStatusHistory.runner_id == runner.id)
                .order_by(RunnerStatusHistory.created_at.desc(), RunnerStatusHistory.id.desc())
                .limit(1)
            )
            .scalars()
            .first()
        )
        if last is None or last.status != status.value:
            self.db.add(RunnerStatusHistory(runner_id=runner.id, status=status.value, reason=reason))

    def refresh_runner_status(self, runner, reason: str = "status_derivado_das_tasks") -> RunnerStatus:
        """BUSY se há task aberta (READY/RUNNING/STOP_REQUESTED), senão ONLINE.

        Não altera OFFLINE nem MAINTENANCE. BLOCKED (herdado de paradas forçadas antigas)
        é tratado como ONLINE/BUSY: o sistema não bloqueia runner.
        """
        if runner is None:
            return RunnerStatus.OFFLINE
        if runner.status not in (RunnerStatus.ONLINE, RunnerStatus.BUSY, RunnerStatus.BLOCKED):
            return runner.status

        self.db.flush()
        target = RunnerStatus.BUSY if self.runner_has_executing_tasks(runner.id) else RunnerStatus.ONLINE
        self.set_runner_status(runner, target, reason)
        return runner.status

    def refresh_runner_status_by_id(self, runner_id: int | None, reason: str = "status_derivado_das_tasks"):
        if runner_id is None:
            return None
        runner = self.db.get(Runner, runner_id)
        return self.refresh_runner_status(runner, reason) if runner else None
