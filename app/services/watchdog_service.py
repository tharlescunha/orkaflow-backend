from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.enums import RunnerStatus, TaskStatus
from app.models.runner import Runner
from app.models.task import Task
from app.repositories.lock_repository import LockRepository


class WatchdogService:
    def __init__(self, db: Session):
        self.db = db
        self.lock_repository = LockRepository(db)

    def mark_offline_runners(self, stale_after_seconds: int = 60) -> int:
        threshold = datetime.now(UTC) - timedelta(seconds=stale_after_seconds)
        now = datetime.now(UTC)

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
            runner.status = RunnerStatus.OFFLINE
            self.db.add(runner)

            if hasattr(self.lock_repository, "release_by_runner_id"):
                self.lock_repository.release_by_runner_id(runner.id, now)

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

    def mark_timed_out_tasks(self) -> int:
        now = datetime.now(UTC)

        stmt = (
            select(Task)
            .where(
                Task.status.in_([
                    TaskStatus.READY,
                    TaskStatus.RUNNING,
                    TaskStatus.STOP_REQUESTED,
                ])
            )
            .where(Task.started_at.is_not(None))
        )

        tasks = list(self.db.execute(stmt).scalars().all())

        total = 0
        for task in tasks:
            timeout_seconds = task.timeout_seconds or 3600
            deadline = task.started_at + timedelta(seconds=timeout_seconds)

            if now >= deadline:
                task.status = TaskStatus.TIMEOUT
                task.finished_at = now
                task.last_update_at = now
                task.final_message = task.final_message or "Task finalizada por timeout."
                self.db.add(task)
                self.lock_repository.release_by_task_id(task.id, now)
                total += 1

        if total:
            self.db.commit()

        return total

    def recover_orphan_tasks(self, stale_after_seconds: int = 120) -> int:
        now = datetime.now(UTC)
        threshold = now - timedelta(seconds=stale_after_seconds)

        stmt = (
            select(Task)
            .where(
                Task.status.in_([
                    TaskStatus.READY,
                    TaskStatus.RUNNING,
                    TaskStatus.STOP_REQUESTED,
                ])
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
                task.final_message = task.final_message or "Task órfã recuperada pelo watchdog."
                self.db.add(task)
                self.lock_repository.release_by_task_id(task.id, now)
                total += 1

        if total:
            self.db.commit()

        return total

    def fail_tasks_without_online_workers(self) -> int:
        now = datetime.now(UTC)

        online_stmt = (
            select(func.count(Runner.id))
            .where(Runner.status.in_([RunnerStatus.ONLINE, RunnerStatus.BUSY]))
        )
        online_count = int(self.db.execute(online_stmt).scalar_one())

        if online_count > 0:
            return 0

        stmt = (
            select(Task)
            .where(
                Task.status.in_([
                    TaskStatus.READY,
                    TaskStatus.RUNNING,
                    TaskStatus.STOP_REQUESTED,
                ])
            )
        )

        tasks = list(self.db.execute(stmt).scalars().all())

        total = 0
        for task in tasks:
            task.status = TaskStatus.ERROR
            task.finished_at = now
            task.last_update_at = now
            task.final_message = (
                task.final_message
                or "Task finalizada pelo watchdog: não existe worker online."
            )
            self.db.add(task)
            self.lock_repository.release_by_task_id(task.id, now)
            total += 1

        if total:
            self.db.commit()

        return total
    