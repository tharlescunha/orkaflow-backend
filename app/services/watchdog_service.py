"""Watchdog do OrkaFlow.

Princípio do dono: NUNCA parar/pausar/bloquear runner, bot ou task por causa de ERRO.
O watchdog só:
- marca runner OFFLINE quando o heartbeat para (sem tocar nas tasks nem nos locks);
- finaliza task por timeout REAL (started_at + timeout + margem) ou inatividade configurada;
- finaliza task READY que nunca virou RUNNING (claim abandonado);
- desfaz pré-vínculo de task WAITING em runner indisponível;
- registra TaskLog warning (uma vez) quando algo está estranho, sem mudar o estado.

stop_requested só é setado automaticamente no timeout real da task.
"""
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.enums import ErrorCategory, RunnerStatus, TaskLogLevel, TaskLogSource, TaskStatus
from app.models.runner import Runner
from app.models.task import Task
from app.repositories.lock_repository import LockRepository
from app.services.capacity_service import CapacityService
from app.services.task_events import add_task_error, add_task_log, add_task_log_once
from app.services.task_rules import (
    EXECUTING_STATUSES,
    RUNNER_OFFLINE_AFTER_SECONDS,
    STALE_READY_CLAIM_SECONDS,
    TASK_TIMEOUT_MARGIN_SECONDS,
    WAITING_UNLINK_AFTER_SECONDS,
    as_aware,
)

logger = logging.getLogger(__name__)

OPEN_STATUSES = (
    TaskStatus.WAITING,
    TaskStatus.READY,
    TaskStatus.RUNNING,
    TaskStatus.STOP_REQUESTED,
)

NO_RUNNER_WARNING_WINDOW = timedelta(hours=1)
WAITING_ASSIGNMENT_REQUEUE_AFTER_SECONDS = 180


