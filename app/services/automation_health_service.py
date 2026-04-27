from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from croniter import croniter
from sqlalchemy.orm import Session, joinedload

from app.domain.enums import (
    CalendarType,
    ScheduleStatus,
    ScheduleType,
    TaskStatus,
)
from app.models.automation import Automation
from app.models.runner import Runner
from app.models.schedule import Schedule
from app.models.task import Task


FINAL_SUCCESS_STATUSES = {
    TaskStatus.FINISHED,
}

FINAL_ERROR_STATUSES = {
    TaskStatus.ERROR,
    TaskStatus.TIMEOUT,
    TaskStatus.FORCED_STOP,
    TaskStatus.CANCELED,
}

RUNNING_STATUSES = {
    TaskStatus.RUNNING,
    TaskStatus.STOP_REQUESTED,
    TaskStatus.READY,
}


@dataclass
class ExpectedWindowResult:
    expected_interval_seconds: int | None
    rule_label: str | None
    reference_time: datetime | None
    is_overdue: bool


class AutomationHealthService:
    @staticmethod
    def list(
        db: Session,
        *,
        repository_id: int | None = None,
        bot_id: int | None = None,
        active: bool | None = True,
    ) -> dict:
        automations = (
            db.query(Automation)
            .options(
                joinedload(Automation.repository),
                joinedload(Automation.bot),
            )
            .order_by(Automation.name.asc())
        )

        if repository_id is not None:
            automations = automations.filter(Automation.repository_id == repository_id)

        if bot_id is not None:
            automations = automations.filter(Automation.bot_id == bot_id)

        if active is not None:
            automations = automations.filter(Automation.active == active)

        automation_items = automations.all()

        automation_ids = [item.id for item in automation_items]
        if not automation_ids:
            return {"items": [], "total": 0}

        schedules = AutomationHealthService._load_schedules(db, automation_ids)
        last_tasks = AutomationHealthService._load_last_tasks(db, automation_ids)

        schedule_map = AutomationHealthService._build_schedule_map(schedules)
        task_map = {task.automation_id: task for task in last_tasks if task.automation_id is not None}

        now_utc = datetime.now(UTC)

        items = []
        for automation in automation_items:
            schedule = schedule_map.get(automation.id)
            task = task_map.get(automation.id)

            expected_window = AutomationHealthService._calculate_expected_window(
                schedule=schedule,
                task=task,
                now_utc=now_utc,
            )

            health_status, health_label, status_color = AutomationHealthService._resolve_health_status(
                task=task,
                expected_window=expected_window,
            )

            last_execution_at = AutomationHealthService._get_last_execution_at(task, schedule)

            machine_name = None
            machine_label = None
            machine_display_name = None
            if task and task.runner:
                machine_name = task.runner.name
                machine_label = task.runner.label
                machine_display_name = task.runner.label or task.runner.name

            items.append(
                {
                    "automation_id": automation.id,
                    "automation_name": automation.name,
                    "automation_label": automation.label,
                    "automation_description": automation.description,
                    "automation_active": automation.active,
                    "repository_id": automation.repository_id,
                    "repository_name": automation.repository.name if automation.repository else None,
                    "bot_id": automation.bot_id,
                    "bot_name": automation.bot.name if automation.bot else None,
                    "bot_active": automation.bot.active if automation.bot else None,
                    "health_status": health_status,
                    "health_label": health_label,
                    "status_color": status_color,
                    "monitored_at": now_utc,
                    "last_execution_at": last_execution_at,
                    "is_overdue": expected_window.is_overdue,
                    "has_recent_success": task is not None and task.status in FINAL_SUCCESS_STATUSES and not expected_window.is_overdue,
                    "has_recent_error": task is not None and task.status in FINAL_ERROR_STATUSES,
                    "has_running_task": task is not None and task.status in RUNNING_STATUSES,
                    "machine_name": machine_name,
                    "machine_label": machine_label,
                    "machine_display_name": machine_display_name,
                    "schedule": AutomationHealthService._serialize_schedule(
                        schedule=schedule,
                        expected_interval_seconds=expected_window.expected_interval_seconds,
                        rule_label=expected_window.rule_label,
                    ),
                    "last_task": AutomationHealthService._serialize_task(task),
                }
            )

        return {
            "items": items,
            "total": len(items),
        }

    @staticmethod
    def _load_schedules(db: Session, automation_ids: list[int]) -> list[Schedule]:
        return (
            db.query(Schedule)
            .filter(Schedule.automation_id.in_(automation_ids))
            .order_by(
                Schedule.automation_id.asc(),
                Schedule.active.desc(),
                Schedule.id.desc(),
            )
            .all()
        )

    @staticmethod
    def _load_last_tasks(db: Session, automation_ids: list[int]) -> list[Task]:
        tasks = (
            db.query(Task)
            .options(joinedload(Task.runner))
            .filter(Task.automation_id.in_(automation_ids))
            .order_by(
                Task.automation_id.asc(),
                Task.created_at.desc(),
                Task.id.desc(),
            )
            .all()
        )

        latest_by_automation: dict[int, Task] = {}
        for task in tasks:
            if task.automation_id not in latest_by_automation:
                latest_by_automation[task.automation_id] = task

        return list(latest_by_automation.values())

    @staticmethod
    def _build_schedule_map(schedules: list[Schedule]) -> dict[int, Schedule]:
        schedule_map: dict[int, Schedule] = {}

        for schedule in schedules:
            if schedule.automation_id in schedule_map:
                continue

            schedule_map[schedule.automation_id] = schedule

        return schedule_map

    @staticmethod
    def _calculate_expected_window(
        *,
        schedule: Schedule | None,
        task: Task | None,
        now_utc: datetime,
    ) -> ExpectedWindowResult:
        if not schedule:
            return ExpectedWindowResult(
                expected_interval_seconds=None,
                rule_label="No schedule",
                reference_time=None,
                is_overdue=True,
            )

        if not schedule.active or schedule.status in {ScheduleStatus.INACTIVE, ScheduleStatus.PAUSED}:
            return ExpectedWindowResult(
                expected_interval_seconds=None,
                rule_label="Inactive schedule",
                reference_time=None,
                is_overdue=False,
            )

        expected_interval_seconds = AutomationHealthService._get_expected_interval_seconds(schedule, now_utc)
        rule_label = AutomationHealthService._build_rule_label(schedule, expected_interval_seconds)

        last_reference_time = AutomationHealthService._get_reference_time(task, schedule)

        if expected_interval_seconds is None:
            return ExpectedWindowResult(
                expected_interval_seconds=None,
                rule_label=rule_label,
                reference_time=last_reference_time,
                is_overdue=task is None,
            )

        if last_reference_time is None:
            return ExpectedWindowResult(
                expected_interval_seconds=expected_interval_seconds,
                rule_label=rule_label,
                reference_time=None,
                is_overdue=True,
            )

        elapsed_seconds = max(0, int((now_utc - last_reference_time.astimezone(UTC)).total_seconds()))
        is_overdue = elapsed_seconds > expected_interval_seconds

        return ExpectedWindowResult(
            expected_interval_seconds=expected_interval_seconds,
            rule_label=rule_label,
            reference_time=last_reference_time,
            is_overdue=is_overdue,
        )

    @staticmethod
    def _get_reference_time(task: Task | None, schedule: Schedule | None) -> datetime | None:
        if task:
            return (
                task.finished_at
                or task.last_update_at
                or task.started_at
                or task.created_at
            )

        if schedule:
            return schedule.last_run_at

        return None

    @staticmethod
    def _get_last_execution_at(task: Task | None, schedule: Schedule | None) -> datetime | None:
        reference_time = AutomationHealthService._get_reference_time(task, schedule)
        return reference_time

    @staticmethod
    def _get_expected_interval_seconds(schedule: Schedule, now_utc: datetime) -> int | None:
        if schedule.schedule_type == ScheduleType.CALENDAR:
            return AutomationHealthService._get_calendar_interval_seconds(schedule)

        if schedule.schedule_type == ScheduleType.CRON:
            return AutomationHealthService._get_cron_interval_seconds(schedule, now_utc)

        return None

    @staticmethod
    def _get_calendar_interval_seconds(schedule: Schedule) -> int | None:
        if schedule.calendar_type == CalendarType.ONCE:
            return None

        if not schedule.interval_value:
            return None

        multiplier_map = {
            CalendarType.SECOND: 1,
            CalendarType.MINUTE: 60,
            CalendarType.HOUR: 3600,
            CalendarType.DAY: 86400,
            CalendarType.WEEK: 604800,
            CalendarType.MONTH: 2592000,
        }

        multiplier = multiplier_map.get(schedule.calendar_type)
        if multiplier is None:
            return None

        return int(schedule.interval_value) * multiplier

    @staticmethod
    def _get_cron_interval_seconds(schedule: Schedule, now_utc: datetime) -> int | None:
        if not schedule.cron_expression:
            return None

        try:
            tz = ZoneInfo(schedule.timezone or "UTC")
        except Exception:
            tz = UTC

        base_time = now_utc.astimezone(tz)
        itr = croniter(schedule.cron_expression, base_time)
        next_run = itr.get_next(datetime)
        next_next_run = itr.get_next(datetime)

        interval = int((next_next_run - next_run).total_seconds())
        return interval if interval > 0 else None

    @staticmethod
    def _build_rule_label(schedule: Schedule, expected_interval_seconds: int | None) -> str | None:
        if schedule.schedule_type == ScheduleType.CALENDAR:
            if schedule.calendar_type == CalendarType.ONCE:
                return "Once"

            if schedule.interval_value and schedule.interval_unit:
                return f"Every {schedule.interval_value} {schedule.interval_unit}"

            if schedule.interval_value and schedule.calendar_type:
                return f"Every {schedule.interval_value} {schedule.calendar_type.value}"

            return "Calendar"

        if schedule.schedule_type == ScheduleType.CRON:
            if expected_interval_seconds is not None:
                return f"Cron ~ every {AutomationHealthService._format_seconds(expected_interval_seconds)}"
            return "Cron"

        return None

    @staticmethod
    def _resolve_health_status(
        *,
        task: Task | None,
        expected_window: ExpectedWindowResult,
    ) -> tuple[str, str, str]:
        if task and task.status in FINAL_ERROR_STATUSES:
            return "error", "Error", "red"

        if task and task.status in RUNNING_STATUSES:
            return "running", "Running", "green_soft"

        if expected_window.is_overdue:
            return "warning", "Warning", "yellow"

        if task and task.status in FINAL_SUCCESS_STATUSES:
            return "success", "Success", "green"

        return "warning", "Warning", "yellow"

    @staticmethod
    def _serialize_schedule(
        *,
        schedule: Schedule | None,
        expected_interval_seconds: int | None,
        rule_label: str | None,
    ) -> dict | None:
        if not schedule:
            return None

        return {
            "id": schedule.id,
            "name": schedule.name,
            "schedule_type": schedule.schedule_type.value if hasattr(schedule.schedule_type, "value") else str(schedule.schedule_type),
            "calendar_type": schedule.calendar_type.value if schedule.calendar_type and hasattr(schedule.calendar_type, "value") else (str(schedule.calendar_type) if schedule.calendar_type else None),
            "cron_expression": schedule.cron_expression,
            "interval_value": schedule.interval_value,
            "interval_unit": schedule.interval_unit,
            "timezone": schedule.timezone,
            "active": schedule.active,
            "status": schedule.status.value if hasattr(schedule.status, "value") else (str(schedule.status) if schedule.status else None),
            "last_run_at": schedule.last_run_at,
            "next_run_at": schedule.next_run_at,
            "expected_interval_seconds": expected_interval_seconds,
            "rule_label": rule_label,
        }

    @staticmethod
    def _serialize_task(task: Task | None) -> dict | None:
        if not task:
            return None

        runner_name = None
        runner_label = None
        runner_display_name = None

        if task.runner:
            runner_name = task.runner.name
            runner_label = task.runner.label
            runner_display_name = task.runner.label or task.runner.name

        return {
            "id": task.id,
            "status": task.status.value if hasattr(task.status, "value") else str(task.status),
            "runner_id": task.runner_id,
            "runner_name": runner_name,
            "runner_label": runner_label,
            "runner_display_name": runner_display_name,
            "started_at": task.started_at,
            "finished_at": task.finished_at,
            "last_update_at": task.last_update_at,
            "final_message": task.final_message,
            "execution_duration_seconds": AutomationHealthService._calculate_execution_duration_seconds(task),
        }

    @staticmethod
    def _calculate_execution_duration_seconds(task: Task) -> int | None:
        if task.started_at and task.finished_at:
            return int((task.finished_at - task.started_at).total_seconds())

        if task.started_at and task.status in RUNNING_STATUSES:
            return int((datetime.now(UTC) - task.started_at.astimezone(UTC)).total_seconds())

        return None

    @staticmethod
    def _format_seconds(value: int) -> str:
        if value < 60:
            return f"{value}s"

        if value < 3600:
            minutes = value // 60
            return f"{minutes}m"

        if value < 86400:
            hours = value // 3600
            return f"{hours}h"

        days = value // 86400
        return f"{days}d"
    