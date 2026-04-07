from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.enums import (
    CalendarType,
    ExecutionMode,
    SchedulePolicy,
    ScheduleStatus,
    ScheduleType,
    TaskStatus,
)
from app.models.schedule import Schedule
from app.models.task import Task
from app.repositories.task_repository import TaskRepository

import json

try:
    from croniter import CroniterBadCronError, croniter
except ImportError:  # pragma: no cover
    croniter = None
    CroniterBadCronError = Exception


class SchedulerEngineService:
    """
    Engine avançada de schedules.

    Responsabilidades:
    - Ler schedules ativos
    - Calcular próxima execução com timezone
    - Interpretar cron real
    - Aplicar misfire policy
    - Evitar duplicidade conforme policy
    - Criar tasks automaticamente
    - Atualizar last_run_at / next_run_at
    """

    MISFIRE_GRACE_SECONDS = 60
    MAX_BACKFILL_OCCURRENCES = 100

    def __init__(self, db: Session):
        self.db = db
        self.task_repo = TaskRepository(db)

    def process_schedules(self) -> int:
        now_utc = datetime.now(UTC)

        stmt = (
            select(Schedule)
            .where(Schedule.active == True)
            .where(Schedule.status == ScheduleStatus.ACTIVE)
            .order_by(Schedule.id.asc())
        )

        schedules = list(self.db.execute(stmt).scalars().all())
        created_tasks = 0

        for schedule in schedules:
            try:
                schedule_created = self._process_single_schedule(
                    schedule=schedule,
                    now_utc=now_utc,
                )
                created_tasks += schedule_created
            except Exception as exc:
                self.db.rollback()
                schedule.status = ScheduleStatus.ERROR
                self.db.add(schedule)
                self.db.commit()
                print(f"[SCHEDULER_ENGINE] erro schedule={schedule.id}: {exc}")

        return created_tasks

    def _process_single_schedule(self, schedule: Schedule, now_utc: datetime) -> int:
        created_tasks = 0
        changed = False

        next_run_at = self._ensure_next_run_at(schedule, now_utc)
        if next_run_at is None:
            return 0

        if schedule.next_run_at != next_run_at:
            schedule.next_run_at = next_run_at
            self.db.add(schedule)
            changed = True

        if next_run_at > now_utc:
            if changed:
                self.db.commit()
            return 0

        due_times_utc, next_future_utc = self._collect_due_occurrences(schedule, now_utc)

        if not due_times_utc:
            if schedule.next_run_at != next_future_utc:
                schedule.next_run_at = next_future_utc
                self.db.add(schedule)
                changed = True

            if changed:
                self.db.commit()
            return 0

        execution_times = self._resolve_execution_times_by_policy(schedule, due_times_utc, now_utc)

        for execution_time_utc in execution_times:
            created = self._create_task(schedule, now_utc, execution_time_utc)
            if created:
                created_tasks += 1
                changed = True

        if execution_times:
            schedule.last_run_at = execution_times[-1]
            changed = True

        if next_future_utc != schedule.next_run_at:
            schedule.next_run_at = next_future_utc
            changed = True

        if schedule.calendar_type == CalendarType.ONCE and next_future_utc is None:
            schedule.active = False
            schedule.status = ScheduleStatus.INACTIVE
            changed = True

        if changed:
            self.db.add(schedule)
            self.db.commit()

        if created_tasks:
            print(
                f"[SCHEDULER_ENGINE] schedule={schedule.id} "
                f"tasks_criadas={created_tasks} "
                f"next_run_at={schedule.next_run_at}"
            )

        return created_tasks

    def _ensure_next_run_at(self, schedule: Schedule, now_utc: datetime) -> datetime | None:
        if schedule.next_run_at is not None:
            return self._normalize_utc(schedule.next_run_at)

        if schedule.schedule_type == ScheduleType.CALENDAR:
            return now_utc

        if schedule.schedule_type == ScheduleType.CRON:
            return self._compute_first_cron_occurrence(schedule, now_utc)

        return now_utc

    def _collect_due_occurrences(
        self,
        schedule: Schedule,
        now_utc: datetime,
    ) -> tuple[list[datetime], datetime | None]:
        due_times: list[datetime] = []

        current_due = self._normalize_utc(schedule.next_run_at)
        if current_due is None:
            return due_times, None

        iterations = 0
        while current_due is not None and current_due <= now_utc:
            due_times.append(current_due)
            current_due = self._compute_next_after(schedule, current_due)
            iterations += 1

            if iterations >= self.MAX_BACKFILL_OCCURRENCES:
                print(
                    f"[SCHEDULER_ENGINE] backfill_limit_reached "
                    f"schedule={schedule.id} limit={self.MAX_BACKFILL_OCCURRENCES}"
                )
                break

        return due_times, current_due

    def _resolve_execution_times_by_policy(
        self,
        schedule: Schedule,
        due_times_utc: list[datetime],
        now_utc: datetime,
    ) -> list[datetime]:
        if not due_times_utc:
            return []

        policy = schedule.policy or SchedulePolicy.CREATE_ALWAYS

        pending_statuses = (
            TaskStatus.WAITING,
            TaskStatus.SCHEDULED,
            TaskStatus.READY,
            TaskStatus.RUNNING,
            TaskStatus.STOP_REQUESTED,
        )
        running_statuses = (
            TaskStatus.READY,
            TaskStatus.RUNNING,
            TaskStatus.STOP_REQUESTED,
        )

        has_pending = self._count_tasks(schedule.id, pending_statuses) > 0
        has_running = self._count_tasks(schedule.id, running_statuses) > 0

        latest_due = due_times_utc[-1]
        is_misfire = self._is_misfire(latest_due, now_utc)

        if policy == SchedulePolicy.IGNORE_IF_RUNNING:
            if has_running:
                return []
            return [latest_due]

        if policy == SchedulePolicy.ENQUEUE_IF_NONE_PENDING:
            if has_pending:
                return []
            return [latest_due]

        if policy == SchedulePolicy.RUN_IF_MISSED:
            if is_misfire:
                return [now_utc]
            return [latest_due]

        if policy == SchedulePolicy.SKIP_IF_MISSED:
            if is_misfire:
                return []
            return [latest_due]

        return due_times_utc

    def _build_task_parameters_from_schedule(self, schedule: Schedule) -> list[dict]:
        payload: list[dict] = []

        if schedule.parameters_json is not None:
            payload.append(
                {
                    "parameter_name": "parameters_json",
                    "parameter_value": json.dumps(schedule.parameters_json, ensure_ascii=False),
                    "is_secret": False,
                    "resolved_from_credential_item_id": None,
                }
            )
            return payload

        parameters = self.task_repo.get_automation_parameters(schedule.automation_id)
        for param in parameters:
            payload.append(
                {
                    "parameter_name": param.name,
                    "parameter_value": param.default_value,
                    "is_secret": False,
                    "resolved_from_credential_item_id": None,
                }
            )

        return payload
    
    def _create_task(
        self,
        schedule: Schedule,
        now_utc: datetime,
        execution_time_utc: datetime,
    ) -> bool:
        existing = self._exists_task_for_execution(schedule.id, execution_time_utc)
        if existing:
            print(
                f"[SCHEDULER_ENGINE] duplicidade_evitar "
                f"schedule={schedule.id} task_id={existing.id} requested_start_at={execution_time_utc}"
            )
            return False

        existing_waiting = self._exists_waiting_task_for_automation(schedule.automation_id)
        if existing_waiting:
            print(
                f"[SCHEDULER_ENGINE] waiting_existente "
                f"automation_id={schedule.automation_id} task_id={existing_waiting.id}"
            )
            return False

        automation = self.task_repo.get_automation_by_id(schedule.automation_id)
        if not automation or not automation.active:
            schedule.status = ScheduleStatus.ERROR
            self.db.add(schedule)
            return False

        bot = automation.bot
        if not bot or not bot.active:
            print(f"[SCHEDULER_ENGINE] bot_inativo automation_id={automation.id}")
            return False

        bot_version = self.task_repo.get_latest_bot_version_for_bot(automation.bot_id)
        if not bot_version:
            schedule.status = ScheduleStatus.ERROR
            self.db.add(schedule)
            return False

        task = self.task_repo.create(
            {
                "automation_id": schedule.automation_id,
                "bot_version_id": bot_version.id,
                "schedule_id": schedule.id,
                "status": TaskStatus.WAITING,
                "execution_mode": ExecutionMode.SCHEDULED,
                "requested_start_at": execution_time_utc,
                "priority": automation.default_priority,
                "created_at": now_utc,
                "last_update_at": now_utc,
            }
        )

        payload = self._build_task_parameters_from_schedule(schedule)
        if payload:
            self.task_repo.create_parameters_bulk(task.id, payload)

        return True

    def _exists_task_for_execution(self, schedule_id: int, execution_time_utc: datetime) -> Task | None:
        stmt = (
            select(Task)
            .where(Task.schedule_id == schedule_id)
            .where(Task.requested_start_at == execution_time_utc)
            .order_by(Task.id.desc())
        )
        return self.db.execute(stmt).scalars().first()

    def _exists_waiting_task_for_automation(self, automation_id: int) -> Task | None:
        stmt = (
            select(Task)
            .where(Task.automation_id == automation_id)
            .where(Task.status == TaskStatus.WAITING)
            .order_by(Task.id.desc())
        )
        return self.db.execute(stmt).scalars().first()

    def _count_tasks(self, schedule_id: int, statuses: tuple[TaskStatus, ...]) -> int:
        stmt = (
            select(func.count(Task.id))
            .where(Task.schedule_id == schedule_id)
            .where(Task.status.in_(statuses))
        )
        return int(self.db.execute(stmt).scalar_one())

    def _is_misfire(self, due_utc: datetime, now_utc: datetime) -> bool:
        delta = now_utc - due_utc
        return delta.total_seconds() > self.MISFIRE_GRACE_SECONDS

    def _compute_first_cron_occurrence(self, schedule: Schedule, now_utc: datetime) -> datetime:
        if croniter is None:
            raise RuntimeError(
                "A biblioteca 'croniter' é obrigatória para schedules do tipo CRON."
            )

        if not schedule.cron_expression:
            raise ValueError("cron_expression não informado para schedule CRON.")

        tz = self._get_schedule_timezone(schedule)
        local_now = now_utc.astimezone(tz)
        base_local = local_now - timedelta(seconds=1)

        try:
            next_local = croniter(schedule.cron_expression, base_local).get_next(datetime)
        except CroniterBadCronError as exc:
            raise ValueError(f"Cron inválido: {schedule.cron_expression}") from exc

        return self._to_utc(next_local)

    def _compute_next_after(self, schedule: Schedule, base_utc: datetime) -> datetime | None:
        if schedule.schedule_type == ScheduleType.CRON:
            return self._compute_next_cron_after(schedule, base_utc)

        return self._compute_next_calendar_after(schedule, base_utc)

    def _compute_next_cron_after(self, schedule: Schedule, base_utc: datetime) -> datetime:
        if croniter is None:
            raise RuntimeError(
                "A biblioteca 'croniter' é obrigatória para schedules do tipo CRON."
            )

        if not schedule.cron_expression:
            raise ValueError("cron_expression não informado para schedule CRON.")

        tz = self._get_schedule_timezone(schedule)
        local_base = self._normalize_utc(base_utc).astimezone(tz)

        try:
            next_local = croniter(schedule.cron_expression, local_base).get_next(datetime)
        except CroniterBadCronError as exc:
            raise ValueError(f"Cron inválido: {schedule.cron_expression}") from exc

        return self._to_utc(next_local)

    def _compute_next_calendar_after(self, schedule: Schedule, base_utc: datetime) -> datetime | None:
        tz = self._get_schedule_timezone(schedule)
        local_base = self._normalize_utc(base_utc).astimezone(tz)

        calendar_type = schedule.calendar_type or CalendarType.ONCE
        value = schedule.interval_value or 1

        if calendar_type == CalendarType.ONCE:
            return None
        if calendar_type == CalendarType.SECOND:
            return self._to_utc(local_base + timedelta(seconds=value))
        if calendar_type == CalendarType.MINUTE:
            return self._to_utc(local_base + timedelta(minutes=value))
        if calendar_type == CalendarType.HOUR:
            return self._to_utc(local_base + timedelta(hours=value))
        if calendar_type == CalendarType.DAY:
            return self._to_utc(local_base + timedelta(days=value))
        if calendar_type == CalendarType.WEEK:
            return self._to_utc(local_base + timedelta(weeks=value))
        if calendar_type == CalendarType.MONTH:
            return self._to_utc(self._add_months(local_base, value))

        return self._to_utc(local_base + timedelta(minutes=value))

    def _get_schedule_timezone(self, schedule: Schedule) -> ZoneInfo:
        timezone_name = schedule.timezone or "UTC"
        try:
            return ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            return ZoneInfo("UTC")

    def _to_utc(self, dt: datetime) -> datetime:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)

    def _normalize_utc(self, dt: datetime | None) -> datetime | None:
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)

    def _add_months(self, dt: datetime, months: int) -> datetime:
        month = dt.month - 1 + months
        year = dt.year + month // 12
        month = month % 12 + 1

        if month == 12:
            next_month_year = year + 1
            next_month = 1
        else:
            next_month_year = year
            next_month = month + 1

        first_of_next_month = dt.replace(
            year=next_month_year,
            month=next_month,
            day=1,
        )
        last_day_of_target_month = (first_of_next_month - timedelta(days=1)).day
        day = min(dt.day, last_day_of_target_month)

        return dt.replace(year=year, month=month, day=day)
        