class WatchdogService:
    def __init__(self, db: Session):
        self.db = db
        self.lock_repository = LockRepository(db)
        self.capacity = CapacityService(db)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _release_task_locks(self, task: Task, now: datetime):
        """Libera locks da task. NÃO remove runner_id (histórico/tela/auditoria)."""
        self.lock_repository.release_by_task_id(task.id, now)

    def _release_runner_if_possible(self, runner_id: int | None):
        """Recalcula BUSY/ONLINE a partir das tasks em execução do banco.

        Não altera OFFLINE nem MAINTENANCE.
        """
        self.capacity.refresh_runner_status_by_id(runner_id, reason="runner_liberado_sem_tasks_abertas")

    def _finalize_task(
        self,
        task: Task,
        *,
        status: TaskStatus,
        now: datetime,
        message: str,
        error_type: str,
        code: str,
        category: ErrorCategory,
        stop_requested: bool = False,
    ) -> None:
        task.status = status
        task.finished_at = now
        task.last_update_at = now
        if stop_requested:
            task.stop_requested = True
        task.final_message = task.final_message or message
        self.db.add(task)

        add_task_error(
            self.db,
            task.id,
            error_type,
            message,
            category=category,
            source=TaskLogSource.SYSTEM,
            code=code,
        )
        add_task_log(
            self.db,
            task.id,
            message,
            level=TaskLogLevel.ERROR,
            source=TaskLogSource.SYSTEM,
            event_code=code,
            runner_id=task.runner_id,
        )
        self._release_task_locks(task, now)
        self._release_runner_if_possible(task.runner_id)

    # ------------------------------------------------------------------
    # runners
    # ------------------------------------------------------------------
    def mark_offline_runners(self, stale_after_seconds: int = RUNNER_OFFLINE_AFTER_SECONDS) -> int:
        """Runner sem heartbeat vira OFFLINE. NÃO libera locks e NÃO mexe nas tasks."""
        threshold = datetime.now(UTC) - timedelta(seconds=stale_after_seconds)

        stmt = (
            select(Runner)
            .where(Runner.status.in_([RunnerStatus.ONLINE, RunnerStatus.BUSY]))
            .where(
                (Runner.last_heartbeat.is_(None))
                | (Runner.last_heartbeat < threshold)
            )
        )

        runners = list(self.db.execute(stmt).scalars().all())

        for runner in runners:
            self.capacity.set_runner_status(runner, RunnerStatus.OFFLINE, "heartbeat_timeout")

        if runners:
            self.db.commit()

        return len(runners)

    # ------------------------------------------------------------------
    # locks
    # ------------------------------------------------------------------
    def release_expired_locks(self) -> int:
        """Só libera lock por expiração real (a task renova o lock enquanto está ativa)."""
        now = datetime.now(UTC)
        locks = self.lock_repository.list_active_expired(now)

        for lock in locks:
            self.lock_repository.release(lock, now)

        if locks:
            self.db.commit()

        return len(locks)

    # ------------------------------------------------------------------
    # timeouts
    # ------------------------------------------------------------------
    def mark_timed_out_tasks(self) -> int:
        """Finaliza tasks por timeout real, inatividade configurada ou claim abandonado.

        - Timeout real: started_at + timeout_seconds + margem (120s). TIMEOUT com TaskError;
          único caso em que o watchdog seta stop_requested=True.
        - Inatividade: RUNNING sem atividade (last_update_at) por mais que
          inactivity_timeout_seconds (>0). TIMEOUT com TaskError, sem stop_requested.
        - READY sem started_at parada por mais de STALE_READY_CLAIM_SECONDS: ERROR com
          TaskError, sem stop_requested.
        """
        now = datetime.now(UTC)
        total = 0

        stmt = select(Task).where(Task.status.in_(list(EXECUTING_STATUSES)))
        tasks = list(self.db.execute(stmt).scalars().all())

        for task in tasks:
            started_at = as_aware(task.started_at)

            if started_at is not None:
                timeout_seconds = task.timeout_seconds or 3600
                deadline = started_at + timedelta(seconds=timeout_seconds + TASK_TIMEOUT_MARGIN_SECONDS)

                if now >= deadline:
                    self._finalize_task(
                        task,
                        status=TaskStatus.TIMEOUT,
                        now=now,
                        message=(
                            f"Task excedeu o timeout de {timeout_seconds}s "
                            f"(+{TASK_TIMEOUT_MARGIN_SECONDS}s de margem) e foi finalizada pelo watchdog."
                        ),
                        error_type="TaskTimeout",
                        code="TASK_TIMEOUT",
                        category=ErrorCategory.TIMEOUT,
                        stop_requested=True,
                    )
                    total += 1
                    continue

                inactivity = task.inactivity_timeout_seconds
                if (
                    task.status == TaskStatus.RUNNING
                    and inactivity
                    and inactivity > 0
                ):
                    reference = as_aware(task.last_update_at) or started_at
                    if reference < started_at:
                        reference = started_at
                    if now - reference > timedelta(seconds=inactivity):
                        self._finalize_task(
                            task,
                            status=TaskStatus.TIMEOUT,
                            now=now,
                            message=(
                                f"Task sem atividade por mais de {inactivity}s "
                                "(inactivity_timeout_seconds) e foi finalizada pelo watchdog."
                            ),
                            error_type="TaskInactivityTimeout",
                            code="TASK_INACTIVITY_TIMEOUT",
                            category=ErrorCategory.TIMEOUT,
                        )
                        total += 1
                continue

            # Sem started_at: claim feito mas nunca chegou a RUNNING.
            if task.status == TaskStatus.READY:
                reference = max(
                    (d for d in (as_aware(task.last_update_at), as_aware(task.runner_claimed_at)) if d),
                    default=None,
                )
                if reference is None:
                    reference = as_aware(task.created_at)
                if reference is not None and now - reference > timedelta(seconds=STALE_READY_CLAIM_SECONDS):
                    self._finalize_task(
                        task,
                        status=TaskStatus.ERROR,
                        now=now,
                        message=(
                            "Task assumida pelo worker (READY) mas nunca iniciou a execução "
                            f"em {STALE_READY_CLAIM_SECONDS // 60} minutos; finalizada pelo watchdog."
                        ),
                        error_type="ClaimAbandoned",
                        code="TASK_CLAIM_ABANDONED",
                        category=ErrorCategory.TECHNICAL,
                    )
                    total += 1

        if total:
            self.db.commit()
            logger.warning("Watchdog finalizou %s task(s) por timeout/inatividade/claim abandonado.", total)

        return total

    # ------------------------------------------------------------------
    # avisos (sem mudar estado)
    # ------------------------------------------------------------------
    def recover_orphan_tasks(self, stale_after_seconds: int = 120) -> int:
        """Task aberta com runner sem heartbeat E sem atividade: só registra aviso.

        NÃO marca ERROR e NUNCA seta stop_requested. Um único TaskLog por task.
        """
        now = datetime.now(UTC)
        threshold = now - timedelta(seconds=stale_after_seconds)

        stmt = select(Task).where(Task.status.in_(list(EXECUTING_STATUSES)))
        tasks = list(self.db.execute(stmt).scalars().all())

        total = 0
        for task in tasks:
            runner = self.db.get(Runner, task.runner_id) if task.runner_id is not None else None

            last_heartbeat = as_aware(runner.last_heartbeat) if runner else None
            runner_stale = (
                runner is None
                or runner.status == RunnerStatus.OFFLINE
                or last_heartbeat is None
                or last_heartbeat < threshold
            )

            last_update = as_aware(task.last_update_at)
            task_stale = last_update is None or last_update < threshold

            if runner_stale and task_stale:
                created = add_task_log_once(
                    self.db,
                    task.id,
                    (
                        "Aviso do watchdog: o runner está sem heartbeat e a task sem atividade há mais de "
                        f"{stale_after_seconds}s. Nenhuma ação foi tomada; a task segue aberta e "
                        "será finalizada apenas por timeout, ação do usuário ou retorno do worker."
                    ),
                    "WATCHDOG_ORPHAN_WARNING",
                    level=TaskLogLevel.WARNING,
                    source=TaskLogSource.SYSTEM,
                    runner_id=task.runner_id,
                )
                if created:
                    total += 1

        if total:
            self.db.commit()

        return total

    def warn_tasks_without_online_workers(self) -> int:
        """Sem nenhum runner online: não falha ninguém, só avisa (no máximo 1x por hora por task)."""
        online_stmt = (
            select(func.count(Runner.id))
            .where(Runner.enabled == True)
            .where(Runner.status.in_([RunnerStatus.ONLINE, RunnerStatus.BUSY]))
        )
        if int(self.db.execute(online_stmt).scalar_one() or 0) > 0:
            return 0

        tasks = list(
            self.db.execute(select(Task).where(Task.status.in_(list(OPEN_STATUSES)))).scalars().all()
        )

        total = 0
        for task in tasks:
            created = add_task_log_once(
                self.db,
                task.id,
                (
                    "Nenhum runner online no momento. A task permanece como está e "
                    "seguirá assim que um runner voltar a ficar online."
                ),
                "WATCHDOG_NO_ONLINE_RUNNER",
                within=NO_RUNNER_WARNING_WINDOW,
                level=TaskLogLevel.WARNING,
                source=TaskLogSource.SYSTEM,
                runner_id=task.runner_id,
            )
            if created:
                total += 1

        if total:
            self.db.commit()

        return total

    def unlink_waiting_from_unavailable_runners(
        self,
        unlink_after_seconds: int = WAITING_UNLINK_AFTER_SECONDS,
    ) -> int:
        """Task WAITING pré-vinculada a runner OFFLINE/desativado/manutenção/bloqueado:
        após alguns minutos desfaz a pré-vinculação (runner_id=None) para outro runner assumir."""
        now = datetime.now(UTC)
        threshold = now - timedelta(seconds=unlink_after_seconds)

        stmt = (
            select(Task, Runner)
            .join(Runner, Runner.id == Task.runner_id)
            .where(Task.status == TaskStatus.WAITING)
            .where(Task.runner_id.is_not(None))
            .where(
                (Runner.enabled == False)
                | (Runner.status.in_([RunnerStatus.OFFLINE, RunnerStatus.MAINTENANCE]))
            )
        )

        total = 0
        for task, runner in self.db.execute(stmt).all():
            reference = as_aware(task.last_update_at) or as_aware(task.created_at)
            if reference is not None and reference > threshold:
                continue

            if not runner.enabled:
                state = "desativado"
            else:
                state = {
                    RunnerStatus.OFFLINE: "offline",
                    RunnerStatus.MAINTENANCE: "em manutenção",
                }.get(runner.status, "indisponível")

            task.runner_id = None
            task.last_update_at = now
            self.db.add(task)
            add_task_log(
                self.db,
                task.id,
                (
                    f"Sem runner online disponível: o runner '{runner.label or runner.name}' está {state} "
                    "há alguns minutos. A pré-vinculação foi desfeita e a task aguardará "
                    "o próximo runner elegível."
                ),
                level=TaskLogLevel.WARNING,
                source=TaskLogSource.SYSTEM,
                event_code="WATCHDOG_WAITING_UNLINKED",
                runner_id=runner.id,
            )
            total += 1

        if total:
            self.db.commit()
            logger.info("Watchdog desfez pré-vínculo de %s task(s) WAITING.", total)

        return total

    def requeue_stale_waiting_assignments(
        self,
        stale_after_seconds: int = WAITING_ASSIGNMENT_REQUEUE_AFTER_SECONDS,
    ) -> int:
        """Devolve à fila tasks WAITING pré-vinculadas a um runner que nunca as assumiu.

        Recurso do remoto (junho/2026), preservado: status continua WAITING, runner_id volta a
        NULL, só se runner_claimed_at é NULL e a task está sem atividade há mais de
        ``stale_after_seconds``. Não toca em task READY/RUNNING nem muda o status para erro.
        """
        now = datetime.now(UTC)
        threshold = now - timedelta(seconds=stale_after_seconds)

        stmt = (
            select(Task)
            .with_hint(Task, "WITH (UPDLOCK, ROWLOCK, READPAST)", "mssql")
            .where(Task.status == TaskStatus.WAITING)
            .where(Task.runner_id.is_not(None))
            .where(Task.runner_claimed_at.is_(None))
            .where((Task.last_update_at.is_(None)) | (Task.last_update_at < threshold))
            .order_by(Task.last_update_at.asc(), Task.id.asc())
        )

        tasks = list(self.db.execute(stmt).scalars().all())

        affected_runner_ids: set[int] = set()
        for task in tasks:
            if task.runner_id is not None:
                affected_runner_ids.add(task.runner_id)
            task.runner_id = None
            task.last_update_at = now
            self.db.add(task)

        for runner_id in affected_runner_ids:
            self._release_runner_if_possible(runner_id)

        if tasks:
            self.db.commit()

        return len(tasks)

    def fail_tasks_without_online_workers(self) -> int:
        """Nome mantido por compatibilidade com app/workers/watchdog_main.py.

        NÃO marca mais nenhuma task como ERROR. Agora apenas grava aviso (uma vez) quando
        não há runner online e desfaz pré-vínculo de WAITING em runner indisponível.
        """
        return self.warn_tasks_without_online_workers() + self.unlink_waiting_from_unavailable_runners()
