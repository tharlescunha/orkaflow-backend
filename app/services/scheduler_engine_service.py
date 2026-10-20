from __future__ import annotations

import json
import logging
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
    TaskLogLevel,
    TaskLogSource,
    TaskStatus,
)
from app.models.schedule import Schedule
from app.models.task import Task
from app.repositories.task_repository import TaskRepository
from app.services.task_events import add_task_log

logger = logging.getLogger(__name__)

try:
    from croniter import CroniterBadCronError, croniter
except ImportError:  # pragma: no cover
    croniter = None
    CroniterBadCronError = Exception

OUTCOME_CREATED = "created"
OUTCOME_DUPLICATE = "duplicate"
OUTCOME_SKIPPED = "skipped"
# Transitório (ex.: já há task aberta da automação): não consome a ocorrência.
OUTCOME_RETRY = "retry"

MAX_TEXT = 1000


class SchedulerEngineService:
    """
    Engine de schedules.

    Regra do dono: schedule NUNCA vai para ERROR por exceção, automação inativa ou
    bot sem versão. Ele continua ACTIVE:
    - exceção transitória: rollback, log, next_run_at não avança (reprocessa no próximo
      ciclo) e o motivo fica em schedule.last_error;
    - execução descartada (automação/bot inativo, sem versão, duplicidade, WAITING
      existente, políticas IGNORE/ENQUEUE...): pula a execução e grava o motivo em
      schedule.last_skipped_reason / last_skipped_at.
    - ONCE só vira INACTIVE quando a task foi realmente criada.
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
        schedule_ids = [schedule.id for schedule in schedules]
        created_tasks = 0

        for schedule_id in schedule_ids:
            try:
                schedule = self.db.get(Schedule, schedule_id)
                if schedule is None:
                    continue
                created_tasks += self._process_single_schedule(
                    schedule=schedule,
                    now_utc=now_utc,
                )
            except Exception as exc:
                self.db.rollback()
                if isinstance(exc, ValueError):
                    logger.warning("schedule=%s erro de configuração: %s", schedule_id, exc)
                else:
                    logger.exception("schedule=%s erro transitório no ciclo", schedule_id)
                self._record_error(schedule_id, exc)

        return created_tasks

    def _record_error(self, schedule_id: int, exc: Exception) -> None:
        """Grava o último erro SEM mudar o status (continua ACTIVE) nem avançar next_run_at."""
        try:
            schedule = self.db.get(Schedule, schedule_id)
            if schedule is None:
                return
            schedule.last_error = f"{type(exc).__name__}: {exc}"[:MAX_TEXT]
            self.db.add(schedule)
            self.db.commit()
        except Exception:
            self.db.rollback()
            logger.exception("schedule=%s não foi possível gravar last_error", schedule_id)

    def _process_single_schedule(self, schedule: Schedule, now_utc: datetime) -> int:
        created_tasks = 0
        duplicate_tasks = 0
        retry_tasks = 0
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

        execution_times, policy_reason = self._resolve_execution_times_by_policy(
            schedule, due_times_utc, now_utc
        )

        skip_reasons: list[str] = []
        if not execution_times and policy_reason:
            skip_reasons.append(policy_reason)

        last_created_time = None
        for execution_time_utc in execution_times:
            outcome, reason = self._create_task(schedule, now_utc, execution_time_utc)
            if outcome == OUTCOME_CREATED:
                created_tasks += 1
                last_created_time = execution_time_utc
            elif outcome == OUTCOME_DUPLICATE:
                duplicate_tasks += 1
                if reason and reason not in skip_reasons:
                    skip_reasons.append(reason)
            else:
                if outcome == OUTCOME_RETRY:
                    retry_tasks += 1
                if reason and reason not in skip_reasons:
                    skip_reasons.append(reason)

        if skip_reasons:
            new_reason = "; ".join(skip_reasons)[:MAX_TEXT]
            # Evita log a cada ciclo quando o mesmo motivo se repete (ex.: aguardando task aberta).
            if new_reason != schedule.last_skipped_reason:
                for reason in skip_reasons:
                    logger.info("schedule=%s execução descartada: %s", schedule.id, reason)
            schedule.last_skipped_reason = new_reason
            schedule.last_skipped_at = now_utc

        schedule.last_error = None

        if retry_tasks and not created_tasks and not duplicate_tasks:
            # Comportamento de junho preservado: nada foi criado por bloqueio transitório
            # (task aberta da automação), então last_run_at/next_run_at NÃO avançam e a
            # ocorrência é reavaliada no próximo ciclo. Status continua ACTIVE.
            self.db.add(schedule)
            self.db.commit()
            return 0

        if created_tasks:
            schedule.last_run_at = last_created_time

        if schedule.calendar_type == CalendarType.ONCE:
            if created_tasks or duplicate_tasks:
                schedule.next_run_at = None
                schedule.active = False
                schedule.status = ScheduleStatus.INACTIVE
            # Sem task criada: mantém ACTIVE e next_run_at para tentar de novo no próximo ciclo.
        elif next_future_utc != schedule.next_run_at:
            schedule.next_run_at = next_future_utc

        self.db.add(schedule)
        self.db.commit()

        if created_tasks:
            logger.info(
                "schedule=%s tasks_criadas=%s next_run_at=%s",
                schedule.id,
                created_tasks,
                schedule.next_run_at,
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
                logger.warning(
                    "backfill_limit_reached schedule=%s limit=%s",
                    schedule.id,
                    self.MAX_BACKFILL_OCCURRENCES,
                )
                break

        return due_times, current_due

    def _resolve_execution_times_by_policy(
        self,
        schedule: Schedule,
        due_times_utc: list[datetime],
        now_utc: datetime,
    ) -> tuple[list[datetime], str | None]:
        """Retorna (horários a executar, motivo do descarte quando a lista vem vazia)."""
        if not due_times_utc:
            return [], None

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
                return [], "Execução ignorada: política IGNORE_IF_RUNNING e há task em execução."
            return [latest_due], None

        if policy == SchedulePolicy.ENQUEUE_IF_NONE_PENDING:
            if has_pending:
                return [], "Execução ignorada: política ENQUEUE_IF_NONE_PENDING e já há task pendente."
            return [latest_due], None

        if policy == SchedulePolicy.RUN_IF_MISSED:
            if is_misfire:
                return [now_utc], None
            return [latest_due], None

        if policy == SchedulePolicy.SKIP_IF_MISSED:
            if is_misfire:
                return [], "Execução ignorada: política SKIP_IF_MISSED e o horário já passou da tolerância."
            return [latest_due], None

        return due_times_utc, None

    def _build_task_parameters_from_schedule(self, schedule: Schedule, automation) -> list[dict]:
        payload: list[dict] = []

        # Credenciais sempre vêm da automação (nunca do agendamento)
        default_params = getattr(automation, "default_parameters_json", None)
        if isinstance(default_params, dict) and default_params:
            payload.append(
                {
                    "parameter_name": "parameters_json",
                    "parameter_value": json.dumps(default_params, ensure_ascii=False),
                    "is_secret": False,
                    "resolved_from_credential_item_id": None,
                }
            )

        # Parâmetros de execução: usa flag do agendamento
        use_default = getattr(schedule, "use_default_runtime_parameters", True)
        if use_default:
            default_runtime = getattr(automation, "default_runtime_parameters_json", None)
            if isinstance(default_runtime, dict) and default_runtime:
                payload.append(
                    {
                        "parameter_name": "runtime_parameters_json",
                        "parameter_value": json.dumps(default_runtime, ensure_ascii=False),
                        "is_secret": False,
                        "resolved_from_credential_item_id": None,
                    }
                )
        else:
            custom_runtime = getattr(schedule, "runtime_parameters_json", None)
            if isinstance(custom_runtime, dict) and custom_runtime:
                payload.append(
                    {
                        "parameter_name": "runtime_parameters_json",
                        "parameter_value": json.dumps(custom_runtime, ensure_ascii=False),
                        "is_secret": False,
                        "resolved_from_credential_item_id": None,
                    }
                )

        existing_names = {item["parameter_name"] for item in payload}
        parameters = self.task_repo.get_automation_parameters(schedule.automation_id)
        for param in parameters:
            if param.name in existing_names:
                continue

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
    ) -> tuple[str, str | None]:
        """Retorna (resultado, motivo). Nunca altera o status do schedule."""
        existing = self._exists_task_for_execution(schedule.id, execution_time_utc)
        if existing:
            return (
                OUTCOME_DUPLICATE,
                f"Duplicidade evitada: task {existing.id} já existe para {execution_time_utc.isoformat()}.",
            )

        existing_open = self.task_repo.get_open_task_for_automation(schedule.automation_id)
        if existing_open:
            # Transitório: a ocorrência NÃO é consumida (o schedule tenta de novo no próximo ciclo).
            return (
                OUTCOME_RETRY,
                f"Já existe task {existing_open.id} aberta (status={existing_open.status.value}) "
                "para a automação; nova execução aguardando.",
            )

        automation = self.task_repo.get_automation_by_id(schedule.automation_id)
        if not automation or not automation.active:
            return OUTCOME_SKIPPED, "Automação inativa ou inexistente; execução pulada."

        bot = automation.bot
        if not bot or not bot.active:
            return OUTCOME_SKIPPED, "Bot inativo ou inexistente; execução pulada."

        bot_version = self.task_repo.get_latest_bot_version_for_bot(automation.bot_id)
        if not bot_version:
            return OUTCOME_SKIPPED, "Bot sem versão disponível; execução pulada."

        timeout_seconds = bot.timeout_default or 3600
        payload = self._build_task_parameters_from_schedule(schedule, automation)
        missing_required = self._find_missing_required_parameters(
            schedule.automation_id,
            payload,
        )
        if missing_required:
            return (
                OUTCOME_SKIPPED,
                "Parâmetros obrigatórios ausentes; execução pulada: " + ", ".join(missing_required),
            )

        task = self.task_repo.create(
            {
                "automation_id": schedule.automation_id,
                "bot_version_id": bot_version.id,
                "schedule_id": schedule.id,
                "status": TaskStatus.WAITING,
                "execution_mode": ExecutionMode.SCHEDULED,
                "requested_start_at": execution_time_utc,
                "priority": automation.default_priority,
                "timeout_seconds": timeout_seconds,
                "created_at": now_utc,
                "last_update_at": now_utc,
            }
        )

        if payload:
            self.task_repo.create_parameters_bulk(task.id, payload)

        add_task_log(
            self.db,
            task.id,
            (
                f"Task criada pelo agendamento '{schedule.name}' (id {schedule.id}) "
                f"para {execution_time_utc.isoformat()}."
            ),
            level=TaskLogLevel.INFO,
            source=TaskLogSource.SCHEDULER,
            event_code="SCHEDULE_TASK_CREATED",
        )

        return OUTCOME_CREATED, None

    def _find_missing_required_parameters(
        self,
        automation_id: int,
        payload: list[dict],
    ) -> list[str]:
        payload_by_name = {str(item.get("parameter_name")): item for item in payload}
        runtime_parameters = self._load_runtime_parameters(payload_by_name)

        missing: list[str] = []
        for param in self.task_repo.get_automation_parameters(automation_id):
            if not getattr(param, "required", False):
                continue
            if param.name in payload_by_name:
                continue
            if param.name in runtime_parameters:
                continue
            if getattr(param, "default_value", None) not in (None, ""):
                continue

            missing.append(param.name)

        return missing

    def _load_runtime_parameters(self, payload_by_name: dict[str, dict]) -> dict:
        runtime_param = payload_by_name.get("runtime_parameters_json")
        if not runtime_param:
            return {}

        raw_value = runtime_param.get("parameter_value")
        if not raw_value:
            return {}

        try:
            parsed_value = json.loads(raw_value)
        except Exception:
            return {}

        return parsed_value if isinstance(parsed_value, dict) else {}

    def _exists_task_for_execution(self, schedule_id: int, execution_time_utc: datetime) -> Task | None:
        stmt = (
            select(Task)
            .where(Task.schedule_id == schedule_id)
            .where(Task.requested_start_at == execution_time_utc)
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
