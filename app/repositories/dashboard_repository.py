from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.domain.enums import RunnerStatus, TaskStatus
from app.models.automation import Automation
from app.models.automation_runner import AutomationRunner
from app.models.bot import Bot
from app.models.bot_version import BotVersion
from app.models.runner import Runner
from app.models.task import Task


SUCCESS_STATUSES = {TaskStatus.FINISHED}
ERROR_STATUSES = {
    TaskStatus.ERROR,
    TaskStatus.TIMEOUT,
    TaskStatus.FORCED_STOP,
}
QUEUE_STATUSES = {
    TaskStatus.WAITING,
    TaskStatus.SCHEDULED,
    TaskStatus.READY,
}
ACTIVE_STATUSES = {
    TaskStatus.RUNNING,
    TaskStatus.STOP_REQUESTED,
}


class DashboardRepository:
    def __init__(self, db: Session):
        self.db = db

    def resolve_period_range(self, period: str) -> tuple[datetime, datetime]:
        now = datetime.now(UTC)

        mapping = {
            "1d": timedelta(days=1),
            "7d": timedelta(days=7),
            "15d": timedelta(days=15),
            "30d": timedelta(days=30),
        }

        delta = mapping.get(period, timedelta(days=1))
        date_from = now - delta
        date_to = now
        return date_from, date_to

    def _base_task_stmt(
        self,
        *,
        date_from: datetime,
        date_to: datetime,
        repository_id: int | None = None,
        runner_id: int | None = None,
        bot_id: int | None = None,
    ):
        stmt = (
            select(Task)
            .join(Automation, Automation.id == Task.automation_id)
            .join(Bot, Bot.id == Automation.bot_id)
            .options(
                selectinload(Task.automation).selectinload(Automation.bot),
                selectinload(Task.runner),
                selectinload(Task.bot_version),
            )
            .where(Task.created_at >= date_from)
            .where(Task.created_at <= date_to)
        )

        if repository_id is not None:
            stmt = stmt.where(Automation.repository_id == repository_id)

        if runner_id is not None:
            stmt = stmt.where(Task.runner_id == runner_id)

        if bot_id is not None:
            stmt = stmt.where(Automation.bot_id == bot_id)

        return stmt

    def list_tasks_in_period(
        self,
        *,
        date_from: datetime,
        date_to: datetime,
        repository_id: int | None = None,
        runner_id: int | None = None,
        bot_id: int | None = None,
    ) -> list[Task]:
        stmt = (
            self._base_task_stmt(
                date_from=date_from,
                date_to=date_to,
                repository_id=repository_id,
                runner_id=runner_id,
                bot_id=bot_id,
            )
            .order_by(Task.created_at.desc(), Task.id.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_recent_tasks(
        self,
        *,
        date_from: datetime,
        date_to: datetime,
        repository_id: int | None = None,
        runner_id: int | None = None,
        bot_id: int | None = None,
        limit: int = 20,
    ) -> list[Task]:
        stmt = (
            self._base_task_stmt(
                date_from=date_from,
                date_to=date_to,
                repository_id=repository_id,
                runner_id=runner_id,
                bot_id=bot_id,
            )
            .order_by(Task.created_at.desc(), Task.id.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_runners(self, *, enabled: bool | None = None) -> list[Runner]:
        stmt = select(Runner).order_by(Runner.name.asc())

        if enabled is not None:
            stmt = stmt.where(Runner.enabled == enabled)

        return list(self.db.execute(stmt).scalars().all())

    def list_bots(
        self,
        *,
        repository_id: int | None = None,
        active: bool | None = None,
    ) -> list[Bot]:
        stmt = select(Bot).order_by(Bot.name.asc())

        if repository_id is not None:
            stmt = stmt.where(Bot.repository_id == repository_id)

        if active is not None:
            stmt = stmt.where(Bot.active == active)

        return list(self.db.execute(stmt).scalars().all())

    def get_runner_linked_bots_map(
        self,
        *,
        repository_id: int | None = None,
    ) -> dict[int, list[dict[str, Any]]]:
        stmt = (
            select(
                AutomationRunner.runner_id.label("runner_id"),
                Bot.id.label("bot_id"),
                Bot.name.label("bot_name"),
            )
            .join(Automation, Automation.id == AutomationRunner.automation_id)
            .join(Bot, Bot.id == Automation.bot_id)
            .order_by(AutomationRunner.runner_id.asc(), Bot.name.asc())
        )

        if repository_id is not None:
            stmt = stmt.where(Automation.repository_id == repository_id)

        rows = self.db.execute(stmt).all()

        linked_map: dict[int, list[dict[str, Any]]] = defaultdict(list)
        seen: set[tuple[int, int]] = set()

        for row in rows:
            key = (row.runner_id, row.bot_id)
            if key in seen:
                continue
            seen.add(key)

            linked_map[row.runner_id].append(
                {
                    "bot_id": row.bot_id,
                    "bot_name": row.bot_name,
                }
            )

        return dict(linked_map)

    def get_bot_runners_map(
        self,
        *,
        repository_id: int | None = None,
    ) -> dict[int, list[dict[str, Any]]]:
        stmt = (
            select(
                Bot.id.label("bot_id"),
                Runner.id.label("runner_id"),
                Runner.name.label("runner_name"),
            )
            .select_from(AutomationRunner)
            .join(Automation, Automation.id == AutomationRunner.automation_id)
            .join(Bot, Bot.id == Automation.bot_id)
            .join(Runner, Runner.id == AutomationRunner.runner_id)
            .order_by(Bot.name.asc(), Runner.name.asc())
        )

        if repository_id is not None:
            stmt = stmt.where(Automation.repository_id == repository_id)

        rows = self.db.execute(stmt).all()

        bot_runners_map: dict[int, list[dict[str, Any]]] = defaultdict(list)
        seen: set[tuple[int, int]] = set()

        for row in rows:
            key = (row.bot_id, row.runner_id)
            if key in seen:
                continue
            seen.add(key)

            bot_runners_map[row.bot_id].append(
                {
                    "runner_id": row.runner_id,
                    "runner_name": row.runner_name,
                }
            )

        return dict(bot_runners_map)

    def get_latest_bot_versions_map(self, bot_ids: list[int]) -> dict[int, str | None]:
        if not bot_ids:
            return {}

        stmt = (
            select(
                BotVersion.bot_id,
                BotVersion.version,
            )
            .where(BotVersion.bot_id.in_(bot_ids))
            .order_by(
                BotVersion.bot_id.asc(),
                BotVersion.created_at.desc(),
                BotVersion.id.desc(),
            )
        )

        rows = self.db.execute(stmt).all()
        result: dict[int, str | None] = {}

        for row in rows:
            if row.bot_id not in result:
                result[row.bot_id] = row.version

        return result

    def count_runners(self) -> int:
        stmt = select(func.count(Runner.id))
        return int(self.db.execute(stmt).scalar_one() or 0)

    def count_bots(self, *, repository_id: int | None = None) -> int:
        stmt = select(func.count(Bot.id))

        if repository_id is not None:
            stmt = stmt.where(Bot.repository_id == repository_id)

        return int(self.db.execute(stmt).scalar_one() or 0)

    @staticmethod
    def calculate_task_counts(tasks: list[Task]) -> dict[str, int]:
        total_tasks = len(tasks)
        success_tasks = 0
        error_tasks = 0
        running_tasks = 0
        queued_tasks = 0

        for task in tasks:
            if task.status in SUCCESS_STATUSES:
                success_tasks += 1
            if task.status in ERROR_STATUSES:
                error_tasks += 1
            if task.status == TaskStatus.RUNNING:
                running_tasks += 1
            if task.status in QUEUE_STATUSES:
                queued_tasks += 1

        return {
            "total_tasks": total_tasks,
            "success_tasks": success_tasks,
            "error_tasks": error_tasks,
            "running_tasks": running_tasks,
            "queued_tasks": queued_tasks,
        }

    @staticmethod
    def calculate_avg_queue_seconds(tasks: list[Task]) -> float:
        durations: list[int] = []

        for task in tasks:
            if task.created_at and task.started_at:
                value = int((task.started_at - task.created_at).total_seconds())
                if value >= 0:
                    durations.append(value)

        if not durations:
            return 0.0

        return round(sum(durations) / len(durations), 2)

    @staticmethod
    def calculate_avg_execution_seconds(tasks: list[Task]) -> float:
        durations: list[int] = []
        now = datetime.now(UTC)

        for task in tasks:
            if task.started_at and task.finished_at:
                value = int((task.finished_at - task.started_at).total_seconds())
                if value >= 0:
                    durations.append(value)
            elif task.started_at and task.status == TaskStatus.RUNNING:
                value = int((now - task.started_at).total_seconds())
                if value >= 0:
                    durations.append(value)

        if not durations:
            return 0.0

        return round(sum(durations) / len(durations), 2)

    @staticmethod
    def calculate_execution_seconds(tasks: list[Task]) -> int:
        total = 0
        now = datetime.now(UTC)

        for task in tasks:
            if task.started_at and task.finished_at:
                value = int((task.finished_at - task.started_at).total_seconds())
                if value > 0:
                    total += value
            elif task.started_at and task.status == TaskStatus.RUNNING:
                value = int((now - task.started_at).total_seconds())
                if value > 0:
                    total += value

        return total

    @staticmethod
    def calculate_success_rate_percent(tasks: list[Task]) -> float:
        counts = DashboardRepository.calculate_task_counts(tasks)
        total = counts["total_tasks"]
        success = counts["success_tasks"]

        if total <= 0:
            return 0.0

        return round((success / total) * 100, 2)

    @staticmethod
    def group_tasks_per_hour(tasks: list[Task]) -> list[dict[str, Any]]:
        grouped: dict[str, dict[str, int]] = defaultdict(
            lambda: {
                "total_tasks": 0,
                "execution_seconds": 0,
            }
        )

        now = datetime.now(UTC)

        for task in tasks:
            hour_key = task.created_at.astimezone(UTC).strftime("%H:00")
            grouped[hour_key]["total_tasks"] += 1

            if task.started_at and task.finished_at:
                execution_seconds = int((task.finished_at - task.started_at).total_seconds())
                if execution_seconds > 0:
                    grouped[hour_key]["execution_seconds"] += execution_seconds
            elif task.started_at and task.status == TaskStatus.RUNNING:
                execution_seconds = int((now - task.started_at).total_seconds())
                if execution_seconds > 0:
                    grouped[hour_key]["execution_seconds"] += execution_seconds

        ordered = sorted(grouped.items(), key=lambda x: x[0])

        return [
            {
                "hour_label": key,
                "total_tasks": value["total_tasks"],
                "execution_seconds": value["execution_seconds"],
            }
            for key, value in ordered
        ]

    @staticmethod
    def get_hottest_hour(tasks: list[Task]) -> tuple[str | None, int]:
        per_hour = DashboardRepository.group_tasks_per_hour(tasks)
        if not per_hour:
            return None, 0

        hottest = max(per_hour, key=lambda x: x["total_tasks"])
        return hottest["hour_label"], hottest["total_tasks"]

    @staticmethod
    def get_last_execution(tasks: list[Task]) -> Task | None:
        execution_tasks = [t for t in tasks if t.started_at is not None]
        if not execution_tasks:
            return None

        execution_tasks.sort(
            key=lambda t: (
                t.started_at or datetime.min.replace(tzinfo=UTC),
                t.id,
            ),
            reverse=True,
        )
        return execution_tasks[0]

    @staticmethod
    def calculate_runner_display_status(runner: Runner, runner_tasks: list[Task]) -> str:
        if not runner.enabled:
            return RunnerStatus.OFFLINE.value

        has_running = any(task.status == TaskStatus.RUNNING for task in runner_tasks)
        if has_running:
            return RunnerStatus.BUSY.value

        if runner.status == RunnerStatus.BUSY:
            return RunnerStatus.ONLINE.value

        if hasattr(runner.status, "value"):
            return runner.status.value

        return str(runner.status)

    @staticmethod
    def calculate_runner_utilization_percent(
        *,
        runner: Runner,
        runner_tasks: list[Task],
        date_from: datetime,
        date_to: datetime,
    ) -> float:
        base_start = runner.created_at if runner.created_at > date_from else date_from
        base_end = date_to

        if base_end <= base_start:
            return 0.0

        available_seconds = int((base_end - base_start).total_seconds())
        if available_seconds <= 0:
            return 0.0

        execution_seconds = DashboardRepository.calculate_execution_seconds(runner_tasks)
        return round((execution_seconds / available_seconds) * 100, 2)

    @staticmethod
    def serialize_recent_task(task: Task) -> dict[str, Any]:
        queue_seconds = None
        execution_duration_seconds = None

        if task.created_at and task.started_at:
            value = int((task.started_at - task.created_at).total_seconds())
            if value >= 0:
                queue_seconds = value

        now = datetime.now(UTC)
        if task.started_at and task.finished_at:
            value = int((task.finished_at - task.started_at).total_seconds())
            if value >= 0:
                execution_duration_seconds = value
        elif task.started_at and task.status == TaskStatus.RUNNING:
            value = int((now - task.started_at).total_seconds())
            if value >= 0:
                execution_duration_seconds = value

        return {
            "task_id": task.id,
            "automation_id": task.automation_id,
            "automation_name": task.automation.name if task.automation else None,
            "bot_id": task.automation.bot_id if task.automation else None,
            "bot_name": task.automation.bot.name
            if task.automation and getattr(task.automation, "bot", None)
            else None,
            "runner_id": task.runner_id,
            "runner_name": task.runner.name if task.runner else None,
            "status": task.status,
            "created_at": task.created_at,
            "started_at": task.started_at,
            "finished_at": task.finished_at,
            "queue_seconds": queue_seconds,
            "execution_duration_seconds": execution_duration_seconds,
            "final_message": task.final_message,
        }
    