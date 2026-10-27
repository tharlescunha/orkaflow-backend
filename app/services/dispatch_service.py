import logging
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.domain.enums import RunnerStatus, TaskLogLevel, TaskLogSource, TaskStatus
from app.models.automation import Automation
from app.models.automation_runner import AutomationRunner
from app.models.bot import Bot
from app.models.bot_version import BotVersion
from app.models.runner import Runner
from app.services.task_rules import runner_in_maintenance
from app.models.task import Task
from app.repositories.task_repository import TaskRepository
from app.services.capacity_service import (
    CapacityService,
    normalize_host,
    runner_max_concurrency,
)
from app.services.task_events import add_task_log
from app.services.queue_reasons import WaitReason, describe_wait_reason, set_waiting_reason
from app.services.task_rules import (
    EXECUTING_STATUSES,
    MODE_FOREGROUND,
    normalize_mode,
)

logger = logging.getLogger(__name__)

NO_RUNNER_LOG_WINDOW = timedelta(hours=1)
# Heartbeat mais antigo que isso: runner não recebe novas pré-vinculações (junho/2026).
DISPATCH_RUNNER_HEARTBEAT_MAX_AGE_SECONDS = 150


class DispatchService:
    """
    Dispatcher: pré-vincula tasks WAITING sem runner ao runner elegível de MENOR carga.

    - ordena por priority DESC, id ASC; só tasks sem runner_id
    - respeita Automation.active, Bot.active e o execution_mode do bot
    - capacidade por modo (BACKGROUND até max_concurrency 1..5; FOREGROUND 1 por host)
    - WAITING pré-vinculada não bloqueia o claim, mas é contada aqui para não
      pré-vincular mais do que o runner consegue executar
    - sem runner elegível: não pré-vincula (aviso no TaskLog no máximo 1x por hora)
    - NÃO coloca a task em READY (quem faz isso é WorkerService.claim_task)
    """

    BATCH_LIMIT = 500

    def __init__(self, db: Session):
        self.db = db
        self.capacity = CapacityService(db)
        self.task_repo = TaskRepository(db)

    def dispatch_pending_tasks(self) -> int:
        now = datetime.now(UTC)

        stmt = (
            select(Task, Bot.execution_mode)
            .join(BotVersion, BotVersion.id == Task.bot_version_id)
            .join(Bot, Bot.id == BotVersion.bot_id)
            .join(Automation, Automation.id == Task.automation_id)
            .where(Task.status == TaskStatus.WAITING)
            .where(Task.runner_id.is_(None))
            .where((Task.requested_start_at.is_(None)) | (Task.requested_start_at <= now))
            .where(Automation.active == True)
            .where(Bot.active == True)
            .order_by(Task.priority.desc(), Task.id.asc())
            .limit(self.BATCH_LIMIT)
        )
        rows = list(self.db.execute(stmt).all())
        if not rows:
            return 0

        links = self._load_links({task.automation_id for task, _ in rows})
        runners = {
            runner.id: runner
            for runner in self.db.execute(
                select(Runner).options(selectinload(Runner.config))
            ).scalars().all()
        }
        host_groups = self._build_host_groups(runners.values())

        executing = self.capacity.count_by_runner_and_mode(EXECUTING_STATUSES)
        pinned = self.capacity.count_by_runner_and_mode([TaskStatus.WAITING])

        dispatched = 0

        for task, raw_mode in rows:
            mode = normalize_mode(raw_mode)

            # Regras de junho/2026 preservadas: uma task aberta por automação e
            # exclusão mútua por grupo (task reservada ou lock ativo do grupo).
            # Out/2026: cada espera deixa o motivo na task (fila com explicação).
            reason = describe_wait_reason(self.task_repo, task)
            if reason is not None:
                set_waiting_reason(self.db, task, reason, source=TaskLogSource.DISPATCHER)
                continue

            candidates = []
            for runner_id in links.get(task.automation_id, ()):
                runner = runners.get(runner_id)
                if runner is None or not self._runner_is_eligible(runner):
                    continue
                if not self._has_room(runner, mode, executing, pinned, host_groups):
                    continue
                candidates.append(runner)

            if not candidates:
                set_waiting_reason(
                    self.db,
                    task,
                    WaitReason(
                        (
                            "Aguardando runner: nenhum runner elegível (online, habilitado, vinculado "
                            f"à automação e com capacidade para o modo {mode.upper()}) no momento."
                        ),
                        "DISPATCH_NO_ELIGIBLE_RUNNER",
                    ),
                    source=TaskLogSource.DISPATCHER,
                )
                continue

            runner = min(
                candidates,
                key=lambda r: (self._load(r.id, executing, pinned), r.id),
            )

            task.waiting_reason = None
            task.runner_id = runner.id
            task.last_update_at = datetime.now(UTC)
            task.dispatch_attempts = (task.dispatch_attempts or 0) + 1
            self.db.add(task)
            add_task_log(
                self.db,
                task.id,
                (
                    f"Task pré-vinculada ao runner '{runner.label or runner.name}' "
                    f"(modo {mode.upper()}, menor carga entre {len(candidates)} elegível(is))."
                ),
                level=TaskLogLevel.INFO,
                source=TaskLogSource.DISPATCHER,
                event_code="DISPATCH_PINNED",
                runner_id=runner.id,
            )

            pinned[(runner.id, mode)] += 1
            dispatched += 1

        self.db.commit()

        if dispatched:
            logger.info("Dispatcher pré-vinculou %s task(s).", dispatched)

        return dispatched

    def _load_links(self, automation_ids: set[int]) -> dict[int, list[int]]:
        stmt = (
            select(AutomationRunner.automation_id, AutomationRunner.runner_id)
            .where(AutomationRunner.automation_id.in_(list(automation_ids)))
            .order_by(AutomationRunner.id.asc())
        )
        links: dict[int, list[int]] = defaultdict(list)
        for automation_id, runner_id in self.db.execute(stmt).all():
            links[automation_id].append(runner_id)
        return links

    @staticmethod
    def _build_host_groups(runners) -> dict[int, list[int]]:
        runners = list(runners)
        by_host: dict[str, list[int]] = defaultdict(list)
        for runner in runners:
            host = normalize_host(runner.host_name)
            if host:
                by_host[host].append(runner.id)

        groups: dict[int, list[int]] = {}
        for runner in runners:
            host = normalize_host(runner.host_name)
            groups[runner.id] = by_host[host] if host else [runner.id]
        return groups

    @staticmethod
    def _runner_is_eligible(runner) -> bool:
        if not (bool(runner.enabled) and runner.status in (RunnerStatus.ONLINE, RunnerStatus.BUSY)):
            return False
        if runner_in_maintenance(runner):
            return False
        heartbeat = runner.last_heartbeat
        if heartbeat is None:
            return False
        if heartbeat.tzinfo is None:
            heartbeat = heartbeat.replace(tzinfo=UTC)
        threshold = datetime.now(UTC) - timedelta(seconds=DISPATCH_RUNNER_HEARTBEAT_MAX_AGE_SECONDS)
        return heartbeat >= threshold

    @staticmethod
    def _count(counter, runner_ids, mode: str) -> int:
        return sum(counter.get((rid, mode), 0) for rid in runner_ids)

    def _has_room(self, runner, mode, executing, pinned, host_groups) -> bool:
        if mode == MODE_FOREGROUND:
            group = host_groups.get(runner.id, [runner.id])
            used = self._count(executing, group, mode) + self._count(pinned, group, mode)
            return used < 1

        used = executing.get((runner.id, mode), 0) + pinned.get((runner.id, mode), 0)
        return used < runner_max_concurrency(runner)

    @staticmethod
    def _load(runner_id: int, executing, pinned) -> int:
        return sum(t for (rid, _), t in executing.items() if rid == runner_id) + sum(
            t for (rid, _), t in pinned.items() if rid == runner_id
        )
