from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime

from app.repositories.dashboard_repository import DashboardRepository
from app.schemas.dashboard import (
    DashboardBotMachineRef,
    DashboardBotMetrics,
    DashboardBotsResponse,
    DashboardOverviewResponse,
    DashboardOverviewSummary,
    DashboardRecentTaskItem,
    DashboardRunnerBotRef,
    DashboardRunnerLastExecution,
    DashboardRunnerMetrics,
    DashboardRunnersResponse,
    DashboardTasksPerHourItem,
)


class DashboardService:
    def __init__(self, db):
        self.repo = DashboardRepository(db)

    def _get_period_range(self, period: str) -> tuple[datetime, datetime]:
        return self.repo.resolve_period_range(period)

    def get_overview(
        self,
        *,
        period: str = "1d",
        repository_id: int | None = None,
        runner_id: int | None = None,
        bot_id: int | None = None,
    ) -> DashboardOverviewResponse:
        date_from, date_to = self._get_period_range(period)

        tasks = self.repo.list_tasks_in_period(
            date_from=date_from,
            date_to=date_to,
            repository_id=repository_id,
            runner_id=runner_id,
            bot_id=bot_id,
        )
        recent_tasks = self.repo.list_recent_tasks(
            date_from=date_from,
            date_to=date_to,
            repository_id=repository_id,
            runner_id=runner_id,
            bot_id=bot_id,
            limit=20,
        )

        runners = self.repo.list_runners()
        if runner_id is not None:
            runners = [runner for runner in runners if runner.id == runner_id]

        if repository_id is not None:
            runner_links = self.repo.get_runner_linked_bots_map(repository_id=repository_id)
            runner_ids_from_repo = set(runner_links.keys())
            runners = [runner for runner in runners if runner.id in runner_ids_from_repo]

        total_runners = len(runners)
        online_runners = 0
        offline_runners = 0
        busy_runners = 0

        tasks_by_runner: dict[int | None, list] = defaultdict(list)
        for task in tasks:
            tasks_by_runner[task.runner_id].append(task)

        for runner in runners:
            display_status = self.repo.calculate_runner_display_status(
                runner,
                tasks_by_runner.get(runner.id, []),
            )

            if display_status == "busy":
                busy_runners += 1
            elif display_status == "online":
                online_runners += 1
            else:
                offline_runners += 1

        task_counts = self.repo.calculate_task_counts(tasks)
        avg_queue_seconds = self.repo.calculate_avg_queue_seconds(tasks)
        avg_execution_seconds = self.repo.calculate_avg_execution_seconds(tasks)
        success_rate_percent = self.repo.calculate_success_rate_percent(tasks)

        total_bots = self.repo.count_bots(repository_id=repository_id)

        tasks_per_hour = [
            DashboardTasksPerHourItem.model_validate(item)
            for item in self.repo.group_tasks_per_hour(tasks)
        ]

        recent_task_items = [
            DashboardRecentTaskItem.model_validate(self.repo.serialize_recent_task(task))
            for task in recent_tasks
        ]

        summary = DashboardOverviewSummary(
            total_runners=total_runners,
            online_runners=online_runners,
            offline_runners=offline_runners,
            busy_runners=busy_runners,
            total_bots=total_bots,
            total_tasks=task_counts["total_tasks"],
            success_tasks=task_counts["success_tasks"],
            error_tasks=task_counts["error_tasks"],
            running_tasks=task_counts["running_tasks"],
            queued_tasks=task_counts["queued_tasks"],
            success_rate_percent=success_rate_percent,
            avg_queue_seconds=avg_queue_seconds,
            avg_execution_seconds=avg_execution_seconds,
        )

        return DashboardOverviewResponse(
            period=period,
            date_from=date_from,
            date_to=date_to,
            summary=summary,
            tasks_per_hour=tasks_per_hour,
            recent_tasks=recent_task_items,
        )

    def get_runners_metrics(
        self,
        *,
        period: str = "1d",
        repository_id: int | None = None,
        runner_id: int | None = None,
        bot_id: int | None = None,
    ) -> DashboardRunnersResponse:
        date_from, date_to = self._get_period_range(period)

        tasks = self.repo.list_tasks_in_period(
            date_from=date_from,
            date_to=date_to,
            repository_id=repository_id,
            runner_id=runner_id,
            bot_id=bot_id,
        )

        runners = self.repo.list_runners()
        if runner_id is not None:
            runners = [runner for runner in runners if runner.id == runner_id]

        linked_bots_map = self.repo.get_runner_linked_bots_map(repository_id=repository_id)

        if repository_id is not None:
            runner_ids_from_repo = set(linked_bots_map.keys())
            runners = [runner for runner in runners if runner.id in runner_ids_from_repo]

        tasks_by_runner: dict[int | None, list] = defaultdict(list)
        for task in tasks:
            tasks_by_runner[task.runner_id].append(task)

        items: list[DashboardRunnerMetrics] = []

        for runner in runners:
            runner_tasks = tasks_by_runner.get(runner.id, [])
            task_counts = self.repo.calculate_task_counts(runner_tasks)
            avg_queue_seconds = self.repo.calculate_avg_queue_seconds(runner_tasks)
            avg_execution_seconds = self.repo.calculate_avg_execution_seconds(runner_tasks)
            utilization_percent = self.repo.calculate_runner_utilization_percent(
                runner=runner,
                runner_tasks=runner_tasks,
                date_from=date_from,
                date_to=date_to,
            )
            hottest_hour_label, hottest_hour_tasks = self.repo.get_hottest_hour(runner_tasks)
            last_execution_task = self.repo.get_last_execution(runner_tasks)
            display_status = self.repo.calculate_runner_display_status(runner, runner_tasks)

            last_execution = None
            if last_execution_task:
                execution_duration_seconds = None
                now = datetime.now(UTC)

                if last_execution_task.started_at and last_execution_task.finished_at:
                    execution_duration_seconds = int(
                        (last_execution_task.finished_at - last_execution_task.started_at).total_seconds()
                    )
                elif (
                    last_execution_task.started_at
                    and hasattr(last_execution_task.status, "value")
                    and last_execution_task.status.value == "running"
                ):
                    execution_duration_seconds = int(
                        (now - last_execution_task.started_at).total_seconds()
                    )

                last_execution = DashboardRunnerLastExecution(
                    task_id=last_execution_task.id,
                    automation_id=last_execution_task.automation_id,
                    automation_name=last_execution_task.automation.name
                    if last_execution_task.automation
                    else None,
                    status=last_execution_task.status,
                    started_at=last_execution_task.started_at,
                    finished_at=last_execution_task.finished_at,
                    execution_duration_seconds=execution_duration_seconds,
                    final_message=last_execution_task.final_message,
                )

            linked_bots = [
                DashboardRunnerBotRef.model_validate(item)
                for item in linked_bots_map.get(runner.id, [])
            ]

            items.append(
                DashboardRunnerMetrics(
                    runner_id=runner.id,
                    runner_name=runner.name,
                    runner_label=runner.label,
                    status=display_status,
                    enabled=runner.enabled,
                    last_heartbeat=runner.last_heartbeat,
                    linked_bots_count=len(linked_bots),
                    linked_bots=linked_bots,
                    total_tasks=task_counts["total_tasks"],
                    success_tasks=task_counts["success_tasks"],
                    error_tasks=task_counts["error_tasks"],
                    running_tasks=task_counts["running_tasks"],
                    queued_tasks=task_counts["queued_tasks"],
                    utilization_percent=utilization_percent,
                    avg_queue_seconds=avg_queue_seconds,
                    avg_execution_seconds=avg_execution_seconds,
                    hottest_hour_label=hottest_hour_label,
                    hottest_hour_tasks=hottest_hour_tasks,
                    last_execution=last_execution,
                )
            )

        items.sort(
            key=lambda x: (
                -x.utilization_percent,
                -x.total_tasks,
                x.runner_name.lower(),
            )
        )

        return DashboardRunnersResponse(
            period=period,
            date_from=date_from,
            date_to=date_to,
            items=items,
            total=len(items),
        )

    def get_bots_metrics(
        self,
        *,
        period: str = "1d",
        repository_id: int | None = None,
        runner_id: int | None = None,
        bot_id: int | None = None,
    ) -> DashboardBotsResponse:
        date_from, date_to = self._get_period_range(period)

        tasks = self.repo.list_tasks_in_period(
            date_from=date_from,
            date_to=date_to,
            repository_id=repository_id,
            runner_id=runner_id,
            bot_id=bot_id,
        )

        bots = self.repo.list_bots(
            repository_id=repository_id,
            active=None,
        )
        if bot_id is not None:
            bots = [bot for bot in bots if bot.id == bot_id]

        bot_runners_map = self.repo.get_bot_runners_map(repository_id=repository_id)
        latest_versions_map = self.repo.get_latest_bot_versions_map([bot.id for bot in bots])

        tasks_by_bot: dict[int, list] = defaultdict(list)
        for task in tasks:
            if task.automation and task.automation.bot_id:
                tasks_by_bot[task.automation.bot_id].append(task)

        items: list[DashboardBotMetrics] = []

        for bot in bots:
            bot_tasks = tasks_by_bot.get(bot.id, [])
            task_counts = self.repo.calculate_task_counts(bot_tasks)
            avg_queue_seconds = self.repo.calculate_avg_queue_seconds(bot_tasks)
            avg_execution_seconds = self.repo.calculate_avg_execution_seconds(bot_tasks)
            success_rate_percent = self.repo.calculate_success_rate_percent(bot_tasks)
            last_execution_task = self.repo.get_last_execution(bot_tasks)

            last_execution_status = None
            last_execution_at = None

            if last_execution_task:
                last_execution_status = last_execution_task.status
                last_execution_at = (
                    last_execution_task.started_at
                    or last_execution_task.created_at
                )

            runners = [
                DashboardBotMachineRef.model_validate(item)
                for item in bot_runners_map.get(bot.id, [])
            ]

            execution_mode = (
                bot.execution_mode.value
                if hasattr(bot.execution_mode, "value")
                else bot.execution_mode
            )

            items.append(
                DashboardBotMetrics(
                    bot_id=bot.id,
                    bot_name=bot.name,
                    execution_mode=execution_mode,
                    current_version=latest_versions_map.get(bot.id) or bot.current_version,
                    active=bot.active,
                    total_tasks=task_counts["total_tasks"],
                    success_tasks=task_counts["success_tasks"],
                    error_tasks=task_counts["error_tasks"],
                    running_tasks=task_counts["running_tasks"],
                    queued_tasks=task_counts["queued_tasks"],
                    avg_queue_seconds=avg_queue_seconds,
                    avg_execution_seconds=avg_execution_seconds,
                    success_rate_percent=success_rate_percent,
                    runners=runners,
                    last_execution_status=last_execution_status,
                    last_execution_at=last_execution_at,
                )
            )

        items.sort(
            key=lambda x: (
                -x.total_tasks,
                -x.success_rate_percent,
                x.bot_name.lower(),
            )
        )

        return DashboardBotsResponse(
            period=period,
            date_from=date_from,
            date_to=date_to,
            items=items,
            total=len(items),
        )
    