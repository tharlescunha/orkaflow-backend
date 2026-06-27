from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import RunnerStatus, TaskStatus
from app.models.runner import Runner
from app.models.task import Task
from app.repositories.automation_runner_repository import AutomationRunnerRepository
from app.repositories.runner_repository import RunnerRepository
from app.repositories.task_repository import TaskRepository


DISPATCH_BATCH_LIMIT = 500
DISPATCH_RUNNER_HEARTBEAT_MAX_AGE_SECONDS = 150


class DispatchService:
    """
    Distribui tasks WAITING para runners elegiveis.

    O dispatcher apenas pre-vincula runner_id. O worker ainda precisa chamar
    claim_task para transformar WAITING em READY de forma transacional.
    """

    def __init__(self, db: Session):
        self.db = db
        self.task_repo = TaskRepository(db)
        self.runner_repo = RunnerRepository(db)
        self.automation_runner_repo = AutomationRunnerRepository

    def dispatch_pending_tasks(self) -> int:
        waiting_tasks = self._list_dispatchable_waiting_tasks()
        dispatched = 0

        for task in waiting_tasks:
            existing_open = self.task_repo.get_open_task_for_automation(
                task.automation_id,
                exclude_task_id=task.id,
            )
            if existing_open:
                continue

            exclusive_conflict = self.task_repo.get_reserved_task_for_exclusive_groups(
                task.automation_id,
                exclude_task_id=task.id,
            )
            if exclusive_conflict:
                continue

            if self.task_repo.has_active_lock_for_exclusive_groups(task.automation_id):
                continue

            runner = self._find_best_runner_for_task(task)
            if not runner:
                continue

            self.task_repo.update(
                task,
                {
                    "runner_id": runner.id,
                    "last_update_at": datetime.now(UTC),
                    "dispatch_attempts": (task.dispatch_attempts or 0) + 1,
                },
            )
            dispatched += 1

        if dispatched:
            self.db.commit()

        return dispatched

    def _list_dispatchable_waiting_tasks(self) -> list[Task]:
        now = datetime.now(UTC)

        stmt = (
            select(Task)
            .with_hint(Task, "WITH (UPDLOCK, ROWLOCK, READPAST)", "mssql")
            .where(Task.status == TaskStatus.WAITING)
            .where(Task.runner_id.is_(None))
            .where((Task.requested_start_at.is_(None)) | (Task.requested_start_at <= now))
            .order_by(Task.priority.desc(), Task.id.asc())
            .limit(DISPATCH_BATCH_LIMIT)
        )

        return list(self.db.execute(stmt).scalars().all())

    def _find_best_runner_for_task(self, task: Task) -> Runner | None:
        links = self.automation_runner_repo.list_by_automation(
            self.db,
            task.automation_id,
        )
        if not links:
            return None

        eligible_runner_ids = {link.runner_id for link in links}
        available_runners = self.runner_repo.list_all(
            skip=0,
            limit=500,
            enabled=True,
        )

        candidates = [
            runner
            for runner in available_runners
            if runner.id in eligible_runner_ids
        ]

        for runner in self._rotate_candidates(candidates, task.id):
            if self._runner_can_receive_task(runner, task):
                return runner

        return None

    def _rotate_candidates(self, candidates: list[Runner], task_id: int) -> list[Runner]:
        if not candidates:
            return []

        ordered = sorted(candidates, key=lambda runner: runner.id)
        start_index = task_id % len(ordered)
        return ordered[start_index:] + ordered[:start_index]

    def _runner_can_receive_task(self, runner: Runner, task: Task) -> bool:
        if not runner.enabled:
            return False

        if runner.status != RunnerStatus.ONLINE:
            return False

        if not self._runner_has_fresh_heartbeat(runner):
            return False

        if not self.task_repo.automation_has_runner_link(
            task.automation_id,
            runner.id,
        ):
            return False

        if self.task_repo.count_open_for_runner(runner.id) > 0:
            return False

        return True

    def _runner_has_fresh_heartbeat(self, runner: Runner) -> bool:
        if runner.last_heartbeat is None:
            return False

        last_heartbeat = runner.last_heartbeat
        if last_heartbeat.tzinfo is None:
            last_heartbeat = last_heartbeat.replace(tzinfo=UTC)

        threshold = datetime.now(UTC) - timedelta(
            seconds=DISPATCH_RUNNER_HEARTBEAT_MAX_AGE_SECONDS
        )
        return last_heartbeat >= threshold
