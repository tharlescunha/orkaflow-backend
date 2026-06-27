from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.enums import RunnerStatus, TaskStatus
from app.models.runner import Runner
from app.models.runner_status_history import RunnerStatusHistory
from app.models.task import Task
from app.repositories.lock_repository import LockRepository


RUNNER_OFFLINE_AFTER_SECONDS = 180
WAITING_ASSIGNMENT_REQUEUE_AFTER_SECONDS = 180
ORPHAN_TASK_AFTER_SECONDS = 300
NO_WORKER_TASK_FAIL_AFTER_SECONDS = 900
READY_NOT_STARTED_AFTER_SECONDS = 300


class WatchdogService:
    def __init__(self, db: Session):
        self.db = db
        self.lock_repository = LockRepository(db)

    def _add_runner_status_history_if_needed(
        self,
        runner: Runner,
        new_status: RunnerStatus,
        reason: str | None = None,
    ):
        """
        Só adiciona histórico se o último status for diferente
        """

        last_status = (
            self.db.execute(
                select(RunnerStatusHistory)
                .where(RunnerStatusHistory.runner_id == runner.id)
                .order_by(RunnerStatusHistory.created_at.desc())
                .limit(1)
            )
            .scalars()
            .first()
        )

        if last_status and last_status.status == new_status.value:
            return

        history = RunnerStatusHistory(
            runner_id=runner.id,
            status=new_status.value,
            reason=reason,
        )

        self.db.add(history)

    def _release_task_locks(self, task: Task, now: datetime):
        """
        Libera locks da task.

        Importante:
        - NÃO remove runner_id da task.
        - runner_id precisa ficar para histórico, tela e auditoria.
        """

        self.lock_repository.release_by_task_id(task.id, now)

    def _runner_has_open_tasks(self, runner_id: int) -> bool:
        open_statuses = (
            TaskStatus.WAITING,
            TaskStatus.SCHEDULED,
            TaskStatus.READY,
            TaskStatus.RUNNING,
            TaskStatus.STOP_REQUESTED,
        )

        stmt = (
            select(func.count(Task.id))
            .where(Task.runner_id == runner_id)
            .where(Task.status.in_(open_statuses))
        )

        total = int(self.db.execute(stmt).scalar_one() or 0)
        return total > 0

    def _release_runner_if_possible(self, runner_id: int | None):
        """
        Libera runner BUSY para ONLINE se ele não tiver mais task aberta.

        Não altera runner:
        - OFFLINE
        - MAINTENANCE
        - BLOCKED
        - ONLINE
        """

        if runner_id is None:
            return

        runner = self.db.execute(
            select(Runner).where(Runner.id == runner_id)
        ).scalars().first()

        if not runner:
            return

        if runner.status != RunnerStatus.BUSY:
            return

        if self._runner_has_open_tasks(runner.id):
            return

        self._add_runner_status_history_if_needed(
            runner=runner,
            new_status=RunnerStatus.ONLINE,
            reason="runner_liberado_sem_tasks_abertas",
        )

        runner.status = RunnerStatus.ONLINE
        self.db.add(runner)

    def mark_offline_runners(self, stale_after_seconds: int = RUNNER_OFFLINE_AFTER_SECONDS) -> int:
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

        total = 0
        for runner in runners:
            self._add_runner_status_history_if_needed(
                runner=runner,
                new_status=RunnerStatus.OFFLINE,
                reason="heartbeat_timeout",
            )

            runner.status = RunnerStatus.OFFLINE
            self.db.add(runner)

            total += 1

        if total:
            self.db.commit()

        return total

    def release_expired_locks(self) -> int:
        now = datetime.now(UTC)
        locks = self.lock_repository.list_active_expired(now)

        for lock in locks:
            self.lock_repository.release(lock, now)

        if locks:
            self.db.commit()

        return len(locks)

    def requeue_stale_waiting_assignments(
        self,
        stale_after_seconds: int = WAITING_ASSIGNMENT_REQUEUE_AFTER_SECONDS,
    ) -> int:
        """
        Devolve para a fila tasks WAITING que foram pre-vinculadas a um runner,
        mas nunca foram assumidas pelo worker.

        Regra:
        - status continua WAITING
        - runner_id volta para NULL
        - runner_claimed_at precisa estar NULL
        - nao altera task que ja foi para READY/RUNNING
        """

        now = datetime.now(UTC)
        threshold = now - timedelta(seconds=stale_after_seconds)

        stmt = (
            select(Task)
            .with_hint(Task, "WITH (UPDLOCK, ROWLOCK, READPAST)", "mssql")
            .where(Task.status == TaskStatus.WAITING)
            .where(Task.runner_id.is_not(None))
            .where(Task.runner_claimed_at.is_(None))
            .where(
                (Task.last_update_at.is_(None))
                | (Task.last_update_at < threshold)
            )
            .order_by(Task.last_update_at.asc(), Task.id.asc())
        )

        tasks = list(self.db.execute(stmt).scalars().all())

        total = 0
        affected_runner_ids: set[int] = set()

        for task in tasks:
            if task.runner_id is not None:
                affected_runner_ids.add(task.runner_id)

            task.runner_id = None
            task.last_update_at = now
            self.db.add(task)
            total += 1

        for runner_id in affected_runner_ids:
            self._release_runner_if_possible(runner_id)

        if total:
            self.db.commit()

        return total

    def mark_timed_out_tasks(self) -> int:
        """
        Finaliza tasks que passaram do timeout configurado.

        Regra:
        - usa task.timeout_seconds
        - se task.timeout_seconds não existir, usa 3600
        - status vai para TIMEOUT
        - stop_requested fica True para o worker parar se ainda estiver vivo
        - locks da task são liberados
        - runner BUSY volta para ONLINE se não tiver mais task aberta
        """

        now = datetime.now(UTC)

        stmt = (
            select(Task)
            .where(
                Task.status.in_(
                    [
                        TaskStatus.READY,
                        TaskStatus.RUNNING,
                        TaskStatus.STOP_REQUESTED,
                    ]
                )
            )
            .where(Task.started_at.is_not(None))
        )

        tasks = list(self.db.execute(stmt).scalars().all())

        total = 0
        for task in tasks:
            timeout_seconds = task.timeout_seconds or 3600
            deadline = task.started_at + timedelta(seconds=timeout_seconds)

            if now < deadline:
                continue

            task.status = TaskStatus.TIMEOUT
            task.finished_at = now
            task.last_update_at = now
            task.stop_requested = True
            task.final_message = task.final_message or "Task cancelada por timeout do bot."

            self.db.add(task)
            self._release_task_locks(task, now)
            self._release_runner_if_possible(task.runner_id)

            total += 1

        if total:
            self.db.commit()

        return total

    def fail_ready_tasks_not_started(
        self,
        stale_after_seconds: int = READY_NOT_STARTED_AFTER_SECONDS,
    ) -> int:
        """
        Finaliza tasks que foram assumidas pelo worker, mas nunca chegaram a RUNNING.

        Isso cobre falha entre claim_task e inicio real do processo local.
        Nao reenvia automaticamente para evitar duplicidade operacional.
        """

        now = datetime.now(UTC)
        threshold = now - timedelta(seconds=stale_after_seconds)

        stmt = (
            select(Task)
            .with_hint(Task, "WITH (UPDLOCK, ROWLOCK, READPAST)", "mssql")
            .where(Task.status == TaskStatus.READY)
            .where(Task.started_at.is_(None))
            .where(Task.runner_claimed_at.is_not(None))
            .where(
                (Task.last_update_at.is_(None))
                | (Task.last_update_at < threshold)
            )
        )

        tasks = list(self.db.execute(stmt).scalars().all())

        total = 0
        for task in tasks:
            runner_id = task.runner_id

            task.status = TaskStatus.ERROR
            task.finished_at = now
            task.last_update_at = now
            task.stop_requested = True
            task.final_message = (
                task.final_message
                or "Task falhou pelo watchdog: assumida pelo worker, mas nao iniciou."
            )

            self.db.add(task)
            self._release_task_locks(task, now)
            self._release_runner_if_possible(runner_id)
            total += 1

        if total:
            self.db.commit()

        return total

    def recover_orphan_tasks(self, stale_after_seconds: int = ORPHAN_TASK_AFTER_SECONDS) -> int:
        now = datetime.now(UTC)
        threshold = now - timedelta(seconds=stale_after_seconds)

        stmt = (
            select(Task)
            .where(
                Task.status.in_(
                    [
                        TaskStatus.READY,
                        TaskStatus.RUNNING,
                        TaskStatus.STOP_REQUESTED,
                    ]
                )
            )
        )

        tasks = list(self.db.execute(stmt).scalars().all())

        total = 0
        for task in tasks:
            runner = None
            if task.runner_id is not None:
                runner = self.db.execute(
                    select(Runner).where(Runner.id == task.runner_id)
                ).scalars().first()

            runner_stale = (
                runner is None
                or runner.status == RunnerStatus.OFFLINE
                or runner.last_heartbeat is None
                or runner.last_heartbeat < threshold
            )

            task_stale = (
                task.last_update_at is None
                or task.last_update_at < threshold
            )

            if runner_stale and task_stale:
                task.status = TaskStatus.ERROR
                task.finished_at = now
                task.last_update_at = now
                task.stop_requested = True
                task.final_message = task.final_message or "Task órfã recuperada pelo watchdog."

                self.db.add(task)
                self._release_task_locks(task, now)
                self._release_runner_if_possible(task.runner_id)

                total += 1

        if total:
            self.db.commit()

        return total

    def fail_tasks_without_online_workers(
        self,
        stale_after_seconds: int = NO_WORKER_TASK_FAIL_AFTER_SECONDS,
    ) -> int:
        now = datetime.now(UTC)
        threshold = now - timedelta(seconds=stale_after_seconds)

        online_stmt = (
            select(func.count(Runner.id))
            .where(Runner.enabled == True)
            .where(Runner.status.in_([RunnerStatus.ONLINE, RunnerStatus.BUSY]))
        )
        online_count = int(self.db.execute(online_stmt).scalar_one() or 0)

        if online_count > 0:
            return 0

        stmt = (
            select(Task)
            .where(
                Task.status.in_(
                    [
                        TaskStatus.READY,
                        TaskStatus.RUNNING,
                        TaskStatus.STOP_REQUESTED,
                    ]
                )
            )
            .where(
                (Task.last_update_at.is_(None))
                | (Task.last_update_at < threshold)
            )
        )

        tasks = list(self.db.execute(stmt).scalars().all())

        total = 0
        for task in tasks:
            task.status = TaskStatus.ERROR
            task.finished_at = now
            task.last_update_at = now
            task.stop_requested = True
            task.final_message = (
                task.final_message
                or "Task finalizada pelo watchdog: não existe worker online."
            )

            self.db.add(task)
            self._release_task_locks(task, now)
            self._release_runner_if_possible(task.runner_id)

            total += 1

        if total:
            self.db.commit()

        return total
